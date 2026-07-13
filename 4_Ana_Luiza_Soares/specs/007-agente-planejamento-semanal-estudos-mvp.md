# Spec 007 — Agente de Planejamento Semanal de Estudos — MVP

## 1. Título

Agente de Planejamento Semanal de Estudos do EstudaUnB — MVP.

## 2. Objetivo

Especificar a próxima fatia do EstudaUnB: transformar disciplinas já cadastradas em um plano semanal de estudos acionável, determinístico, auditável e seguro.

O sistema deve receber as disciplinas selecionadas pelo estudante, sua disponibilidade semanal, limites de sessão, prioridades opcionais e um objetivo textual curto. A partir disso, o backend deve montar um plano-base determinístico, opcionalmente explicar e refinar a apresentação com ajuda de LLM, validar a saída e devolver uma resposta estruturada para o frontend.

O agente não deve criar disciplinas, horários fictícios ou alterar a estrutura do plano fora das regras determinísticas.

## 3. Problema que esta fatia resolve

O EstudaUnB já permite cadastrar disciplinas manualmente e via SIGAA público, mas ainda não transforma esse conjunto em uma rotina semanal de estudo utilizável.

Hoje o estudante precisa organizar sozinho:

- quais disciplinas estudar primeiro;
- quanto tempo dedicar por disciplina;
- como distribuir o tempo disponível ao longo da semana;
- como lidar com disponibilidade parcial ou irregular;
- como interpretar o plano em caso de ausência de LLM.

Esta fatia resolve essa lacuna com um planejador semanal que usa regras explícitas para distribuir tempo, respeita a disponibilidade informada e mantém um fallback funcional sem LLM.

## 4. Contexto do produto

Esta spec assume o estado atual do produto:

- o cadastro manual de disciplinas já funciona;
- a busca pública de componentes do SIGAA já funciona;
- a listagem de disciplinas cadastradas já existe;
- o frontend já possui navegação simples em React + Vite + TypeScript;
- o backend já é FastAPI e expõe o armazenamento em memória das disciplinas;
- o agente de recomendação de estudos existente não deve ser reescrito nem contradito;
- a integração SIGAA Componentes não deve ser reespecificada nesta fatia.

O novo planejador deve reaproveitar os dados já cadastrados e não introduzir dependências pesadas, banco novo ou framework agentístico complexo.

## 5. Escopo

Esta fatia deve especificar a futura implementação de:

- um endpoint para gerar plano semanal de estudos;
- validação tipada da entrada;
- consulta às disciplinas cadastradas como fonte de verdade;
- orquestração explícita entre ferramentas internas;
- algoritmo determinístico de alocação de tempo;
- explicação opcional assistida por LLM;
- validação programática da saída;
- fallback determinístico quando o LLM não estiver disponível;
- frontend mínimo para montar e visualizar o plano;
- logs estruturados sem dados sensíveis.

### Entrada principal esperada

A entrada deve representar, no mínimo:

- lista de IDs das disciplinas selecionadas;
- disponibilidade semanal;
- dias disponíveis;
- janelas horárias opcionais;
- duração máxima por sessão;
- prioridades opcionais por disciplina;
- objetivo textual opcional.

### Saída principal esperada

A resposta deve ser estruturada e conter, no mínimo:

- `status`;
- `source`;
- `plan`;
- `summary`;
- `warnings`;
- `metrics`;
- `request_id`.

## 6. Fora do escopo

Não fazer nesta fatia:

- login no SIGAA;
- scraping autenticado;
- importação de PDF;
- calendário mensal ou diário completo;
- integração com Google Calendar;
- persistência do plano semanal por padrão;
- histórico de versões do plano;
- criação de um modelo preditivo;
- uso obrigatório de LLM;
- alteração da integração SIGAA existente;
- alteração dos cálculos determinísticos acadêmicos já implementados;
- redesign completo do frontend.

## 7. Fontes de dados e regras de entrada

### Fontes de dados permitidas

O planejador pode usar apenas:

- disciplinas cadastradas pelo usuário;
- disponibilidade informada pelo usuário;
- prioridades informadas pelo usuário;
- objetivo textual curto do usuário;
- dados acadêmicos já disponíveis no sistema, quando úteis como contexto;
- resposta do LLM, apenas para explicação ou reformulação, nunca para alterar o plano estrutural.

### Fontes proibidas

O planejador não pode usar:

- disciplinas não cadastradas;
- dados externos não validados;
- horários inventados;
- avaliação de professor;
- taxa de reprovação por professor;
- informações pessoais desnecessárias;
- raciocínio interno detalhado em logs ou respostas.

### Regra sobre texto livre

O texto livre do usuário é apenas um contexto auxiliar.

Ele não pode:

- criar disciplina inexistente;
- adicionar disciplina não selecionada;
- alterar a lista de disciplinas escolhidas;
- inventar disponibilidade;
- inventar horários reais.

Se o texto citar uma disciplina não selecionada, a citação deve ser ignorada e sinalizada em warning apropriado.

### Regra sobre horas semanais e janelas

Quando `time_windows` estiver presente:

- as janelas são a fonte de verdade para a alocação real;
- `available_hours_per_week` serve como verificação de consistência;
- se a soma das janelas ultrapassar muito o total semanal informado, a entrada deve ser rejeitada;
- se a soma das janelas for menor, o backend pode usar o menor valor como teto real de planejamento, mas deve registrar warning de inconsistência;
- nunca assumir horários fora das janelas para compensar a diferença.

Quando `time_windows` não estiver presente:

- `available_hours_per_week` continua válido como teto total;
- o plano deve ser representado por dia, sequência e duração, sem horário real;
- não inventar `start_time` ou `end_time`.

## 8. Contrato da API

### Endpoint principal

```http
POST /api/study-plans/generate
```

### Entrada esperada

Exemplo conceitual:

```json
{
  "discipline_ids": [
    "uuid-da-disciplina-1",
    "uuid-da-disciplina-2"
  ],
  "availability": {
    "available_hours_per_week": 12,
    "days_available": ["monday", "tuesday", "thursday"],
    "time_windows": [
      {
        "day": "monday",
        "start_time": "18:00",
        "end_time": "20:00"
      },
      {
        "day": "tuesday",
        "start_time": "19:00",
        "end_time": "21:30"
      }
    ]
  },
  "max_session_minutes": 90,
  "priorities": [
    {
      "discipline_id": "uuid-da-disciplina-1",
      "priority": 5
    },
    {
      "discipline_id": "uuid-da-disciplina-2",
      "priority": 2
    }
  ],
  "objective_text": "quero revisar para a prova da próxima semana"
}
```

### Saída de sucesso

Exemplo conceitual:

```json
{
  "status": "success",
  "source": "deterministic_fallback",
  "plan": [
    {
      "day": "monday",
      "sequence": 1,
      "discipline_id": "uuid-da-disciplina-1",
      "discipline_code": "FGA0124",
      "discipline_name": "Projeto de Algoritmos",
      "duration_minutes": 90,
      "activity": "Revisão guiada e resolução de exercícios",
      "start_time": "18:00",
      "end_time": "19:30"
    }
  ],
  "summary": "Plano semanal montado com distribuição determinística e prioridade maior para a disciplina com maior peso informado.",
  "warnings": [
    "Uma das disciplinas selecionadas recebeu menos tempo do que o desejado devido à disponibilidade limitada."
  ],
  "metrics": {
    "requested_minutes": 720,
    "allocated_minutes": 720,
    "unallocated_minutes": 0,
    "session_count": 6,
    "discipline_count": 2
  },
  "request_id": "uuid-ou-trace-id"
}
```

### Regras de resposta

- `status` deve ser `success` nas respostas válidas.
- `source` deve ser `llm_assisted` quando o LLM contribuir apenas na explicação validada.
- `source` deve ser `deterministic_fallback` quando o LLM não estiver disponível, falhar ou for rejeitado pelos guardrails.
- `plan` deve ser sempre estruturado.
- `warnings` não devem ser usados como campo de erro silencioso.
- `metrics` devem permitir auditoria do tamanho do plano e da cobertura da disponibilidade.
- `request_id` deve ser gerado por requisição.

### Respostas de erro

Erros de validação devem seguir o padrão do framework já usado no backend, com mensagens amigáveis e sem stack trace.

Erros esperados:

- `422` para entrada inválida;
- `404` para disciplina inexistente;
- `400` para pedido fora do escopo;
- `500` sanitizado para erro interno irrecuperável.

## 9. Modelo do plano semanal

O plano retornado deve ser simples, explícito e renderizável pelo frontend sem interpretação de texto livre.

Cada item do plano deve conter:

- `day`;
- `sequence`;
- `discipline_id`;
- `discipline_code`;
- `discipline_name`;
- `duration_minutes`;
- `activity`;
- `start_time` opcional;
- `end_time` opcional.

### Regra sobre horários

Uma entrada contendo apenas dias disponíveis e horas semanais não é suficiente para inventar `start_time`.

Quando houver janelas horárias reais, o planner pode preencher `start_time` e `end_time`.

Quando não houver janelas:

- o plano deve ser representado por dia, sequência e duração;
- o frontend deve exibir a sessão sem horário real;
- o backend não deve inventar `08:00`, `19:00` ou qualquer outro horário arbitrário.

### Regra sobre disponibilidade insuficiente

Se a disponibilidade não permitir nem uma sessão mínima válida, o backend deve recusar a entrada com erro amigável, em vez de criar uma sessão de duração zero.

Se houver tempo suficiente para pelo menos uma sessão, mas não para cobrir todas as disciplinas, o sistema deve:

- priorizar de forma determinística;
- retornar warnings claros;
- informar quais disciplinas ficaram com tempo insuficiente ou sem tempo.

## 10. Algoritmo determinístico

O plano-base deve ser produzido por algoritmo determinístico e reproduzível.

### Estratégia mínima

1. Validar entrada.
2. Consultar as disciplinas cadastradas.
3. Rejeitar IDs inexistentes.
4. Normalizar a disponibilidade em minutos.
5. Arredondar a disponibilidade para blocos de 30 minutos.
6. Calcular peso explícito por disciplina.
7. Reservar um bloco mínimo por disciplina quando houver tempo suficiente.
8. Distribuir o tempo restante proporcionalmente aos pesos.
9. Resolver restos de divisão com desempate estável.
10. Dividir o tempo em sessões que não ultrapassem `max_session_minutes`.
11. Distribuir sessões apenas pelos dias permitidos.
12. Respeitar janelas diárias quando existirem.
13. Não ultrapassar o total disponível.
14. Nunca retornar duração zero ou negativa.

### Peso de prioridade

A prioridade opcional deve ser representada por um valor explícito e finito.

Para o MVP, a representação recomendada é:

- inteiro de `1` a `5`;
- `5` representa maior prioridade;
- se ausente, assumir prioridade neutra.

### Distribuição determinística

O algoritmo deve usar desempate estável, nesta ordem:

1. maior prioridade;
2. maior necessidade contextual, se houver;
3. código da disciplina;
4. ID da disciplina.

### Regras de alocação

- Se houver minutos suficientes para todas as disciplinas, cada uma recebe ao menos um bloco mínimo.
- Se não houver minutos suficientes, disciplinas de maior prioridade recebem cobertura antes das demais.
- Se restarem minutos após a cobertura mínima, o excedente é distribuído por proporcionalidade.
- Remainders devem ser resolvidos sempre pelo mesmo critério.

### Regras de tempo real

Quando janelas horárias forem fornecidas:

- preencher o plano dentro das janelas;
- quebrar sessões apenas se necessário;
- não ultrapassar início e fim de janela;
- não cruzar dias não permitidos.

Quando janelas não forem fornecidas:

- não inventar horário real;
- exibir apenas a ordem da sessão e a duração;
- manter o plano por dia de forma legível.

## 11. Ferramentas internas do agente

O planejador deve ser orquestrado por funções pequenas, explícitas e testáveis.

As responsabilidades mínimas são equivalentes a:

- listar disciplinas cadastradas;
- montar o plano-base;
- validar o plano montado;
- gerar explicação curta do plano.

Essas funções devem:

- ter responsabilidade única;
- aceitar entrada tipada;
- devolver saída tipada;
- registrar erros explicitamente;
- não depender de LLM para o núcleo determinístico.

Não usar framework agentístico pesado para encobrir essa orquestração.

## 12. Orquestração do agente

Fluxo esperado:

1. validar entrada;
2. consultar disciplinas cadastradas;
3. recusar IDs inexistentes;
4. montar o plano determinístico;
5. validar o plano determinístico;
6. chamar o LLM apenas para explicar ou resumir;
7. validar a saída do LLM;
8. combinar explicação validada com o plano-base;
9. retornar a resposta estruturada;
10. usar fallback determinístico quando o LLM falhar.

### Papel do LLM

O LLM pode apenas:

- explicar a distribuição de forma curta;
- interpretar o objetivo textual;
- sugerir foco semanal em linguagem natural;
- destacar limitações já verificadas;
- produzir uma justificativa legível.

O LLM não pode:

- criar disciplinas novas;
- alterar dias;
- alterar duração;
- alterar prioridade estrutural;
- criar horários fictícios;
- contradizer o plano-base;
- decidir o que já foi validado deterministicamente.

### Resultado da orquestração

O backend deve sempre ter o plano determinístico como fonte de verdade.

Se a explicação do LLM for inválida, a resposta deve cair para fallback determinístico sem alterar a estrutura do plano.

## 13. Fallback baseado em regras

O fallback deve ser determinístico e retornar o mesmo contrato da API.

Ele deve ser acionado quando ocorrer:

- ausência de chave de LLM;
- timeout;
- indisponibilidade do provedor;
- resposta vazia;
- JSON inválido;
- violação de schema;
- disciplina inventada;
- explicação incompatível com o plano;
- erro inesperado do provedor;
- qualquer falha que comprometa a validação da saída.

No fallback:

- o plano determinístico deve ser preservado;
- o contrato de resposta deve continuar o mesmo;
- `source` deve ser `deterministic_fallback`;
- `summary` deve permanecer útil e não técnica;
- warnings devem explicar a limitação sem vazar detalhes internos.

## 14. Guardrails de entrada

### Validações obrigatórias

O backend deve rejeitar:

- lista vazia de disciplinas;
- IDs duplicados;
- disciplina inexistente;
- horas iguais a zero ou negativas;
- horas acima de limite plausível;
- dias vazios;
- dias repetidos;
- duração máxima inválida;
- duração abaixo do bloco mínimo;
- início de janela maior ou igual ao fim;
- janelas sobrepostas;
- tipos de campo inválidos;
- texto excessivamente longo;
- campos extras fora do schema;
- tentativa de usar texto livre para introduzir disciplinas inexistentes.

### Limites sugeridos

Para manter o MVP simples e previsível:

- `available_hours_per_week` deve ficar em uma faixa plausível;
- `max_session_minutes` deve ser múltiplo do bloco mínimo;
- blocos mínimos devem ser de 30 minutos;
- texto livre deve ter limite curto e explícito;
- janelas não devem ultrapassar 24 horas por dia.

### Prioridades

Prioridades devem ser:

- opcionais;
- explícitas;
- numéricas ou categóricas com mapeamento fixo;
- estáveis durante a execução;
- ignoradas fora do conjunto de disciplinas selecionadas.

## 15. Guardrails de saída

Antes de retornar a resposta, o backend deve validar:

- todas as disciplinas existem;
- todas as disciplinas vieram da lista selecionada;
- todos os dias são permitidos;
- nenhuma sessão ultrapassa o máximo por sessão;
- nenhuma duração é zero ou negativa;
- o total alocado não ultrapassa o disponível;
- janelas diárias são respeitadas quando existirem;
- não existem campos inventados;
- o resumo não contradiz o plano;
- a resposta segue o schema esperado.

Se o LLM produzir conteúdo inválido:

- ignorar a parte inválida;
- preservar o plano-base;
- cair para fallback determinístico;
- registrar o motivo internamente.

Se o plano determinístico falhar na validação:

- não mascarar o defeito;
- retornar erro controlado;
- registrar o problema;
- corrigir a causa na implementação futura.

## 16. Integração com o frontend

O frontend deve expor uma interface mínima para:

- selecionar disciplinas já cadastradas;
- informar disponibilidade;
- escolher dias ou janelas;
- definir duração máxima por sessão;
- definir prioridades opcionais;
- escrever objetivo opcional;
- gerar o plano;
- visualizar loading;
- visualizar erros de validação;
- visualizar warnings;
- visualizar o plano agrupado por dia;
- distinguir `llm_assisted` de `deterministic_fallback`;
- tentar novamente sem perder os dados preenchidos.

### Regras de UX

- não redesenhar o restante da aplicação;
- reutilizar o shell e estilos existentes;
- não exibir JSON cru;
- não exibir stack trace;
- não apresentar fallback como falha total;
- não afirmar uso de IA quando `source` indicar fallback;
- não inventar horários se a entrada não trouxer janelas;
- não perder o formulário em caso de falha da API.

### Navegação

Adicionar navegação mínima para a tela de planejamento, seguindo o padrão atual de navegação hash do frontend.

## 17. Observabilidade

Os logs devem ser estruturados e suficientes para auditoria do planejador.

### Registrar

- `request_id`;
- duração total;
- duração do LLM, quando houver;
- ferramentas executadas;
- quantidade de disciplinas;
- quantidade de sessões;
- minutos solicitados;
- minutos alocados;
- validações rejeitadas;
- fallback acionado;
- categoria do erro do provedor;
- modelo utilizado;
- tokens, quando disponíveis.

### Não registrar

- chave de API;
- headers de autenticação;
- prompt completo;
- chain-of-thought;
- dados pessoais desnecessários;
- matrícula;
- PDF bruto.

## 18. Casos de teste

Esta fatia deve ser validada, futuramente, com testes que cubram pelo menos:

1. uma disciplina;
2. várias disciplinas;
3. pesos de prioridade;
4. desempate determinístico;
5. distribuição somente em dias permitidos;
6. limite máximo por sessão;
7. arredondamento por blocos;
8. disponibilidade insuficiente;
9. nenhuma disciplina;
10. disciplina inexistente;
11. ID duplicado;
12. horas inválidas;
13. janelas inválidas;
14. texto excessivamente longo;
15. plano determinístico válido;
16. saída válida do LLM;
17. timeout do LLM;
18. resposta vazia;
19. JSON inválido;
20. schema inválido;
21. disciplina inventada pelo LLM;
22. fallback sem chave configurada;
23. contrato do endpoint;
24. sanitização de erros;
25. métricas e origem da resposta.

### Casos de UI

A interface deve demonstrar, no mínimo:

- carregamento das disciplinas;
- envio correto do formulário;
- exibição do plano;
- exibição de warnings;
- identificação de fallback;
- estado de loading;
- erro de validação;
- preservação dos dados após falha;
- ausência de disciplinas cadastradas.

## 19. Critérios de aceite

Esta spec será considerada aceita se:

- `specs/007-agente-planejamento-semanal-estudos-mvp.md` existir;
- a spec definir um endpoint de geração de plano semanal;
- a entrada exigir disciplinas cadastradas e disponibilidade do estudante;
- o plano-base for determinístico;
- o plano respeitar dias, duração máxima e disponibilidade;
- horários reais só forem usados quando janelas reais existirem;
- o frontend consiga renderizar o plano sem interpretar texto livre;
- o LLM não controlar a estrutura da agenda;
- nenhuma disciplina inexistente apareça na resposta;
- o sistema funcione sem chave de LLM;
- o fallback mantenha o mesmo contrato;
- guardrails e logs estejam especificados;
- a integração SIGAA atual permaneça fora do escopo desta fatia.

## 20. Próximos passos

1. Implementar o contrato do endpoint e os schemas de entrada/saída.
2. Criar as funções internas do planejador determinístico.
3. Conectar o fallback e a explicação opcional por LLM.
4. Adicionar a tela mínima de planejamento no frontend.
5. Criar testes de validação, fallback e contrato da API.
6. Revisar os logs para garantir ausência de dados sensíveis.
