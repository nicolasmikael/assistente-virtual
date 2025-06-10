from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
import os
from dotenv import load_dotenv
from datetime import datetime
from rag_system import RAGSystem
import re
import json
from prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

load_dotenv()

def filtrar_resposta_produtos(resposta: str, produtos_catalogo: List[Dict]) -> str:
    nomes_produtos = [p['nome'].lower() for p in produtos_catalogo]
    linhas = resposta.split('\n')
    resposta_filtrada = []
    for linha in linhas:
        if any(nome in linha.lower() for nome in nomes_produtos):
            resposta_filtrada.append(linha)
    if not resposta_filtrada:
        return 'Desculpe, não encontrei produtos relevantes no nosso catálogo.'
    return '\n'.join(resposta_filtrada)

class AssistenteVirtual:
    def __init__(self):
        """Initialize the virtual assistant with necessary components."""
        self.llm = ChatOpenAI(
            model_name="o4-mini",
            temperature=1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.rag_system = RAGSystem()
        
        self.system_prompt = SYSTEM_PROMPT
        
        self.chat_history: List[Dict] = []

    def _extract_category(self, message: str) -> Optional[str]:
        """Extract category from message if present."""
        categories = {
            'eletrônicos': ['eletrônicos', 'eletronicos', 'notebook', 'computador', 'celular', 'smartphone'],
            'casa': ['casa', 'panelas', 'utensílios', 'utensilios', 'cozinha', 'fogão', 'panela', 'presente de cozinha'],
            'esportes': ['esportes', 'tênis', 'tenis', 'corrida'],
            'livros': ['livros', 'livro', 'leitura']
        }
        
        message = message.lower()
        for category, keywords in categories.items():
            if any(keyword in message for keyword in keywords):
                return category
        return None

    def _buscar_pedido(self, mensagem: str) -> Optional[Dict]:
        # Tenta extrair o número do pedido em qualquer formato
        pedido_id = None
        # Primeiro tenta o padrão mais comum
        match = re.search(r'pedido[\s#:]*([0-9]+)', mensagem.lower())
        if match:
            pedido_id = match.group(1)
        else:
            # Fallback: pega qualquer número na mensagem se 'pedido' estiver presente
            if 'pedido' in mensagem.lower():
                numeros = re.findall(r'\d+', mensagem)
                if numeros:
                    pedido_id = numeros[0]
        if not pedido_id:
            return None
        try:
            with open('data/pedidos.json', 'r', encoding='utf-8') as f:
                pedidos = json.load(f)
            for pedido in pedidos:
                if str(pedido['pedido_id']) == str(pedido_id):
                    return pedido
        except Exception as e:
            print(f"Erro ao buscar pedido: {e}")
        return None

    async def processar_mensagem(self, mensagem: str, contexto: Optional[Dict] = None) -> str:
        """
        Process a user message and return an appropriate response.
        
        Args:
            mensagem: The user's message
            contexto: Optional context information (e.g., user preferences, order history)
            
        Returns:
            str: The assistant's response
        """
        try:
            # Consulta de pedidos (primeiro tenta buscar o pedido)
            if 'pedido' in mensagem.lower():
                pedido = self._buscar_pedido(mensagem)
                if pedido:
                    produtos = ', '.join([p['nome'] for p in pedido['produtos']])
                    return f"Status do pedido {pedido['pedido_id']}: {pedido['status']}. Produtos: {produtos}. Data da compra: {pedido['data_compra']}. Previsão de entrega: {pedido['previsao_entrega']}."
                # Se não encontrou número, oriente o usuário
                if not re.search(r'\d+', mensagem):
                    return "Para consultar o status do seu pedido, por favor informe o número do pedido. Exemplo: 'Qual o status do pedido #12345?'"
                else:
                    return "Desculpe, não encontrei esse pedido em nossa base. Verifique o número e tente novamente."

            # Perguntas sobre produtos
            if any(keyword in mensagem.lower() for keyword in ['produto', 'produtos', 'notebook', 'smartphone', 'celular', 'computador', 'livro', 'tênis', 'panelas', 'cozinha', 'presente']):
                category = self._extract_category(mensagem)
                filters = {"category": category} if category else None
                produtos = await self.rag_system.search_products(mensagem, filters)
                if produtos:
                    produtos_info = "\n".join([f"{i+1}. {p['nome']} - {p['descricao']}" for i, p in enumerate(produtos)])
                    contexto_produtos = f"Produtos disponíveis no catálogo:\n{produtos_info}"
                else:
                    contexto_produtos = "Nenhum produto relevante encontrado no catálogo."
                prompt_text = USER_PROMPT_TEMPLATE.format(mensagem=mensagem, produtos_contexto=produtos_info if produtos else "Nenhum produto relevante encontrado.")
                prompt = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=prompt_text)
                ])

            # Perguntas sobre políticas da loja
            elif any(keyword in mensagem.lower() for keyword in ['política', 'politica', 'troca', 'devolução', 'devolucao', 'entrega', 'pagamento', 'garantia', 'prazo', 'suporte']):
                info_chunks = await self.rag_system.query_knowledge_base(mensagem)
                contexto_politicas = "\n".join(info_chunks)
                prompt = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=f"{mensagem}\n\nInformações relevantes da política da loja:\n{contexto_politicas}")
                ])

            else:
                # Para outras mensagens, usa o prompt normal
                prompt = ChatPromptTemplate.from_messages([
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=mensagem)
                ])

            # Get response from LLM
            response = await self.llm.agenerate([prompt.format_messages()])
            resposta_texto = response.generations[0][0].text

            # Pós-processamento para garantir que só produtos do catálogo sejam exibidos
            if 'produtos' in mensagem.lower() or 'presente' in mensagem.lower() or 'cozinha' in mensagem.lower():
                resposta_texto = filtrar_resposta_produtos(resposta_texto, produtos if 'produtos' in locals() else [])
            
            # Store in chat history
            self.chat_history.append({
                "user": mensagem,
                "assistant": resposta_texto,
                "timestamp": datetime.now().isoformat()
            })
            
            return resposta_texto
            
        except Exception as e:
            # Log the error and return a graceful error message
            print(f"Error processing message: {str(e)}")
            return "Desculpe, tive um problema ao processar sua mensagem. Por favor, tente novamente em alguns instantes."

    def get_chat_history(self) -> List[Dict]:
        """Return the chat history."""
        return self.chat_history

    def clear_chat_history(self):
        """Clear the chat history."""
        self.chat_history = [] 
