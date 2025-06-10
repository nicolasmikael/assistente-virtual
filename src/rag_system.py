from typing import List, Dict, Any
import json
import os
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
import numpy as np
from functools import lru_cache

class RAGSystem:
    def __init__(self):
        """Initialize the RAG system with necessary components."""
        self.embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
        self.product_index = None
        self.knowledge_base_index = None
        self.initialize_indices()

    def initialize_indices(self):
        """Initialize vector indices for products and knowledge base."""
        # Load and process product data
        with open("data/produtos.json", "r", encoding="utf-8") as f:
            products = json.load(f)
        
        # Create product documents with more structured information
        product_docs = []
        for product in products:
            doc = f"""
            ID: {product['id']}
            Nome: {product['nome']}
            Categoria: {product['categoria']}
            Preço: R${product['preco']}
            Descrição: {product['descricao']}
            Especificações: {json.dumps(product['especificacoes'], ensure_ascii=False)}
            Disponibilidade: {'Disponível' if product['disponivel'] else 'Indisponível'}
            """
            product_docs.append(doc)
        
        # Create product index
        self.product_index = FAISS.from_texts(
            product_docs,
            self.embeddings,
            metadatas=[{"type": "product", "id": p["id"]} for p in products]
        )
        
        # Load and process knowledge base
        with open("data/politicas.md", "r", encoding="utf-8") as f:
            knowledge_text = f.read()
        
        # Split knowledge base into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        knowledge_chunks = text_splitter.split_text(knowledge_text)
        
        # Create knowledge base index
        self.knowledge_base_index = FAISS.from_texts(
            knowledge_chunks,
            self.embeddings,
            metadatas=[{"type": "knowledge"} for _ in knowledge_chunks]
        )

    async def search_products(self, query: str, filters: Dict[str, Any] = None) -> List[Dict]:
        """
        Search for products using semantic search and filters.
        
        Args:
            query: The search query
            filters: Optional filters (price range, category, etc.)
            
        Returns:
            List of matching products
        """
        # Perform semantic search with higher k for better recall
        docs = self.product_index.similarity_search_with_score(query, k=10)
        
        # Load full product data
        with open("data/produtos.json", "r", encoding="utf-8") as f:
            all_products = json.load(f)
        
        # Filter and score results
        scored_results = []
        for doc, score in docs:
            product_id = doc.metadata["id"]
            product = next((p for p in all_products if p["id"] == product_id), None)
            
            if product and self._apply_filters(product, filters):
                # Calculate relevance score based on multiple factors
                relevance_score = self._calculate_relevance_score(product, query, score)
                scored_results.append((product, relevance_score))
        
        # Sort by relevance score and return top results
        scored_results.sort(key=lambda x: x[1], reverse=True)
        return [product for product, _ in scored_results[:3]]  # Return top 3 most relevant products

    def _calculate_relevance_score(self, product: Dict, query: str, semantic_score: float) -> float:
        """Calculate a relevance score for a product based on multiple factors."""
        query = query.lower()
        score = 1.0 - semantic_score  # Convert distance to similarity score
        
        # Boost score for exact matches in name
        if any(word in product['nome'].lower() for word in query.split()):
            score *= 1.5
        
        # Boost score for category matches
        if any(word in product['categoria'].lower() for word in query.split()):
            score *= 1.3
        
        # Boost score for description matches
        if any(word in product['descricao'].lower() for word in query.split()):
            score *= 1.2
        
        return score

    def _apply_filters(self, product: Dict, filters: Dict[str, Any] = None) -> bool:
        """Apply filters to a product."""
        if not filters:
            return True
            
        if "max_price" in filters and product["preco"] > filters["max_price"]:
            return False
            
        if "min_price" in filters and product["preco"] < filters["min_price"]:
            return False
            
        if "category" in filters and product["categoria"].lower() != filters["category"].lower():
            return False
            
        return True

    async def query_knowledge_base(self, query: str) -> List[str]:
        """
        Query the knowledge base for relevant information.
        
        Args:
            query: The question or query
            
        Returns:
            List of relevant information chunks
        """
        docs = self.knowledge_base_index.similarity_search(query, k=3)
        return [doc.page_content for doc in docs]

    @lru_cache(maxsize=1000)
    def get_embedding(self, text: str):
        return self.embeddings.embed_query(text) 
