from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict
from pathlib import Path
from dotenv import load_dotenv
import logging
import re

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

class Message(BaseModel):
    content: str
    context: Optional[Dict] = None

class ProductSearch(BaseModel):
    query: str
    filters: Optional[Dict] = None

class KnowledgeQuery(BaseModel):
    query: str

@app.get("/")
async def read_root():
    """
    Serve the main page.
    """
    return FileResponse(str(STATIC_DIR / "index.html"))

@app.post("/chat")
async def chat(message: Message):
    """
    Process a chat message and return the assistant's response.
    """
    try:
        # Perguntas genéricas sobre pedidos (sem número)
        if any(keyword in message.content.lower() for keyword in ['status do pedido', 'meu pedido', 'acompanhar pedido', 'onde está meu pedido', 'pedido', 'acompanhar entrega']) and not re.search(r'pedido[\\s#:]*[0-9]+', message.content.lower()):
            return {"response": "Para consultar o status do seu pedido, por favor informe o número do pedido. Exemplo: 'Qual o status do pedido #12345?'"}

        response = await assistente.processar_mensagem(message.content, message.context)
        return {"response": response}
    except Exception as e:
        return handle_error("chat", e)

@app.post("/search/products")
async def search_products(search: ProductSearch):
    """
    Search for products using semantic search and filters.
    """
    try:
        results = await rag_system.search_products(search.query, search.filters)
        return {"products": results}
    except Exception as e:
        return handle_error("search_products", e)

@app.post("/query/knowledge")
async def query_knowledge(query: KnowledgeQuery):
    """
    Query the knowledge base for relevant information.
    """
    try:
        results = await rag_system.query_knowledge_base(query.query)
        return {"information": results}
    except Exception as e:
        return handle_error("query_knowledge", e)

@app.get("/chat/history")
async def get_chat_history():
    """
    Get the chat history.
    """
    return {"history": assistente.get_chat_history()}

@app.delete("/chat/history")
async def clear_chat_history():
    """
    Clear the chat history.
    """
    assistente.clear_chat_history()
    return {"message": "Chat history cleared"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
