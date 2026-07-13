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

## Dados públicos do SIGAA

Na página de detalhe da disciplina, a seção `Dados públicos do SIGAA` permite buscar componentes curriculares por código ou nome e associar o resultado à disciplina cadastrada.

A busca usa o backend em `GET /api/sigaa/components/search?query=...` e a associação usa `PATCH /api/disciplines/{id}/sigaa-component`. Se a busca falhar ou não encontrar dados, a tela mostra mensagem amigável e mantém os dados cadastrados manualmente.

Quando ementa ou programa atual não vierem da fonte pública, a interface mostra que esses dados não estão disponíveis na fonte consultada. A chave `GOOGLE_API_KEY` não é usada nem exposta no frontend.


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

- Autenticação restrita ao usuário configurado no backend; cadastro público desabilitado.
- Sem calendário nesta etapa.
- Importações de documentos sempre exigem revisão humana antes da persistência.
- Agente disponível via backend; sem `GOOGLE_API_KEY`, usa fallback por regras.
- Consulta SIGAA limitada à fonte pública de componentes curriculares, via backend.
- Dados acadêmicos persistem no banco configurado por `DATABASE_URL`.

## Rotas públicas e sessão

- `/` é a landing page pública do EstudaUnB.
- `/login` autentica com o usuário de demonstração configurado no backend.
- `/register` valida o formulário somente no navegador e informa que o cadastro público está indisponível; não chama API nem persiste credenciais.
- `/app`, `/disciplines`, `/study-plan` e `/matricula-import` são rotas protegidas.

Use `ALLOW_REGISTRATION=false` no backend. O usuário de demonstração é criado por `EMAIL_TESTE` e `SENHA_TESTE`; não inclua os valores reais em código, HTML, logs ou documentação.
