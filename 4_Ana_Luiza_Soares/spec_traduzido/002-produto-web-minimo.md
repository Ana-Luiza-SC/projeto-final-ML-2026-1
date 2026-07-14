# Spec 002 — Produto Web Mínimo EstudaUnB

> Idioma: Português do Brasil
> Fonte canônica: [../specs/002-produto-web-minimo.md](../specs/002-produto-web-minimo.md)
> Status da tradução: sincronizada
> Última sincronização: 2026-07-13

## 1. Título

Produto Web Mínimo do EstudaUnB — Interface para demonstrar API + produto.

## 2. Objetivo

Criar um frontend web simples que consuma a API FastAPI já existente e permita demonstrar o fluxo principal do EstudaUnB: verificar a API, cadastrar disciplina manualmente, registrar faltas, cadastrar avaliações e consultar a simulação acadêmica por menção e frequência.

Esta fatia deve preparar a demonstração do ciclo agente → API → produto sem implementar o agente de IA ainda. A interface deve expor os cálculos determinísticos produzidos pelo backend e preservar os guardrails acadêmicos da UnB.

## 3. Problema que esta fatia resolve

A primeira fatia entregou a API, mas ainda não há produto navegável para um estudante ou avaliador usar. Esta spec resolve a lacuna de demonstração criando uma interface mínima para operar o backend e visualizar, de forma clara, média parcial, nota necessária, menção, frequência, riscos e warnings.

## 4. Escopo

Implementar apenas o frontend web mínimo para:

- Ver status da API usando `GET /api/health`.
- Cadastrar disciplina manualmente.
- Listar disciplinas cadastradas.
- Abrir detalhe de uma disciplina.
- Atualizar faltas/frequência da disciplina.
- Cadastrar avaliação com nome, peso e nota.
- Consultar simulação acadêmica da disciplina.
- Exibir média parcial, contribuição atual, peso concluído, peso restante, nota necessária, menção atual/projetada, risco por nota, frequência, risco por falta, situação acadêmica resumida e warnings.
- Usar o termo "menção" com destaque, pois a UnB trabalha com SS, MS, MM, MI, II e SR.
- Consumir a documentação Swagger/OpenAPI do backend durante desenvolvimento.

Stack sugerida:

- React + Vite + TypeScript.
- CSS simples ou Tailwind, se já estiver configurado.
- `fetch` ou `axios` para chamadas HTTP.
- Sem biblioteca pesada de calendário nesta etapa.

## 5. Fora do escopo

- Login ou autenticação.
- Calendário.
- Upload de PDF.
- Parsing real de PDF.
- LLM ou agente de recomendação.
- Scraping real do SIGAA.
- Edição avançada de disciplinas.
- Persistência frontend complexa.
- Dashboard analítico.
- Avaliação de professor como fácil ou difícil.
- Afirmação de aprovação final quando a frequência estiver desconhecida.

## 6. Fluxo do usuário

1. Usuário abre a Home.
2. Home mostra nome do projeto, descrição curta e status da API.
3. Usuário acessa Disciplinas.
4. Usuário cadastra uma disciplina manualmente.
5. A disciplina aparece na lista.
6. Usuário abre o detalhe da disciplina.
7. Usuário informa total de aulas/horas e faltas.
8. Usuário cadastra uma avaliação com nome, peso e nota.
9. Usuário consulta a simulação acadêmica.
10. Interface mostra menção, nota necessária, frequência, riscos e warnings.
11. Se faltarem dados, a interface mostra que a simulação está incompleta, sem afirmar aprovação final.

## 7. Telas necessárias

### Home

- Nome do projeto: EstudaUnB.
- Descrição curta do objetivo.
- Status da API com estado visual simples: online, offline ou verificando.
- Botão/link para a tela de Disciplinas.
- Link opcional para a documentação local da API em `http://localhost:8000/docs`.

### Disciplinas

- Lista de disciplinas cadastradas.
- Formulário de cadastro manual com campos mínimos:
  - código;
  - nome;
  - professor;
  - turma;
  - código de horário;
  - local;
  - total de aulas;
  - faltas.
- Mensagem amigável se a API falhar.
- Estado vazio quando não houver disciplinas.
- Ação para abrir o detalhe de uma disciplina.

### Detalhe da disciplina

- Dados básicos da disciplina.
- Formulário de frequência/faltas:
  - total de aulas;
  - faltas;
  - ou total de horas-aula;
  - horas-aula perdidas.
- Formulário de avaliação:
  - nome;
  - peso;
  - nota;
  - data opcional;
  - tópicos opcionais.
- Painel de simulação acadêmica com:
  - média parcial;
  - contribuição atual;
  - peso concluído;
  - peso restante;
  - nota necessária;
  - menção atual;
  - menção projetada;
  - risco por nota;
  - frequência;
  - risco por falta;
  - situação acadêmica resumida;
  - warnings.

## 8. Contratos com a API existente

Base URL local sugerida: `http://localhost:8000`.

A documentação interativa do backend deve estar disponível em:

- Swagger UI: `GET /docs`.
- ReDoc: `GET /redoc`.
- OpenAPI JSON: `GET /openapi.json`.

A aplicação FastAPI deve expor metadados OpenAPI:

- `title`: `EstudaUnB API`.
- `description`: `API para organização acadêmica de estudantes da UnB, com cadastro de disciplinas, avaliações, faltas e simulação por menção/frequência.`
- `version`: `0.1.0`.

Tags esperadas no OpenAPI:

- `health`;
- `disciplines`;
- `assessments`;
- `attendance`;
- `academic-simulation`.

Endpoints consumidos pela interface:

### `GET /api/health`

Verifica se a API está disponível.

Resposta esperada:

```json
{
  "status": "ok"
}
```

### `POST /api/disciplines`

Cria disciplina manualmente.

Payload exemplo:

```json
{
  "code": "FGA0000",
  "name": "Disciplina de Exemplo",
  "professor": "Docente",
  "class_code": "01",
  "schedule_code": "24M12",
  "local": "Sala 1",
  "total_classes": 30,
  "missed_classes": 2
}
```

### `GET /api/disciplines`

Lista disciplinas cadastradas.

### `GET /api/disciplines/{id}`

Retorna os dados de uma disciplina.

Erro esperado:

- `404`: disciplina não encontrada.

### `PATCH /api/disciplines/{id}/attendance`

Atualiza frequência/faltas.

Payload exemplo:

```json
{
  "total_classes": 30,
  "missed_classes": 4,
  "total_class_hours": null,
  "missed_class_hours": null
}
```

Erros esperados:

- `404`: disciplina não encontrada.
- `400`: faltas maiores que total de aulas/horas.

### `POST /api/disciplines/{id}/assessments`

Cadastra avaliação.

Payload exemplo:

```json
{
  "name": "Prova 1",
  "weight": 30,
  "grade": 8.0,
  "topics": ["Introdução", "Exercícios"]
}
```

Erros esperados:

- `404`: disciplina não encontrada.
- `422` ou `400`: nota fora do intervalo 0 a 10.
- `422` ou `400`: peso inválido.

### `GET /api/disciplines/{id}/academic-simulation?target_average=5.0`

Retorna simulação acadêmica.

A interface deve tratar:

- dados insuficientes para simulação;
- frequência desconhecida;
- meta inalcançável apenas com avaliações restantes;
- risco por falta mesmo quando a nota estiver boa.

## 9. Estados de erro e fallback

- API offline: mostrar mensagem amigável e permitir nova tentativa.
- Falha ao cadastrar disciplina: manter formulário preenchido e mostrar erro genérico legível.
- Disciplina não encontrada: voltar para lista e mostrar aviso.
- Nota inválida: orientar que a nota deve estar entre 0 e 10.
- Peso inválido: orientar que peso pode ser decimal ou porcentagem válida.
- Faltas maiores que total: orientar correção do total ou das faltas.
- Simulação sem avaliações: mostrar que faltam avaliações/notas.
- Frequência desconhecida: mostrar que não é possível afirmar aprovação final.
- Erro técnico inesperado: não mostrar stack trace; exibir mensagem amigável.

## 10. Critérios de aceite

- A spec existe em `specs/002-produto-web-minimo.md`.
- A spec 001 não foi alterada por esta tarefa.
- A fatia descrita é pequena, implementável e limitada ao frontend mínimo, com exceção dos ajustes de Swagger/OpenAPI no backend.
- Home mostra status da API usando `GET /api/health`.
- Usuário consegue cadastrar disciplina manualmente.
- Usuário consegue listar e abrir disciplinas.
- Usuário consegue atualizar faltas/frequência.
- Usuário consegue cadastrar avaliação.
- Usuário consegue consultar e visualizar simulação acadêmica.
- Interface exibe menção, frequência, riscos e warnings.
- Interface não afirma aprovação final quando a frequência estiver desconhecida.
- Erros da API são apresentados de forma amigável.
- Guardrails do projeto são preservados.
- Swagger UI, ReDoc e OpenAPI JSON seguem disponíveis para consulta local.

## 11. Testes esperados

Frontend:

- Testar renderização da Home com status da API online.
- Testar estado de API offline com mensagem amigável.
- Testar cadastro manual de disciplina.
- Testar listagem de disciplinas.
- Testar abertura do detalhe de disciplina.
- Testar atualização de faltas/frequência.
- Testar cadastro de avaliação.
- Testar renderização do painel de simulação acadêmica.
- Testar que frequência desconhecida não mostra aprovação final.
- Testar que warnings são exibidos.

Backend/OpenAPI:

- `GET /docs` retorna 200 ou HTML válido.
- `GET /openapi.json` retorna 200.
- O schema OpenAPI contém o título `EstudaUnB API`.
- O schema OpenAPI contém tags para health, disciplines, assessments, attendance e academic-simulation.

## 12. Próximos passos após esta spec

1. Criar frontend React + Vite + TypeScript.
2. Configurar URL da API por variável de ambiente.
3. Implementar cliente HTTP simples para os endpoints existentes.
4. Implementar telas Home, Disciplinas e Detalhe da disciplina.
5. Adicionar testes do frontend.
6. Depois da demonstração API + produto, planejar importação de PDF com fixture anonimizada.
7. Em fatia futura, implementar o agente de recomendação usando os cálculos determinísticos como contexto.
