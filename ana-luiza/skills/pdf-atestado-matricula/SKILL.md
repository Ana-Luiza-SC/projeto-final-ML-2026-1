---
name: pdf-atestado-matricula
description: Extrai disciplinas, atividades acadêmicas, turmas, docentes, locais, status e códigos de horário de PDFs de atestado de matrícula do SIGAA/UnB enviados pelo estudante.
---

# Skill: PDF de Atestado de Matrícula SIGAA/UnB

## Objetivo

Implementar parsing de PDFs de atestado de matrícula do SIGAA/UnB.

O parser deve extrair, quando disponível:

- período letivo;
- código da disciplina;
- nome da disciplina;
- docente ou orientador;
- tipo do item, como DISCIPLINA ou ATIVIDADE DE ORIENTAÇÃO INDIVIDUAL;
- local;
- turma;
- status;
- código de horário, como 24M12, 24M34, 24T23 ou 24T45;
- tabela semanal de horários.

## Estrutura esperada do PDF

O atestado pode conter:

1. Cabeçalho institucional.
2. Dados pessoais do estudante.
3. Turmas matriculadas.
4. Atividades matriculadas.
5. Tabela principal com colunas:
   - Cód.
   - Componentes Curriculares/Docentes
   - Turma
   - Status
   - Horário
6. Tabela de horários semanal.
7. Bloco de autenticação do documento.

## Regras de parsing

- Usar primeiro extração textual com pdfplumber.
- Se falhar, tentar PyMuPDF.
- Não usar OCR no MVP, exceto se explicitamente necessário.
- Separar disciplinas regulares de atividades acadêmicas.
- Não salvar automaticamente os dados extraídos.
- Retornar uma prévia para revisão humana.
- Não armazenar PDF bruto por padrão.
- Não registrar nome, matrícula ou código de verificação em logs.

## Tipos de item

### Disciplina regular

Campos esperados:

- code
- name
- professor
- type
- local
- class_code
- status
- schedule_code

### Atividade acadêmica

Campos esperados:

- code
- name
- advisor
- participation_type
- status
- schedule_code

Atividades sem horário devem retornar `schedule_code: null`.

## Saída esperada

```json
{
  "status": "success",
  "period": "2026.1",
  "disciplines": [],
  "activities": [],
  "warnings": []
}
````

## Fallback obrigatório

Se nenhuma disciplina for extraída:

```json
{
  "status": "error",
  "message": "Não foi possível extrair disciplinas do PDF. Cadastre manualmente.",
  "fallback": "manual_entry"
}
```

## Testes obrigatórios

Criar testes para:

* PDF válido;
* texto extraído de PDF válido;
* PDF vazio;
* arquivo não PDF;
* atividade sem horário;
* disciplina com nome em múltiplas linhas;
* disciplina com dois docentes;
* status com caracteres quebrados, como MATRICULADO�A�.
