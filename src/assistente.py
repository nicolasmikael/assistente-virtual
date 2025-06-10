print("assistente.py foi carregado!")  # DEBUG GLOBAL
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
from pathlib import Path
from prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
import sys

# Força a saída do console para não bufferizar
sys.stdout.reconfigure(line_buffering=True)

load_dotenv()

# Get the absolute path to the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
PEDIDOS_FILE = PROJECT_ROOT / 'data' / 'pedidos.json'

def debug_print(*args, **kwargs):
    """Função auxiliar para debug que força a saída imediata"""
    print(*args, **kwargs, flush=True)

def load_pedidos() -> List[Dict]:
    """
    Carrega os pedidos do arquivo JSON com tratamento de erros robusto.
    
    Returns:
        List[Dict]: Lista de pedidos ou lista vazia em caso de erro
    """
    debug_print(f"\n[DEBUG] ===== CARREGANDO PEDIDOS =====")
    debug_print(f"[DEBUG] Caminho do arquivo: {PEDIDOS_FILE}")
    debug_print(f"[DEBUG] Arquivo existe? {PEDIDOS_FILE.exists()}")
    
    try:
        if not PEDIDOS_FILE.exists():
            debug_print(f"[ERRO] Arquivo de pedidos não encontrado em: {PEDIDOS_FILE}")
            return []
            
        # Tenta diferentes encodings
        encodings = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
        for encoding in encodings:
            try:
                debug_print(f"[DEBUG] Tentando encoding: {encoding}")
                with open(PEDIDOS_FILE, 'r', encoding=encoding) as f:
                    conteudo = f.read()
                    # Corrige problemas de encoding em memória
                    conteudo = conteudo.replace('Ã¢', 'â')
                    conteudo = conteudo.replace('Ã£', 'ã')
                    conteudo = conteudo.replace('Ã©', 'é')
                    conteudo = conteudo.replace('Ã³', 'ó')
                    conteudo = conteudo.replace('Ãº', 'ú')
                    conteudo = conteudo.replace('Ã§', 'ç')
                    debug_print(f"[DEBUG] Conteúdo do arquivo após correção (primeiros 200 caracteres): {conteudo[:200]}")
                    pedidos = json.loads(conteudo)
                    
                if not isinstance(pedidos, list):
                    debug_print(f"[ERRO] Arquivo de pedidos não contém uma lista válida. Tipo recebido: {type(pedidos)}")
                    continue
                    
                debug_print(f"[DEBUG] Pedidos carregados com sucesso usando encoding {encoding}. Total: {len(pedidos)}")
                for i, pedido in enumerate(pedidos):
                    debug_print(f"[DEBUG] Pedido {i+1}: {pedido}")
                return pedidos
            except UnicodeDecodeError:
                debug_print(f"[DEBUG] Falha ao decodificar com {encoding}")
                continue
            except json.JSONDecodeError as e:
                debug_print(f"[ERRO] Erro ao decodificar JSON com {encoding}: {e}")
                debug_print(f"[DEBUG] Posição do erro: {e.pos}")
                debug_print(f"[DEBUG] Linha do erro: {e.lineno}")
                debug_print(f"[DEBUG] Coluna do erro: {e.colno}")
                continue
                
        debug_print("[ERRO] Falha ao carregar pedidos com todos os encodings tentados")
        return []
            
    except Exception as e:
        debug_print(f"[ERRO] Erro inesperado ao carregar pedidos: {str(e)}")
        debug_print(f"[DEBUG] Tipo do erro: {type(e)}")
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
        debug_print("[DEBUG] Inicializando AssistenteVirtual")
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            temperature=0.2,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        self.rag_system = RAGSystem()
        self.system_prompt = SYSTEM_PROMPT
        self.chat_history: List[Dict] = []
        
        # Carrega pedidos na inicialização
        debug_print("[DEBUG] Carregando pedidos na inicialização")
        self.pedidos = load_pedidos()
        debug_print(f"[DEBUG] Pedidos carregados na inicialização: {len(self.pedidos)}")
        if not self.pedidos:
            debug_print("[ERRO] Nenhum pedido foi carregado na inicialização!")

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
        """
        Busca informações de um pedido específico.
        
        Args:
            mensagem: Mensagem do usuário contendo o número do pedido
            
        Returns:
            Optional[Dict]: Dicionário com informações do pedido ou None se não encontrado
        """
        debug_print(f"\n[DEBUG] ===== INÍCIO DA BUSCA DE PEDIDO =====")
        debug_print(f"[DEBUG] Mensagem recebida: '{mensagem}'")
        
        pedido_id = None
        
        # Procura por padrões como #12345, pedido: 12345, etc.
        match = re.search(r'(?:pedido[\s#:]*|#)(\d+)', mensagem.lower())
        if match:
            pedido_id = match.group(1)
            debug_print(f"[DEBUG] ID encontrado via regex: '{pedido_id}'")
        else:
            debug_print("[DEBUG] Nenhum padrão de ID encontrado via regex")
            # Fallback: pega qualquer número na mensagem se 'pedido' estiver presente
            if 'pedido' in mensagem.lower():
                debug_print("[DEBUG] Palavra 'pedido' encontrada na mensagem")
                numeros = re.findall(r'\d+', mensagem)
                debug_print(f"[DEBUG] Números encontrados na mensagem: {numeros}")
                if numeros:
                    pedido_id = numeros[0]
                    debug_print(f"[DEBUG] ID selecionado dos números encontrados: '{pedido_id}'")
        
        if not pedido_id:
            debug_print("[DEBUG] Nenhum ID de pedido encontrado na mensagem")
            return None
            
        # Converte para string e remove espaços para comparação
        pedido_id = str(pedido_id).strip()
        debug_print(f"[DEBUG] ID do pedido após limpeza: '{pedido_id}'")
        
        # Recarrega pedidos para garantir dados atualizados
        debug_print("[DEBUG] Recarregando pedidos para busca")
        self.pedidos = load_pedidos()
        debug_print(f"[DEBUG] Total de pedidos carregados: {len(self.pedidos)}")
        
        if not self.pedidos:
            debug_print("[ERRO] Nenhum pedido disponível para busca!")
            return None
        
        for i, pedido in enumerate(self.pedidos):
            pedido_atual = str(pedido['pedido_id']).strip()
            debug_print(f"[DEBUG] Comparando pedido {i+1}:")
            debug_print(f"[DEBUG]   - ID do arquivo: '{pedido_atual}'")
            debug_print(f"[DEBUG]   - ID buscado: '{pedido_id}'")
            debug_print(f"[DEBUG]   - São iguais? {pedido_atual == pedido_id}")
            
            if pedido_atual == pedido_id:
                debug_print(f"[DEBUG] Pedido encontrado: {pedido}")
                return pedido
                
        debug_print(f"[DEBUG] Pedido {pedido_id} não encontrado na base")
        debug_print("[DEBUG] ===== FIM DA BUSCA DE PEDIDO =====\n")
        return None

    async def processar_mensagem(self, mensagem: str, contexto: Optional[Dict] = None) -> str:
        debug_print(f"\n[DEBUG] ===== INÍCIO DO PROCESSAMENTO DE MENSAGEM =====")
        debug_print(f"[DEBUG] Mensagem recebida: '{mensagem}'")
        
        try:
            # Checagem simples de prazo de troca
            resposta_troca = self.rag_system.checar_prazo_troca(mensagem)
            if resposta_troca:
                debug_print("[DEBUG] Resposta de troca encontrada")
                return resposta_troca

            # Consulta de pedidos (primeiro tenta buscar o pedido)
            if 'pedido' in mensagem.lower():
                debug_print(f"[DEBUG] Detectada consulta de pedido na mensagem")
                pedido = self._buscar_pedido(mensagem)
                debug_print(f"[DEBUG] Resultado da busca do pedido: {pedido}")
                
                if pedido:
                    try:
                        produtos = ', '.join([p['nome'] for p in pedido['produtos']])
                        resposta = f"Status do pedido {pedido['pedido_id']}: {pedido['status']}. Produtos: {produtos}. Data da compra: {pedido['data_compra']}. Previsão de entrega: {pedido['previsao_entrega']}."
                        debug_print(f"[DEBUG] Resposta formatada para pedido encontrado: {resposta}")
                        return resposta
                    except KeyError as e:
                        debug_print(f"[ERRO] Campo faltando no pedido: {e}")
                        debug_print(f"[DEBUG] Pedido com erro: {pedido}")
                        return "Desculpe, encontrei o pedido mas há informações faltando. Por favor, entre em contato com o suporte."
                elif re.search(r'\d+', mensagem):
                    debug_print("[DEBUG] Número de pedido encontrado mas pedido não localizado")
                    return "Desculpe, não encontrei esse pedido em nossa base. Verifique o número e tente novamente."
                else:
                    debug_print("[DEBUG] Consulta de pedido sem número específico")
                    return "Para consultar o status do seu pedido, por favor informe o número do pedido. Exemplo: 'Qual o status do pedido #12345?'"

            # Perguntas sobre produtos
            if any(keyword in mensagem.lower() for keyword in ['produto', 'produtos', 'notebook', 'smartphone', 'celular', 'computador', 'livro', 'tênis', 'panelas', 'cozinha', 'presente']):
                category = self._extract_category(mensagem)
                filters = {"category": category} if category else None
                produtos = await self.rag_system.search_products(mensagem, filters)
                if produtos:
                    produtos_info = []
                    for i, p in enumerate(produtos):
                        # Formata as especificações em uma string legível
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
            
        except Exception as e:
            # Log the error and return a graceful error message
            debug_print(f"Error processing message: {str(e)}")
            return "Desculpe, tive um problema ao processar sua mensagem. Por favor, tente novamente em alguns instantes."

    def get_chat_history(self) -> List[Dict]:
        """Return the chat history."""
        return self.chat_history

    def clear_chat_history(self):
        """Clear the chat history."""
        self.chat_history = [] 
