---
name: privacidade-documentos-academicos
description: Define regras para tratar, anonimizar, descartar e não registrar dados pessoais extraídos de documentos acadêmicos enviados pelo estudante.
---

# Skill: Privacidade em Documentos Acadêmicos

## Objetivo

Garantir minimização de dados ao processar documentos acadêmicos enviados pelo estudante.

## Dados pessoais possíveis

- nome completo;
- matrícula;
- curso;
- vínculo;
- data de emissão;
- código de verificação;
- QR code;
- assinatura;
- histórico acadêmico;
- notas.

## Regras obrigatórias

- Não armazenar o PDF bruto por padrão.
- Não salvar nome completo nem matrícula se não forem necessários.
- Não registrar dados pessoais em logs.
- Não enviar dados pessoais desnecessários ao LLM.
- Não commitar PDFs reais no repositório.
- Usar fixtures anonimizadas nos testes.
- O usuário deve revisar os dados extraídos antes de salvar.
- Armazenar apenas os campos necessários para organização de estudos.

## Campos permitidos no MVP

- código da disciplina;
- nome da disciplina;
- turma;
- professor/docente;
- horário;
- local;
- período letivo;
- status da matrícula na disciplina.

## Campos que não devem ser persistidos

- nome completo do estudante;
- matrícula;
- código de verificação;
- link de autenticação do documento;
- PDF original.

## Logs permitidos

```json
{
  "event": "pdf_import_finished",
  "disciplines_found": 4,
  "activities_found": 1,
  "fallback_used": false,
  "duration_ms": 842
}
````

## Logs proibidos

```json
{
  "student_name": "...",
  "registration_number": "...",
  "verification_code": "..."
}
```

## Testes obrigatórios

Criar testes para garantir que:

* matrícula não aparece nos logs;
* nome do estudante não aparece nos logs;
* código de verificação não é salvo;
* PDF bruto não é persistido por padrão;
* fixtures de teste são anonimizadas.
