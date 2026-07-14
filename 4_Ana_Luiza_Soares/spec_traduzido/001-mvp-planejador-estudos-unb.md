
# Spec 001 — MVP EstudaUnB

> Idioma: Português do Brasil
> Fonte canônica: [../specs/001-mvp-planejador-estudos-unb.md](../specs/001-mvp-planejador-estudos-unb.md)
> Status da tradução: sincronizada
> Última sincronização: 2026-07-13

## Nome

EstudaUnB — Agente de Planejamento Acadêmico para Estudantes da UnB

## Objetivo

Construir uma plataforma web simples que ajude estudantes da Universidade de Brasília a organizar disciplinas, conteúdos, avaliações e metas de nota.

O sistema deve importar disciplinas a partir de um PDF de atestado de matrícula do SIGAA ou permitir cadastro manual. Depois disso, o estudante poderá registrar conteúdos, avaliações e notas. Um agente de IA irá classificar a dedicação recomendada por disciplina e sugerir ações de estudo.

## Problema

Estudantes da UnB frequentemente precisam lidar com várias disciplinas, avaliações, trabalhos, leituras e metas de aprovação ao mesmo tempo. A organização costuma ficar distribuída entre SIGAA, PDFs, anotações pessoais e calendários manuais.

A dor principal é transformar a grade e as avaliações em um plano de estudo acionável.

## Stakeholders

- Estudantes da UnB.
- Equipe da disciplina avaliadora.
- Desenvolvedores do projeto.

## Usuário principal

Estudante da UnB matriculado em disciplinas no semestre atual.

## Métrica de sucesso de negócio

Um estudante consegue importar ou cadastrar ao menos uma disciplina, registrar uma avaliação e receber uma recomendação de estudo em menos de 5 minutos.

## Métricas técnicas

- Parsing do PDF extrai corretamente código, nome e horário da disciplina em pelo menos 80% dos PDFs de teste.
- API de recomendação responde em menos de 10 segundos em média.
- 100% das entradas inválidas retornam erro amigável.
- Sistema possui fallback manual quando PDF ou scraping falhar.
- Sistema registra latência, erros e fallback acionado.

## Escopo do MVP

O sistema deve permitir:

1. Upload de PDF de atestado de matrícula.
2. Extração preliminar de disciplinas do PDF.
3. Tela de revisão dos dados extraídos.
4. Cadastro manual de disciplina.
5. Cadastro de conteúdos a estudar por disciplina.
6. Cadastro de avaliações, pesos e notas.
7. Cálculo de média parcial.
8. Cálculo de nota necessária para atingir média alvo.
9. Classificação de dedicação recomendada por IA.
10. Geração de recomendação semanal de estudo.
11. Fallback amigável quando PDF, scraping ou IA falhar.

## Fora do escopo

- Login com SIGAA.
- Scraping de área autenticada.
- Taxa histórica de aprovação/reprovação por professor.
- Integração com Google Calendar.
- Aplicativo mobile.
- Modelo preditivo treinado complexo.
- Calendário mensal/diário completo.
- Armazenamento permanente do PDF bruto.

## Fontes de dados

### Dados fornecidos pelo usuário

- PDF de atestado de matrícula.
- Disciplinas cadastradas manualmente.
- Conteúdos a estudar.
- Avaliações, pesos e notas.
- Meta de média final.

### Dados públicos externos

- Página pública de componentes curriculares do SIGAA/UnB.
- Página pública de turmas do SIGAA/UnB, se tecnicamente viável.

O sistema não deve depender de dados históricos de reprovação/aprovação por professor, pois essa fonte ainda não foi confirmada.

## Entidades principais

### Discipline

Campos:
- id
- code
- name
- class_code
- professor
- schedule
- syllabus
- source_url
- created_at
- updated_at

### StudyTopic

Campos:
- id
- discipline_id
- title
- description
- status
- difficulty
- due_date

Status possíveis:
- not_started
- in_progress
- reviewed

Dificuldade:
- low
- medium
- high

### Assessment

Campos:
- id
- discipline_id
- name
- weight
- grade
- date
- topics

### GradeSimulation

Campos:
- discipline_id
- current_average
- completed_weight
- remaining_weight
- target_average
- required_average_on_remaining
- risk_level

### StudyRecommendation

Campos:
- discipline_id
- dedication_level
- confidence
- reasons
- recommended_actions
- generated_at

## Endpoints mínimos

### POST /api/import/matricula-pdf

Recebe PDF e retorna disciplinas extraídas.

Não deve salvar automaticamente no banco.

Resposta esperada:

```json
{
  "status": "success",
  "disciplines": [
    {
      "code": "FGA0000",
      "name": "Nome da Disciplina",
      "class_code": "01",
      "professor": "Nome do Professor",
      "schedule": "SEG 10:00-11:50"
    }
  ],
  "warnings": []
}

```

Se falhar:

```json
{
  "status": "error",
  "message": "Não foi possível extrair disciplinas do PDF. Cadastre manualmente.",
  "fallback": "manual_entry"
}

```

### POST /api/disciplines/confirm-import

Salva disciplinas confirmadas pelo usuário.

### POST /api/disciplines

Cadastra disciplina manualmente.

### GET /api/disciplines

Lista disciplinas cadastradas.

### GET /api/disciplines/{id}

Mostra detalhes de uma disciplina.

### POST /api/disciplines/{id}/topics

Cadastra conteúdo de estudo.

### POST /api/disciplines/{id}/assessments

Cadastra avaliação.

### GET /api/disciplines/{id}/grade-simulation

Calcula média, nota necessária e risco.

### POST /api/agent/study-recommendation

Gera classificação de dedicação e recomendação de estudo.

Entrada:

```json
{
  "discipline_id": "uuid",
  "target_average": 6.0
}

```

Saída:

```json
{
  "dedication_level": "high",
  "confidence": 0.78,
  "reasons": [
    "A próxima avaliação tem peso alto.",
    "Há conteúdos pendentes marcados como difíceis.",
    "A nota necessária restante está acima da média alvo."
  ],
  "recommended_actions": [
    "Priorizar os conteúdos pendentes da próxima avaliação.",
    "Reservar sessões curtas de revisão ao longo da semana."
  ]
}
```



## Regras acadêmicas da UnB

- A UnB usa menções SS, MS, MM, MI, II e SR.
- Menções de aprovação: SS, MS e MM.
- Menções de reprovação: MI, II e SR.
- Frequência mínima exigida: 75%.
- Faltas acima de 25% indicam risco grave ou reprovação por falta.
- O sistema deve alertar risco por falta mesmo quando a nota estiver boa.
- O sistema não deve afirmar aprovação final se a frequência for desconhecida.
- O cálculo de nota, menção e frequência é determinístico.
- O agente de IA deve explicar e recomendar, mas não calcular livremente nota/frequência.
- O sistema deve demonstrar o ciclo agente → API → produto.
- PDFs de atestado de matrícula não devem ser armazenados por padrão.
- O cadastro manual de disciplinas é fallback obrigatório.
- Scraping deve ser apenas de páginas públicas, futuramente.

## Regras de cálculo de nota

A média parcial deve ser calculada como:

```text
media_parcial = soma(nota * peso) / soma(pesos_concluidos)
```

A contribuição atual na nota final deve ser:

```text
contribuicao_atual = soma(nota * peso)
```

A nota média necessária nas avaliações restantes deve ser:

```text
necessaria_restante = (media_alvo - contribuicao_atual) / peso_restante
```

Assumir pesos em escala de 0 a 1 ou normalizar se vierem como porcentagem.

## Regras de risco acadêmico

Risco baixo:

* nota necessária restante <= 6.0

Risco médio:

* nota necessária restante > 6.0 e <= 8.0

Risco alto:

* nota necessária restante > 8.0
* ou avaliação próxima com peso alto
* ou muitos conteúdos pendentes difíceis

## Regras do agente

O agente deve considerar:

* conteúdos pendentes;
* dificuldade dos conteúdos;
* datas de avaliações;
* peso das avaliações;
* média atual;
* nota necessária;
* ementa, se disponível;
* carga horária, se disponível.

O agente deve retornar:

* dedicação recomendada;
* confiança;
* motivos;
* ações recomendadas.

O agente deve declarar incerteza quando dados importantes estiverem ausentes.

## Guardrails

Entrada:

* rejeitar PDF vazio;
* rejeitar arquivo que não seja PDF;
* rejeitar disciplina sem nome ou código;
* validar pesos entre 0 e 100%;
* validar notas entre 0 e 10.

Saída:

* não inventar dados do SIGAA;
* não afirmar taxas históricas;
* não avaliar professor;
* não gerar recomendação se não houver dados mínimos;
* sempre retornar justificativa.

## Fallbacks

* Se PDF falhar: cadastro manual.
* Se scraping SIGAA falhar: disciplina fica sem ementa, mas sistema continua.
* Se IA falhar: usar recomendação baseada em regras.
* Se cálculo de nota não for possível: mostrar campos faltantes.

## Interface mínima

Páginas:

1. Home

   * explicar o objetivo do sistema;
   * botão para importar PDF;
   * botão para cadastrar disciplina manualmente.

2. Importação

   * upload do PDF;
   * prévia dos dados extraídos;
   * botão confirmar;
   * opção editar campos.

3. Disciplinas

   * lista de disciplinas;
   * risco/dedicação por disciplina.

4. Detalhe da disciplina

   * dados básicos;
   * ementa, se encontrada;
   * conteúdos;
   * avaliações;
   * simulação de nota;
   * recomendação da IA.

## Critérios de aceite

* O backend sobe localmente.
* O frontend sobe localmente.
* O usuário consegue cadastrar disciplina manualmente.
* O usuário consegue enviar PDF e ver tentativa de extração.
* O usuário consegue confirmar ou editar disciplinas extraídas.
* O usuário consegue cadastrar avaliação com peso e nota.
* O sistema calcula média e nota necessária.
* O agente retorna recomendação explicada.
* O sistema possui fallback para PDF inválido.
* O sistema não quebra se o SIGAA estiver indisponível.
* O projeto roda com Docker ou docker-compose.
