import os
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from dotenv import load_dotenv
from datetime import datetime
from rag_system import RAGSystem
import re
import json
from pathlib import Path
from prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

load_dotenv()

# Get the absolute path to the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
PEDIDOS_FILE = PROJECT_ROOT / 'data' / 'pedidos.json'

def load_pedidos() -> List[Dict]:
    """Carrega os pedidos do arquivo JSON."""
    try:
        if not PEDIDOS_FILE.exists():
            return []
            
        with open(PEDIDOS_FILE, 'r', encoding='utf-8') as f:
            pedidos = json.load(f)
            
        if not isinstance(pedidos, list):
            return []
            
        return pedidos
    except Exception:
        return []

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
            model_name="gpt-4",
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.rag_system = RAGSystem()
        self.system_prompt = SYSTEM_PROMPT
        self.chat_history: List[Dict] = []
        self.pedidos = load_pedidos()

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
        """Busca informações de um pedido específico."""
        pedido_id = None
        
        # Procura por padrões como #12345, pedido: 12345, etc.
        match = re.search(r'(?:pedido[\s#:]*|#)(\d+)', mensagem.lower())
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
            
        # Converte para string e remove espaços para comparação
        pedido_id = str(pedido_id).strip()
        
        # Recarrega pedidos para garantir dados atualizados
        self.pedidos = load_pedidos()
        
        for pedido in self.pedidos:
            pedido_atual = str(pedido['pedido_id']).strip()
            if pedido_atual == pedido_id:
                return pedido
                
        return None

    async def processar_mensagem(self, mensagem: str, contexto: Optional[Dict] = None) -> str:
        try:
            # Checagem simples de prazo de troca
            resposta_troca = self.rag_system.checar_prazo_troca(mensagem)
            if resposta_troca:
                return resposta_troca

            # Consulta de pedidos
            if 'pedido' in mensagem.lower():
                pedido = self._buscar_pedido(mensagem)
                
                if pedido:
                    try:
                        produtos = ', '.join([p['nome'] for p in pedido['produtos']])
                        return f"Status do pedido {pedido['pedido_id']}: {pedido['status']}. Produtos: {produtos}. Data da compra: {pedido['data_compra']}. Previsão de entrega: {pedido['previsao_entrega']}."
                    except KeyError:
                        return "Desculpe, encontrei o pedido mas há informações faltando. Por favor, entre em contato com o suporte."
                elif re.search(r'\d+', mensagem):
                    return "Desculpe, não encontrei esse pedido em nossa base. Verifique o número e tente novamente."
                else:
                    return "Para consultar o status do seu pedido, por favor informe o número do pedido. Exemplo: 'Qual o status do pedido #12345?'"

            # Perguntas sobre produtos
            if any(keyword in mensagem.lower() for keyword in ['produto', 'produtos', 'notebook', 'smartphone', 'celular', 'computador', 'livro', 'tênis', 'panelas', 'cozinha', 'presente']):
                category = self._extract_category(mensagem)
                filters = {"category": category} if category else None
                produtos = await self.rag_system.search_products(mensagem, filters)
                if produtos:
                    produtos_info = []
                    for i, p in enumerate(produtos):
                        specs = ", ".join([f"{k}: {v}" for k, v in p['especificacoes'].items()])
                        produto_info = f"""
{i+1}. {p['nome']}
   Preço: R${p['preco']:.2f}
   Categoria: {p['categoria']}
   Descrição: {p['descricao']}
   Especificações: {specs}
   Status: {'Disponível' if p['disponivel'] else 'Indisponível'}
"""
                        produtos_info.append(produto_info)
                    contexto_produtos = "Produtos disponíveis no catálogo:\n" + "\n".join(produtos_info)
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
            
        except Exception:
            return "Desculpe, tive um problema ao processar sua mensagem. Por favor, tente novamente em alguns instantes."

    def get_chat_history(self) -> List[Dict]:
        """Return the chat history."""
        return self.chat_history

    def clear_chat_history(self):
        """Clear the chat history."""
        self.chat_history = [] 
