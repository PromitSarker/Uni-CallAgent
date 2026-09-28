import os
from typing import List

from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from agent.config import GEMINI_API_KEY

# Persist directory for ChromaDB
CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")

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
	
	_vectorstore.add_documents(documents=docs, ids=doc_ids)
	return doc_ids

def delete_document(doc_id: str) -> bool:
	"""Deletes a document from the Chroma vector store by ID."""
	if _vectorstore is None:
		return False
	try:
		_vectorstore.delete(ids=[doc_id])
		return True
	except ValueError:
		# ID not found
		return False

def search_documents(query: str, k: int = 5) -> str:
	"""Searches the vector store using Hybrid Search (BM25 + Vector) and returns a formatted string of results."""
	if _vectorstore is None:
		return "Vector store is offline."
	
	# 1. Dense Retriever setup (using custom query embeddings)
	query_embeddings = GoogleGenerativeAIEmbeddings(
		model="models/gemini-embedding-001",
		google_api_key=GEMINI_API_KEY,
		task_type="retrieval_query"
	)
	
	# We perform manual search for the vector part to keep the 'retrieval_query' embeddings
	vector_results = _vectorstore.similarity_search_by_vector(
		query_embeddings.embed_query(query), k=k
	)
	
	# 2. Sparse Retriever (BM25) setup
	all_docs_data = _vectorstore.get()
	if not all_docs_data.get('documents'):
		if not vector_results:
			return "No relevant information found in the knowledge base."
		final_results = vector_results
	else:
		all_documents = [
			Document(page_content=doc, metadata=meta) 
			for doc, meta in zip(all_docs_data['documents'], all_docs_data['metadatas'])
		]
		bm25_retriever = BM25Retriever.from_documents(all_documents)
		bm25_retriever.k = k
		
		# Get BM25 results
		sparse_results = bm25_retriever.invoke(query)
		
		# 3. Manual Reciprocal Rank Fusion (RRF) since we bypass EnsembleRetriever to keep custom embeddings
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
