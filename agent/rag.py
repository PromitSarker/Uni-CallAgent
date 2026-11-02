import os
import time
import threading
from typing import List

from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from agent.config import GEMINI_API_KEY

# Persist directory for ChromaDB
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")

_chroma_lock = threading.Lock()
_bm25_retriever = None

# Query-side embeddings client, created once and reused (it used to be rebuilt
# on every search).
try:
    _query_embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=GEMINI_API_KEY,
        task_type="retrieval_query"
    )
except Exception:
    _query_embeddings = None

# Whole-KB text cache for inlining into the voice prompt (see get_kb_text()).
KB_CACHE_TTL_SECONDS = float(os.getenv("KB_CACHE_TTL_SECONDS", "30"))
_kb_cache = {"text": None, "at": 0.0}

# Initialize embeddings
try:
    _embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=GEMINI_API_KEY,
        task_type="retrieval_document"
    )

    # Initialize Chroma vector store
    _vectorstore = Chroma(
    	collection_name="rt_comm_knowledge_gemini",
    	embedding_function=_embeddings,
    	persist_directory=CHROMA_PERSIST_DIR
    )
except Exception as e:
    import traceback
    os.makedirs("data", exist_ok=True)
    with open("data/crash.log", "w") as f:
        f.write(traceback.format_exc())
    _vectorstore = None

def _refresh_bm25():
	global _bm25_retriever
	if _vectorstore is None:
		return
	with _chroma_lock:
		try:
			all_docs_data = _vectorstore.get()
		except Exception as e:
			print(f"Error fetching from Chroma: {e}")
			return

	if not all_docs_data.get('documents'):
		_bm25_retriever = None
		return
	
	all_documents = [
		Document(page_content=doc, metadata=meta or {}) 
		for doc, meta in zip(all_docs_data['documents'], all_docs_data['metadatas'])
	]
	_bm25_retriever = BM25Retriever.from_documents(all_documents)

# Initial BM25 load
_refresh_bm25()

def add_document(text: str, metadata: dict = None) -> list[str]:
	"""Adds a document to the Chroma vector store after chunking, and returns the IDs."""
	if _vectorstore is None:
		raise RuntimeError("Vector store is not initialized. Check crash.log.")
	import uuid
	
	text_splitter = RecursiveCharacterTextSplitter(
		chunk_size=1000,
		chunk_overlap=150,
		separators=["\n\n", "\n", ". ", " ", ""]
	)
	chunks = text_splitter.split_text(text)
	
	doc_ids = []
	docs = []
	for chunk in chunks:
		doc_id = str(uuid.uuid4())
		doc_ids.append(doc_id)
		docs.append(Document(page_content=chunk, metadata=metadata or {}))
	
	with _chroma_lock:
		_vectorstore.add_documents(documents=docs, ids=doc_ids)
	
	invalidate_kb_cache()
	_refresh_bm25()
	return doc_ids

def delete_document(doc_id: str) -> bool:
	"""Deletes a document from the Chroma vector store by ID."""
	if _vectorstore is None:
		return False
	try:
		with _chroma_lock:
			_vectorstore.delete(ids=[doc_id])
		invalidate_kb_cache()
		_refresh_bm25()
		return True
	except ValueError:
		# ID not found
		return False

def search_documents(query: str, k: int = 5) -> str:
	"""Searches the vector store using Hybrid Search (BM25 + Vector) and returns a formatted string of results."""
	if _vectorstore is None:
		return "Vector store is offline."
	
	print(f"[RAG Search] Query: '{query}', k={k}")
	
	# 1. Dense Retriever (query embeddings client is created once at import)
	query_embeddings = _query_embeddings
	
	vector_results = []
	# Retry logic for embeddings API
	for attempt in range(3):
		try:
			if query_embeddings is None:
				raise RuntimeError("query embeddings client is not initialised")
			embedded_query = query_embeddings.embed_query(query)
			with _chroma_lock:
				vector_results = _vectorstore.similarity_search_by_vector(embedded_query, k=k)
			break
		except Exception as e:
			print(f"[RAG Search] Embeddings attempt {attempt + 1} failed: {e}")
			if attempt < 2:
				# Back off between attempts only (no pointless sleep after the last one).
				time.sleep(0.5 * (2 ** attempt))
	
	print(f"[RAG Search] Vector results: {len(vector_results)} docs")
	for i, doc in enumerate(vector_results):
		print(f"  [Vector #{i+1}] {doc.page_content[:100]}...")
	
	# 2. Sparse Retriever (BM25) setup
	sparse_results = []
	if _bm25_retriever is not None:
		_bm25_retriever.k = k
		try:
			sparse_results = _bm25_retriever.invoke(query)
		except Exception as e:
			print(f"[RAG Search] BM25 invoke failed: {e}")
		
		print(f"[RAG Search] BM25 results: {len(sparse_results)} docs")
		for i, doc in enumerate(sparse_results):
			print(f"  [BM25 #{i+1}] {doc.page_content[:100]}...")
	
	if not vector_results and not sparse_results:
		return "No relevant information found in the knowledge base."
		
	# 3. Manual Reciprocal Rank Fusion (RRF)
	fused_scores = {}
	for rank, doc in enumerate(sparse_results):
		if doc.page_content not in fused_scores:
			fused_scores[doc.page_content] = {"doc": doc, "score": 0}
		fused_scores[doc.page_content]["score"] += 1 / (rank + 60)
		
	for rank, doc in enumerate(vector_results):
		if doc.page_content not in fused_scores:
			fused_scores[doc.page_content] = {"doc": doc, "score": 0}
		fused_scores[doc.page_content]["score"] += 1 / (rank + 60)
		
	reranked = sorted(fused_scores.values(), key=lambda x: x["score"], reverse=True)
	final_results = [x["doc"] for x in reranked][:k]
	
	print(f"[RAG Search] Final RRF results: {len(final_results)} docs")
	for i, item in enumerate(reranked[:k]):
		print(f"  [RRF #{i+1} score={item['score']:.4f}] {item['doc'].page_content[:100]}...")
	
	if not final_results:
		return "No relevant information found in the knowledge base."
	
	formatted = []
	for doc in final_results:
		formatted.append(f"<knowledge_base_document>\n{doc.page_content}\n</knowledge_base_document>")
	
	return "\n\n".join(formatted)

def list_documents() -> List[dict]:
	"""Returns all documents from the vector store."""
	if _vectorstore is None:
		return []
	with _chroma_lock:
		results = _vectorstore.get()
	documents = []
	
	if not results or "ids" not in results:
		return documents
		
	for i in range(len(results["ids"])):
		doc_id = results["ids"][i]
		text = results["documents"][i] if "documents" in results and results["documents"] else ""
		metadata = results["metadatas"][i] if "metadatas" in results and results["metadatas"] else {}
		documents.append({
			"id": doc_id,
			"text": text,
			"metadata": metadata
		})
	
	return documents


def invalidate_kb_cache() -> None:
	"""Drop the cached whole-KB text (called after documents change)."""
	_kb_cache["text"] = None
	_kb_cache["at"] = 0.0


def get_kb_text(max_chars: int = 0):
	"""Return the entire knowledge base as one prompt-ready string, or None.

	Used to put the (small) KB straight into the voice agent's system prompt so
	a spoken question needs no search round trip. Returns None when the KB is
	empty/unavailable or larger than ``max_chars`` (0 = no limit); the caller
	then falls back to the search tool. Cached for KB_CACHE_TTL_SECONDS so a new
	call does not hit Chroma, while edits (also made by other worker processes)
	show up within the TTL.
	"""
	if _vectorstore is None:
		return None

	now = time.monotonic()
	cached = _kb_cache["text"]
	if cached is None or now - _kb_cache["at"] > KB_CACHE_TTL_SECONDS:
		try:
			with _chroma_lock:
				data = _vectorstore.get()
		except Exception as e:
			print(f"[RAG] get_kb_text failed: {e}")
			return cached if cached else None
		docs = [d.strip() for d in (data.get("documents") or []) if d and d.strip()]
		cached = "\n\n".join(docs) if docs else ""
		_kb_cache["text"] = cached
		_kb_cache["at"] = now

	if not cached:
		return None
	if max_chars and len(cached) > max_chars:
		return None
	return cached

