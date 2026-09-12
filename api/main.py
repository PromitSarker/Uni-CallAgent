from fastapi import FastAPI

from api.routers.chat import router as chat_router
from api.routers.documents import router as documents_router
from api.routers.admin import router as admin_router
from api.routers.upload import router as upload_router
from api.routers.voice import router as voice_router
from api.routers.voice_stream import router as voice_stream_router

from fastapi.staticfiles import StaticFiles
import os


from fastapi.middleware.cors import CORSMiddleware

def create_app() -> FastAPI:
	app = FastAPI(
		title="Unified IT API",
		version="1.0.0",
		description="Minimal chat API backed by Unified IT LangGraph agent.",
	)

	allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
	allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

	app.add_middleware(
		CORSMiddleware,
		allow_origins=allowed_origins,
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"],
	)

	app.include_router(chat_router, prefix="/api")
	app.include_router(documents_router, prefix="/api")
	app.include_router(admin_router, prefix="/api")
	app.include_router(upload_router, prefix="/api")
	app.include_router(voice_router, prefix="/api")
	app.include_router(voice_stream_router, prefix="/api")
	from api.routers.timesheets import router as timesheets_router
	app.include_router(timesheets_router, prefix="/api")

	
	uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
	os.makedirs(uploads_dir, exist_ok=True)
	app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
	
	@app.get("/api/test-llm")
	def test_llm():
		try:
			from langchain_google_genai import ChatGoogleGenerativeAI
			from agent.config import GEMINI_API_KEY, GEMINI_MODEL
			
			llm = ChatGoogleGenerativeAI(
				model=GEMINI_MODEL,
				api_key=GEMINI_API_KEY,
			)
			res = llm.invoke("Hello, are you there?")
			return {
				"status": "success", 
				"response": res.content, 
				"model": GEMINI_MODEL, 
				"key_configured": bool(GEMINI_API_KEY)
			}
		except Exception as e:
			import traceback
			return {
				"status": "error", 
				"error": str(e), 
				"traceback": traceback.format_exc()
			}
			
	return app

app = create_app()
