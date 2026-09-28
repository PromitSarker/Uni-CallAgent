from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
import json
from pypdf import PdfReader

from agent.rag import add_document, delete_document, list_documents

router = APIRouter(prefix="/documents", tags=["documents"])

class DocumentCreateRequest(BaseModel):
	text: str
	metadata: dict = None

class DocumentResponse(BaseModel):
	id: str
	status: str

class DocumentListResponse(BaseModel):
	documents: list[dict]

@router.get("", response_model=DocumentListResponse)
def get_documents() -> DocumentListResponse:
	try:
		docs = list_documents()
		return DocumentListResponse(documents=docs)
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to fetch documents: {str(e)}")

@router.post("", response_model=DocumentResponse)
def create_document(payload: DocumentCreateRequest) -> DocumentResponse:
	if not payload.text.strip():
		raise HTTPException(status_code=400, detail="Document text cannot be empty.")
	
	try:
		doc_ids = add_document(payload.text, payload.metadata)
		return DocumentResponse(id=",".join(doc_ids), status=f"created {len(doc_ids)} chunks")
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to add document: {str(e)}")

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...), metadata_str: str = Form(None)) -> DocumentResponse:
	if not file.filename.lower().endswith(".pdf"):
		raise HTTPException(status_code=400, detail="Only PDF files are supported.")
	
	try:
		# Parse optional metadata
		metadata = {}
		if metadata_str:
			try:
				parsed = json.loads(metadata_str)
				if isinstance(parsed, dict):
					metadata = parsed
				else:
					metadata = {"info": str(parsed)}
			except json.JSONDecodeError:
				metadata = {"info": metadata_str}

		# Extract text from PDF
		reader = PdfReader(file.file)
		text_content = []
		for page in reader.pages:
			text = page.extract_text()
			if text:
				text_content.append(text)
		
		full_text = "\n".join(text_content)
		if not full_text.strip():
			raise HTTPException(status_code=400, detail="Failed to extract any text from the PDF.")
			
		doc_ids = add_document(full_text, metadata)
		return DocumentResponse(id=",".join(doc_ids), status=f"created {len(doc_ids)} chunks from PDF")
	except HTTPException:
		raise
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Failed to process PDF document: {str(e)}")

@router.delete("/{doc_id}")
def remove_document(doc_id: str):
	success = delete_document(doc_id)
	if not success:
		raise HTTPException(status_code=404, detail="Document not found or could not be deleted.")
	return {"id": doc_id, "status": "deleted"}
