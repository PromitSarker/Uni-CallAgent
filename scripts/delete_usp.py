import sys
sys.path.append('.')
from agent.rag import list_documents, delete_document

docs = list_documents()
for doc in docs:
    meta = doc.get("metadata") or {}
    title = meta.get("title", "")
    if "Unique Selling Propositions (USPs)" in title or "USP" in title:
        print(f"Deleting doc {doc['id']}")
        delete_document(doc["id"])
