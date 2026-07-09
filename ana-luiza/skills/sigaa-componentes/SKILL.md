---
name: sigaa-componentes
description: Consulta páginas públicas do SIGAA/UnB para buscar dados de componentes curriculares, como nome, código, carga horária, ementa e programa atual.
---

# Skill: SIGAA Componentes

## Objetivo

Buscar dados públicos de componentes curriculares no SIGAA/UnB.

## Dados desejados

- código;
- nome;
- unidade;
- carga horária;
- ementa;
- programa atual, se disponível;
- URL da fonte.

## Regras

- Não solicitar login ou senha.
- Não acessar área autenticada.
- Não fazer scraping massivo.
- Usar cache local.
- Registrar a URL da fonte consultada.
- Retornar fallback amigável se a consulta falhar.
- Não inventar ementa.

## Estratégia

1. Receber código ou nome da disciplina.
2. Consultar a página pública de componentes curriculares.
3. Fazer parsing do HTML.
4. Extrair campos disponíveis.
5. Salvar em cache.
6. Retornar dados estruturados.

## Fallback

Se a disciplina não for encontrada:

```json
{
  "status": "not_found",
  "message": "Não foi possível encontrar a ementa na fonte pública consultada.",
  "source_url": null
}
````

## Testes obrigatórios

Criar testes com HTML salvo localmente para não depender do SIGAA nos testes automatizados.
