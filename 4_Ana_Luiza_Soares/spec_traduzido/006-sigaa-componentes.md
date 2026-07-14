# Spec 006 — Integração com Componentes Públicos do SIGAA/UnB

> Idioma: Português do Brasil
> Fonte canônica: [../specs/006-sigaa-componentes.md](../specs/006-sigaa-componentes.md)
> Status da tradução: sincronizada
> Última sincronização: 2026-07-13

## 1. Título

Integração com a página pública de componentes curriculares do SIGAA/UnB.

## 2. Objetivo

Especificar a próxima fatia do EstudaUnB para enriquecer disciplinas cadastradas manualmente com dados públicos de componentes curriculares da UnB.

O objetivo é permitir consulta por código ou nome da disciplina em fonte pública do SIGAA, retornando dados estruturados e auditáveis sem depender de login, sem acessar área autenticada e sem comprometer o fallback manual do sistema.

## 3. Problema que esta fatia resolve

Hoje o cadastro manual de disciplinas resolve o fluxo principal do produto, mas deixa o detalhe da disciplina pobre em contexto acadêmico institucional. O estudante precisa preencher ou descobrir externamente dados como carga horária, ementa e programa atual.

Esta fatia resolve essa limitação consultando a página pública de componentes curriculares do SIGAA/UnB para complementar o cadastro manual com dados públicos, mantendo o sistema útil mesmo quando a consulta externa falhar.

## 4. Fonte de dados

Fonte inicial pública:

- `https://sigaa.unb.br/sigaa/public/componentes/busca_componentes.jsf`

Essa página pública informa que permite consultar componentes curriculares oferecidos nos cursos da UnB, visualizar detalhes e consultar o programa atual.

Nesta fatia, a integração deve usar apenas essa fonte pública e URLs públicas derivadas dela, caso a navegação para detalhes do componente também ocorra em páginas públicas.

## 5. Licença/condições de uso e limitações

- A integração deve usar apenas navegação pública, sem autenticação e sem contornar restrições do portal.
- Não deve haver scraping massivo nem coleta em lote de todo o catálogo.
- A consulta deve ser sob demanda, acionada por busca do usuário ou por enriquecimento de uma disciplina específica.
- Como a página usa JSF, a estrutura HTML pode mudar com frequência; a implementação deve assumir fragilidade de parsing e depender de fallback.
- Se `requests` + `BeautifulSoup` não forem suficientes por causa do fluxo JSF, a implementação futura deve registrar fallback técnico para Playwright, mas sem torná-lo obrigatório nesta primeira versão.

## 6. Escopo

Esta fatia deve especificar a futura implementação de:

- Serviço backend para busca de componentes curriculares públicos do SIGAA.
- Busca por código ou nome da disciplina.
- Retorno estruturado com:
  - código do componente;
  - nome;
  - tipo;
  - unidade;
  - carga horária;
  - ementa, se disponível;
  - programa atual, se disponível;
  - URL da fonte;
  - timestamp de consulta;
  - status da consulta.
- Cache local simples em memória ou arquivo JSON.
- Endpoint de busca pública no backend.
- Endpoint opcional para associar dados do componente SIGAA a uma disciplina já cadastrada.
- Documentação Swagger/OpenAPI dos endpoints.
- Preparação de integração futura com a página de detalhe da disciplina no frontend.

## 7. Fora do escopo

- Login no SIGAA.
- Páginas autenticadas.
- Dados de estudante.
- Histórico de aprovação ou reprovação.
- Taxa de trancamento.
- Dificuldade por professor.
- Avaliação de professor.
- Scraping massivo.
- Importação de PDF.
- Calendário.
- Persistência em banco robusto.

## 8. Estratégia técnica

Estratégia inicial proposta:

1. Criar um serviço backend dedicado para consulta pública de componentes.
2. Fazer busca sob demanda por `query`, interpretando código ou nome.
3. Tentar usar `requests` + `BeautifulSoup` para:
   - carregar a página pública;
   - reproduzir a busca mínima necessária;
   - extrair resultado encontrado;
   - seguir link público de detalhe, se necessário, para obter ementa ou programa.
4. Normalizar os dados em um contrato estruturado e explícito.
5. Se o fluxo JSF impedir uma implementação estável com HTML estático, documentar fallback técnico futuro para Playwright.

Requisitos adicionais:

- Não inventar nenhum campo ausente.
- Não inferir ementa, programa ou carga horária.
- Registrar claramente `status`, `warnings`, `source_url` e `timestamp`.
- Tratar resposta `not_found` como caso esperado, não como falha fatal.

## 9. Estratégia de cache

Primeira versão:

- Cache local em memória ou arquivo JSON simples.
- Chave de cache baseada em `query` normalizada e, se necessário, no identificador do componente encontrado.
- TTL curto e configurável futuramente, suficiente para evitar consultas repetidas na mesma demonstração.
- O retorno deve indicar se veio de cache com o campo `cached`.

Regras:

- O cache não deve armazenar dados pessoais.
- O cache deve armazenar apenas dados acadêmicos públicos e metadados da consulta.
- O cache deve poder ser descartado sem impacto no funcionamento do cadastro manual.
- Se o cache estiver inválido ou ausente, a aplicação deve continuar funcionando com nova tentativa de consulta ou fallback manual.

## 10. Contratos de API

Endpoint principal proposto:

```http
GET /api/sigaa/components/search?query=FGA0315
```

Resposta de sucesso:

```json
{
  "status": "found",
  "source": "sigaa_public_components",
  "query": "FGA0315",
  "component": {
    "code": "FGA0315",
    "name": "QUALIDADE DE SOFTWARE 1",
    "type": "DISCIPLINA",
    "unit": "FCTE",
    "workload_hours": 60,
    "syllabus": "",
    "current_program": "",
    "source_url": "https://sigaa.unb.br/...",
    "fetched_at": "2026-07-09T23:59:59Z",
    "lookup_status": "found"
  },
  "cached": false,
  "warnings": []
}
```

Resposta quando não encontrar:

```json
{
  "status": "not_found",
  "source": "sigaa_public_components",
  "query": "FGA0315",
  "component": null,
  "cached": false,
  "warnings": [
    "Não foi possível encontrar o componente na fonte pública consultada."
  ]
}
```

Resposta de falha externa controlada:

```json
{
  "status": "source_unavailable",
  "source": "sigaa_public_components",
  "query": "FGA0315",
  "component": null,
  "cached": false,
  "warnings": [
    "A fonte pública consultada está indisponível no momento.",
    "Use ou mantenha o cadastro manual da disciplina."
  ]
}
```

Endpoint opcional:

```http
PATCH /api/disciplines/{id}/sigaa-component
```

Finalidade:

- Associar ou atualizar uma disciplina já cadastrada com dados públicos do SIGAA.

Comportamento esperado:

- Preservar o cadastro manual como fonte funcional principal.
- Atualizar apenas os campos efetivamente encontrados na fonte pública.
- Registrar `source_url`, timestamp e status da associação.

## 11. Integração com disciplina existente

A integração com disciplina já cadastrada deve seguir estas regras:

- O cadastro manual continua obrigatório como fallback.
- A consulta SIGAA complementa a disciplina, não substitui o fluxo manual.
- Campos ausentes na fonte pública não devem sobrescrever dados manuais com valores vazios.
- Os dados públicos devem ser marcados como provenientes do SIGAA.
- A disciplina deve continuar utilizável mesmo que a associação falhe.

Campos candidatos para enriquecimento:

- `code`
- `name`
- `type`
- `unit`
- `workload_hours`
- `syllabus`
- `current_program`
- `source_url`
- `sigaa_lookup_status`
- `sigaa_fetched_at`

## 12. Integração com frontend

Na página de detalhe da disciplina, prever futuramente:

- botão `Buscar dados no SIGAA`;
- exibição de ementa, programa atual e carga horária;
- indicação se o dado veio do cache;
- link para a URL pública da fonte;
- mensagem amigável se não encontrar;
- mensagem amigável se o SIGAA estiver indisponível.

Regras de UX:

- Não travar a tela se a consulta falhar.
- Não esconder o cadastro manual quando a busca pública falhar.
- Mostrar claramente que os dados vieram de fonte pública institucional.
- Mostrar aviso quando ementa ou programa não estiverem disponíveis.

## 13. Fallbacks

Fallbacks obrigatórios:

- Se o componente não for encontrado, retornar `not_found` sem quebrar o fluxo.
- Se o SIGAA estiver indisponível, retornar `source_unavailable` com aviso amigável.
- Se o parsing HTML falhar por mudança estrutural, retornar status controlado e manter o cadastro manual.
- Se `requests` + `BeautifulSoup` não forem suficientes por causa de JSF, registrar fallback técnico futuro para Playwright.
- Em qualquer falha externa, o sistema deve continuar funcionando com disciplina manual.

## 14. Guardrails

- Não inventar ementa.
- Não inventar programa atual.
- Não inventar carga horária.
- Não acessar área autenticada.
- Não solicitar login ou senha.
- Não armazenar dado pessoal.
- Não registrar nome, matrícula ou qualquer dado de estudante.
- Registrar URL da fonte consultada.
- Exibir aviso quando dado não for encontrado.
- Manter cadastro manual como fallback.
- Não fazer scraping massivo.
- Não depender da rede para testes automatizados.

## 15. Logs

Eventos mínimos previstos:

- `sigaa_component_search_requested`
- `sigaa_component_cache_hit`
- `sigaa_component_fetched`
- `sigaa_component_not_found`
- `sigaa_component_source_unavailable`
- `sigaa_component_parse_failed`
- `sigaa_component_attached_to_discipline`

Campos sugeridos:

- `timestamp`
- `event`
- `query`
- `source`
- `cached`
- `status`
- `source_url`
- `discipline_id`, quando houver associação
- `latency_ms`
- `error_type`, quando houver

Os logs não podem conter:

- dados pessoais de estudante;
- PDF bruto;
- matrícula;
- nome completo do estudante;
- qualquer credencial ou sessão.

## 16. Testes

Testes esperados:

- parsing de fixture HTML com componente encontrado;
- parsing de fixture HTML sem resultado;
- fonte SIGAA indisponível usa fallback;
- endpoint retorna `not_found` sem quebrar;
- cache evita nova consulta;
- não há chamada real ao SIGAA nos testes automatizados;
- não inventa `syllabus` quando o campo não existe;
- não inventa `current_program` quando o campo não existe;
- Swagger documenta os endpoints.

Regras de teste:

- Usar fixtures HTML anonimizadas e salvas localmente.
- Não depender da rede externa.
- Não depender da disponibilidade do SIGAA.
- Isolar o parser do restante da aplicação sempre que possível.

## 17. Critérios de aceite

- `specs/006-sigaa-componentes.md` existe.
- A spec usa somente fonte pública do SIGAA.
- A spec não inclui dados privados.
- A spec não inclui taxa de reprovação ou professor difícil.
- A spec define cache e fallback.
- A spec define testes sem depender da rede.
- A spec prepara integração com frontend.
- Nenhum código é implementado nesta tarefa.

## 18. Próximos passos

1. Mapear manualmente a estrutura HTML pública atual do SIGAA para definir o parser mínimo.
2. Criar fixtures HTML locais para resultado encontrado e `not_found`.
3. Implementar serviço backend de busca pública com cache local simples.
4. Expor `GET /api/sigaa/components/search` no backend com Swagger/OpenAPI.
5. Adicionar integração opcional com detalhe de disciplina no frontend.
6. Avaliar necessidade real de Playwright apenas se o fluxo JSF inviabilizar `requests` + `BeautifulSoup`.
