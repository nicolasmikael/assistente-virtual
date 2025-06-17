from typing import List, Dict, Any, Optional
import json
import os
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
import numpy as np
from functools import lru_cache
import re
from pathlib import Path
from langchain_community.document_loaders import TextLoader
from dotenv import load_dotenv

load_dotenv()

class RAGSystem:
    def __init__(self):
        """Initialize the RAG system with necessary components."""
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.2,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.embeddings = OpenAIEmbeddings(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Initialize vector stores
        self._init_vector_stores()
        
    def _init_vector_stores(self):
        """Initialize vector stores for products and knowledge base."""
        # Get project root directory
        project_root = Path(__file__).parent.parent.absolute()
        
        # Initialize products vector store
        products_file = project_root / 'data' / 'produtos.json'
        if products_file.exists():
            with open(products_file, 'r', encoding='utf-8') as f:
                self.produtos = json.load(f)
        else:
            self.produtos = []
            
        # Initialize knowledge base vector store
        knowledge_dir = project_root / 'data' / 'knowledge'
        if knowledge_dir.exists():
            self.knowledge_base = self._load_knowledge_base(knowledge_dir)
        else:
            self.knowledge_base = None
            
    def _load_knowledge_base(self, knowledge_dir: Path) -> FAISS:
        """Load and process knowledge base documents."""
        documents = []
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        
        for file in knowledge_dir.glob('*.txt'):
            loader = TextLoader(str(file), encoding='utf-8')
            documents.extend(loader.load())
            
        if not documents:
            return None
            
        texts = text_splitter.split_documents(documents)
        return FAISS.from_documents(texts, self.embeddings)
        
    async def search_products(self, query: str, filters: Optional[Dict] = None) -> List[Dict]:
        """Search for products using semantic search and filters."""
        if not self.produtos:
            return []
            
        # Apply filters if provided
        filtered_products = self.produtos
        if filters:
            if 'category' in filters:
                filtered_products = [p for p in filtered_products if p['categoria'].lower() == filters['category'].lower()]
            if 'min_price' in filters:
                filtered_products = [p for p in filtered_products if p['preco'] >= filters['min_price']]
            if 'max_price' in filters:
                filtered_products = [p for p in filtered_products if p['preco'] <= filters['max_price']]
                
        # If no products after filtering, return empty list
        if not filtered_products:
            return []
            
        # Get query embedding
        query_embedding = await self.embeddings.aembed_query(query)
        
        # Calculate similarity scores
        scored_products = []
        for product in filtered_products:
            # Create a text representation of the product
            product_text = f"{product['nome']} {product['descricao']} {product['categoria']}"
            product_embedding = await self.embeddings.aembed_query(product_text)
            
            # Calculate cosine similarity
            similarity = self._cosine_similarity(query_embedding, product_embedding)
            scored_products.append((product, similarity))
            
        # Sort by similarity score and return top 5
        scored_products.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in scored_products[:5]]
        
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        return dot_product / (norm1 * norm2) if norm1 * norm2 != 0 else 0
        
    async def query_knowledge_base(self, query: str) -> List[str]:
        """Query the knowledge base for relevant information."""
        if not self.knowledge_base:
            return []
            
        # Search for relevant documents
        docs = self.knowledge_base.similarity_search(query, k=3)
        return [doc.page_content for doc in docs]
        
    def checar_prazo_troca(self, mensagem: str) -> Optional[str]:
        """Check if the message is about exchange deadline and return appropriate response."""
        if any(keyword in mensagem.lower() for keyword in ['prazo', 'troca', 'devolução', 'devolucao', 'trocas', 'devoluções', 'devolucoes']):
            return """O prazo para troca ou devolução é de 7 dias corridos a partir do recebimento do produto.

Para realizar uma troca ou devolução:
1. Entre em contato com nosso suporte
2. Informe o número do pedido
3. Descreva o motivo da troca/devolução
4. Aguarde as instruções para envio do produto

Observações:
- O produto deve estar em perfeito estado
- A embalagem original deve estar intacta
- Todos os acessórios e manuais devem ser incluídos"""
        return None

    @lru_cache(maxsize=1000)
    def get_embedding(self, text: str):
        return self.embeddings.embed_query(text)
