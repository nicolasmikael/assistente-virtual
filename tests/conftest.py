import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import pytest
import types
sys.modules.setdefault("langchain_openai", types.SimpleNamespace(ChatOpenAI=object, OpenAIEmbeddings=object))
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda *a, **k: None))
sys.modules.setdefault('langchain.prompts', types.SimpleNamespace(ChatPromptTemplate=type('CPT',(object,),{'from_messages':staticmethod(lambda msgs: type('X',(object,),{'format_messages':lambda self: msgs})())})))
langchain_mod=types.ModuleType('langchain'); langchain_mod.__path__=[]; sys.modules['langchain']=langchain_mod
sys.modules.setdefault("langchain.text_splitter", types.SimpleNamespace(RecursiveCharacterTextSplitter=object))
sys.modules.setdefault("langchain_community.vectorstores", types.SimpleNamespace(FAISS=object))
sys.modules.setdefault("numpy", types.ModuleType("numpy"))
sys.modules.setdefault("langchain.schema", types.SimpleNamespace(HumanMessage=type("HM",(object,),{"__init__":lambda self,*a,**k:None}), SystemMessage=type("SM",(object,),{"__init__":lambda self,*a,**k:None})))
import json

class DummyLLM:
    def __init__(self, *args, **kwargs):
        pass
    async def agenerate(self, *args, **kwargs):
        class Gen:
            text = "dummy"
        class Result:
            generations = [[Gen()]]
        return Result()

class DummyRAG:
    async def search_products(self, query, filters=None):
        with open('data/produtos.json', 'r', encoding='utf-8') as f:
            products = json.load(f)
        results = []
        for p in products:
            if 'notebook' in query.lower() and 'notebook' in p['nome'].lower():
                results.append(p)
        return results

    async def query_knowledge_base(self, query):
        return ["Você tem até 7 dias corridos para solicitar a troca de produtos não perecíveis"]

@pytest.fixture
def assistant(monkeypatch):
    import assistente as assistente_module
    monkeypatch.setattr(assistente_module, 'ChatOpenAI', lambda *a, **k: DummyLLM())
    monkeypatch.setattr(assistente_module, 'RAGSystem', lambda: DummyRAG())
    return assistente_module.AssistenteVirtual()
