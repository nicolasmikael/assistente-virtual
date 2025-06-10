import asyncio

def test_order_status(assistant):
    response = asyncio.run(assistant.processar_mensagem('Qual o status do pedido #12345?'))
    assert 'Status do pedido 12345' in response
    assert 'Em trânsito' in response
