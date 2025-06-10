import asyncio

def test_product_search(assistant):
    results = asyncio.run(assistant.rag_system.search_products('notebook'))
    assert any('Notebook' in p['nome'] for p in results)
