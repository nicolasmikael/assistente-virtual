from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
from pathlib import Path
from dotenv import load_dotenv
import logging
import re
import json

from assistente import AssistenteVirtual
from rag_system import RAGSystem

load_dotenv()

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Get the absolute path to the static directory
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


def handle_error(endpoint: str, error: Exception) -> JSONResponse:
    """Log the error and return a standardized JSON response."""
    logger.exception("Error in %s: %s", endpoint, error)
    return JSONResponse(
        status_code=500,
        content={"error": "Ocorreu um erro interno. Por favor, tente novamente mais tarde."},
    )

app = FastAPI(
    title="Assistente Virtual E-commerce",
    description="API para o assistente virtual de e-commerce",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Initialize components
assistente = AssistenteVirtual()
rag_system = RAGSystem()

class ChatRequest(BaseModel):
    content: str
    context: Optional[Dict] = None

class SearchRequest(BaseModel):
    query: str
    filters: Optional[Dict] = None

class KnowledgeRequest(BaseModel):
    query: str

@app.get("/")
async def read_root():
    """
    Serve the main page.
    """
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.post("/chat")
async def chat(request: ChatRequest):
    """Processa uma mensagem do usuário e retorna a resposta do assistente."""
    try:
        resposta = await assistente.processar_mensagem(request.content, request.context)
        return {"response": resposta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search/products")
async def search_products(request: SearchRequest):
    """Busca produtos no catálogo."""
    try:
        produtos = await rag_system.search_products(request.query, request.filters)
        return {"products": produtos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query/knowledge")
async def query_knowledge(request: KnowledgeRequest):
    """Consulta a base de conhecimento."""
    try:
        info_chunks = await rag_system.query_knowledge_base(request.query)
        return {"chunks": info_chunks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/chat/history")
async def get_chat_history():
    """Retorna o histórico de chat."""
    try:
        return {"history": assistente.get_chat_history()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/chat/history")
async def clear_chat_history():
    """Limpa o histórico de chat."""
    try:
        assistente.clear_chat_history()
        return {"message": "Histórico de chat limpo com sucesso"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
