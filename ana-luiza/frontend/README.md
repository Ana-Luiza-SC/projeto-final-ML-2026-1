# Frontend EstudaUnB

Frontend mínimo em React + Vite + TypeScript para demonstrar o fluxo principal do EstudaUnB.

## Instalar dependências

```bash
cd frontend
npm install
```

## Configurar API

Por padrão, o frontend usa:

```bash
http://localhost:8000
```

Para alterar, crie `frontend/.env`:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## Rodar frontend

```bash
npm run dev
```

Acesse: http://localhost:5173

## Rodar backend junto

Em outro terminal:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

Swagger: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc

## Fluxo de demonstração

1. Abrir a Home e verificar o status da API.
2. Ir para Disciplinas.
3. Cadastrar uma disciplina manualmente.
4. Abrir o detalhe da disciplina.
5. Informar faltas/frequência.
6. Cadastrar uma avaliação com peso e nota.
7. Consultar a simulação acadêmica.

## Limitações

- Sem login.
- Sem calendário.
- Sem upload ou parsing de PDF.
- Sem LLM.
- Sem scraping SIGAA.
- Dados do backend ficam em memória nesta etapa.
