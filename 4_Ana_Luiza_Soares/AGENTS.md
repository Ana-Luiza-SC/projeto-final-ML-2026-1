# AGENTS.md

## Contexto do projeto

Este projeto é o EstudaUnB, uma plataforma para auxiliar estudantes da Universidade de Brasília na organização dos estudos.

O sistema deve permitir que o estudante:
- importe disciplinas a partir de um PDF de atestado de matrícula do SIGAA;
- cadastre disciplinas manualmente como fallback;
- visualize informações da disciplina;
- registre conteúdos a estudar;
- registre avaliações, pesos e notas;
- calcule média atual, nota necessária e cenários de desempenho;
- receba recomendações de estudo geradas por um agente de IA.

O projeto é para uma disciplina de Machine Learning/Agentes de IA. O escopo precisa ser pequeno, funcional, auditável e entregável até 13/07/2026.

## Prioridade de implementação

1. Backend funcional com FastAPI.
2. Cadastro manual de disciplinas.
3. Importação de disciplinas via parsing de PDF.
4. Cálculo de notas e nota necessária.
5. Página simples de disciplinas/conteúdos/notas.
6. Agente de IA para recomendação de dedicação.
7. Guardrails, fallback e logs.
8. Docker e documentação.

Não implementar funcionalidades fora do MVP sem necessidade.

## Regras de escopo

Fazer:
- parsing de PDF enviado pelo usuário;
- scraping apenas de páginas públicas do SIGAA;
- fallback manual quando parsing ou scraping falhar;
- respostas claras e auditáveis;
- logs de latência, erro e fallback;
- código simples e testável.

Não fazer:
- login no SIGAA;
- scraping de páginas autenticadas;
- armazenamento do PDF bruto por padrão;
- histórico de reprovação por professor;
- calendário complexo mensal/diário no primeiro MVP;
- integração com Google Calendar;
- modelo preditivo complexo sem necessidade.

## Regras de segurança e privacidade

- Não solicitar senha do SIGAA.
- Não acessar páginas autenticadas.
- Não armazenar dados sensíveis desnecessários.
- O PDF de matrícula deve ser processado e descartado, salvo se o usuário permitir explicitamente.
- Dados pessoais do estudante não devem aparecer em logs.
- Se o sistema não conseguir extrair dados do PDF, deve retornar erro amigável e permitir cadastro manual.

## Regras do agente de IA

O agente deve:
- classificar dedicação recomendada: baixa, média ou alta;
- justificar a recomendação com evidências;
- usar apenas dados fornecidos pelo usuário ou obtidos de fonte pública;
- não inventar ementa, professor, nota ou taxa de reprovação;
- informar quando uma informação não foi encontrada;
- recomendar ações de estudo específicas.

O agente não deve:
- afirmar taxa de reprovação sem fonte;
- classificar professor como fácil/difícil;
- dar diagnóstico psicológico ou médico;
- gerar recomendação sem evidência mínima.

## Stack sugerida

Backend:
- Python
- FastAPI
- Pydantic
- pdfplumber ou PyMuPDF
- BeautifulSoup/requests
- SQLite ou PostgreSQL

Frontend:
- React + Vite
- TypeScript
- Tailwind, se já estiver configurado
- calendário simples semanal, se couber

Infra:
- Docker
- docker-compose

## Comandos esperados

Antes de finalizar qualquer tarefa, tente rodar:

```bash
cd backend && pytest
cd frontend && npm run build
docker compose up --build
```

Se algum comando não existir ainda, criar scripts mínimos ou documentar a ausência.

## Estilo de código

- Preferir código simples, modular e legível.
- Separar parsing, scraping, cálculo de notas e agente em módulos diferentes.
- Criar testes para funções determinísticas.
- Não esconder erros técnicos no backend, mas retornar mensagens amigáveis para o frontend.
- Não usar mocks silenciosos sem identificar claramente no código.


## Entregáveis do trabalho

O sistema precisa demonstrar:

- problema real;
- dados/contexto com fonte clara;
- agente construído;
- API;
- produto utilizável;
- guardrails;
- fallback;
- avaliação;
- logs/monitoramento;
- relatório.

## Regras acadêmicas da UnB

- A UnB usa menções SS, MS, MM, MI, II e SR.
- Menções de aprovação: SS, MS e MM.
- Menções de reprovação: MI, II e SR.
- Frequência mínima exigida: 75%.
- Faltas acima de 25% indicam risco grave ou reprovação por falta.
- O sistema deve alertar risco por falta mesmo quando a nota estiver boa.
- O sistema não deve afirmar aprovação final se a frequência for desconhecida.

## Regras de cálculo acadêmico

- O sistema deve demonstrar o ciclo agente → API → produto.
- Cálculo de nota, menção e frequência deve ser determinístico.
- O agente de IA deve explicar e recomendar usando esses cálculos como contexto.
- O agente de IA não deve calcular livremente nota, menção ou frequência.
