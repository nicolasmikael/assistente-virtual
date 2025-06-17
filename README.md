# Codex - Sistema de Assistente Virtual com RAG

Este projeto implementa um sistema de assistente virtual inteligente utilizando técnicas de RAG (Retrieval-Augmented Generation) para fornecer respostas precisas e contextualizadas sobre pedidos e produtos.

## Funcionalidades

- Processamento de consultas em linguagem natural
- Sistema RAG para recuperação de informações relevantes
- API REST para integração com outros sistemas
- Suporte a múltiplos formatos de dados
- Processamento assíncrono de consultas
- Sistema de cache para otimização de performance

## Tecnologias Utilizadas

- Python 3.8+
- FastAPI
- LangChain
- OpenAI GPT
- FAISS (Facebook AI Similarity Search)
- Pandas
- Uvicorn

## Pré-requisitos

- Python 3.8 ou superior
- pip (gerenciador de pacotes Python)
- Ambiente virtual Python (recomendado)

## Instalação

1. Clone o repositório:

```bash
git clone [URL_DO_REPOSITÓRIO]
cd codex-test
```

2. Crie e ative um ambiente virtual:

```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. Instale as dependências:

```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente:
   Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```
OPENAI_API_KEY=sua_chave_api
```

## Estrutura do Projeto

```
codex-test/
├── data/               # Diretório para armazenamento de dados
├── deploy/            # Scripts e configurações de deploy
├── src/               # Código fonte principal
│   ├── api.py         # Implementação da API REST
│   ├── assistente.py  # Lógica principal do assistente
│   ├── rag_system.py  # Sistema RAG
│   ├── prompts.py     # Templates de prompts
│   └── static/        # Arquivos estáticos
├── tests/             # Testes automatizados
├── requirements.txt   # Dependências do projeto
└── README.md         # Documentação
```

## Uso

1. Inicie o servidor:

```bash
uvicorn src.api:app --reload
```

2. A API estará disponível em `http://localhost:8000`

3. Endpoints disponíveis:

- `POST /chat`: Envia uma mensagem para o assistente
- `GET /health`: Verifica o status do servidor

## Documentação da API

### POST /chat

Envia uma mensagem para o assistente e recebe uma resposta.

**Request Body:**

```json
{
  "message": "Qual é o status do pedido 123?",
  "session_id": "optional_session_id"
}
```

**Response:**

```json
{
  "response": "Resposta do assistente",
  "session_id": "session_id"
}
```

## Testes

Para executar os testes:

```bash
pip install -r requirements-dev.txt
pytest
```

## Fluxo de Trabalho

1. O usuário envia uma consulta através da API
2. O sistema RAG processa a consulta e recupera informações relevantes
3. O assistente gera uma resposta contextualizada
4. A resposta é retornada ao usuário

## Autores

- Nícolas Mikael - _Desenvolvimento Inicial_

## Agradecimentos

- OpenAI pelo modelo GPT
- Comunidade LangChain
