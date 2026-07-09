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

## Rodar com Docker

Na raiz do projeto:

```bash
docker compose up --build
```

O frontend é servido por nginx em:

```bash
http://localhost:5173
```

No Docker Compose, `VITE_API_BASE_URL` usa `http://localhost:8000`, porque o navegador acessa a API pela porta publicada do host. O frontend não recebe `GOOGLE_API_KEY`; essa chave é exclusiva do backend e é opcional.

## Rodar backend junto

Em outro terminal:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

Swagger: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc

## Painel de recomendação

No detalhe da disciplina, informe opcionalmente:

- objetivo da semana;
- conteúdos pendentes com título, dificuldade e status.

Depois clique em `Gerar recomendação de estudo`. O backend funciona sem `GOOGLE_API_KEY` usando fallback por regras. Quando fallback for usado, o painel mostra um aviso. A recomendação é uma simulação e não substitui o resultado oficial do SIGAA.

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
- Agente disponível via backend; sem `GOOGLE_API_KEY`, usa fallback por regras.
- Sem scraping SIGAA.
- Dados do backend ficam em memória nesta etapa.
