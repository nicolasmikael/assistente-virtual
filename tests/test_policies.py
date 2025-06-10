import asyncio

def test_policy_query(assistant, monkeypatch):
    called = {}
    async def fake_query(msg):
        called['q'] = msg
        return ['sample policy']
    monkeypatch.setattr(assistant.rag_system, 'query_knowledge_base', fake_query)
    response = asyncio.run(assistant.processar_mensagem('Qual é a política de trocas?'))
    assert called['q'] == 'Qual é a política de trocas?'
    assert 'dummy' in response
