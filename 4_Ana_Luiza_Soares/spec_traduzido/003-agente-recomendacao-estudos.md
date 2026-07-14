# Spec 003 — Agente de Recomendação de Estudos EstudaUnB

> Idioma: Português do Brasil
> Fonte canônica: [../specs/003-agente-recomendacao-estudos.md](../specs/003-agente-recomendacao-estudos.md)
> Status da tradução: sincronizada
> Última sincronização: 2026-07-13

## 1. Título

Agente de Recomendação de Estudos do EstudaUnB — interpretação acadêmica, dedicação recomendada e ações semanais.

## 2. Objetivo

Especificar a próxima fatia do EstudaUnB: um agente de IA que interpreta dados acadêmicos já estruturados e a simulação determinística calculada pelo backend para gerar recomendações de estudo claras, auditáveis e seguras.

O agente deve explicar a situação acadêmica do estudante, classificar a dedicação recomendada como baixa, média ou alta e sugerir ações de estudo para a semana. Ele não deve recalcular livremente nota, menção ou frequência; esses resultados vêm do backend determinístico.

## 3. Problema que esta fatia resolve

O EstudaUnB já permite cadastrar disciplinas, avaliações e faltas, além de calcular média, menção, nota necessária, frequência e riscos. Ainda falta transformar esses dados em uma recomendação orientada à ação, com linguagem compreensível para o estudante e respeitando as regras acadêmicas da UnB.

Esta fatia resolve essa lacuna com um agente que usa a simulação acadêmica como contexto e retorna uma recomendação explicável, com fallback por regras quando o LLM não puder ser usado com segurança.

## 4. Escopo

Esta fatia deve especificar a futura implementação de:

- Componente de agente no backend.
- Integração com Google/Gemini via API do Google.
- Endpoint `POST /api/agent/study-recommendation`.
- Uso da variável `GOOGLE_API_KEY` para autenticação do provedor LLM.
- Fallback determinístico baseado em regras.
- Guardrails de entrada e saída.
- Logs e monitoramento sem dados sensíveis.
- Contrato de resposta em JSON estruturado.
- Integração futura com a página de detalhe da disciplina no frontend.

O agente deve receber dados estruturados da disciplina, simulação acadêmica determinística e conteúdos pendentes, quando existirem.

## 5. Fora do escopo

- Scraping do SIGAA.
- Importação de PDF.
- Parsing real de PDF.
- Calendário mensal ou semanal.
- SQLite ou outra persistência nova.
- Autenticação.
- Histórico persistente de recomendações.
- Taxa de reprovação por professor.
- Avaliação de professor.
- Integração com Google Calendar.
- Treinamento, fine-tuning ou modelo preditivo complexo.
- Alteração dos cálculos determinísticos de nota, menção ou frequência.

## 6. Papel do agente

O agente deve:

- Receber dados estruturados da disciplina.
- Receber a simulação acadêmica determinística calculada pelo backend.
- Receber conteúdos pendentes, se existirem.
- Interpretar a situação acadêmica do estudante.
- Explicar a situação por menção.
- Explicar risco por falta.
- Classificar dedicação recomendada como `low`, `medium` ou `high`.
- Sugerir ações de estudo para a semana.
- Declarar incerteza quando faltarem dados.
- Respeitar as regras de menção da UnB.
- Respeitar a frequência mínima de 75%.
- Usar fallback baseado em regras se o LLM estiver indisponível, lento ou inválido.

O agente não pode:

- Recalcular livremente nota, menção ou frequência.
- Inventar dados do SIGAA.
- Inventar ementa.
- Inventar taxa de reprovação.
- Avaliar professor como fácil ou difícil.
- Afirmar aprovação final sem nota final e frequência final.
- Usar dados pessoais desnecessários no prompt.
- Registrar chave de API ou dados sensíveis em logs.

## 7. Entradas do agente

Entrada direta do endpoint:

```json
{
  "discipline_id": "uuid",
  "target_average": 5.0,
  "pending_topics": [
    {
      "title": "GQM",
      "difficulty": "medium",
      "status": "not_started"
    }
  ],
  "user_goal": "quero me organizar para a próxima semana"
}
```

O backend deve buscar internamente:

- Disciplina.
- Avaliações.
- Faltas/frequência.
- Simulação acadêmica determinística.
- Conteúdos pendentes, se existirem no modelo futuro.

Campos úteis para o contexto do agente:

- Código, nome, turma, horário e local da disciplina.
- Média parcial.
- Contribuição atual.
- Peso concluído.
- Peso restante.
- Nota necessária restante.
- Menção atual.
- Menção projetada.
- Risco por nota.
- Frequência.
- Percentual de faltas.
- Risco por falta.
- Warnings da simulação.
- Conteúdos pendentes com título, dificuldade e status.
- Objetivo textual curto do usuário.

## 8. Saídas do agente

Resposta esperada:

```json
{
  "dedication_level": "low | medium | high",
  "confidence": 0.0,
  "academic_situation_summary": "",
  "grade_status": "",
  "attendance_status": "",
  "recommended_actions": [],
  "reasons": [],
  "missing_information": [],
  "used_fallback": false,
  "provider": "google | rules",
  "latency_ms": 0
}
```

Regras de saída:

- `dedication_level` deve ser `low`, `medium` ou `high`.
- `confidence` deve estar entre 0 e 1.
- `recommended_actions` deve ser lista não vazia.
- `reasons` deve ser lista não vazia.
- `missing_information` deve listar dados importantes ausentes.
- `used_fallback` indica se fallback determinístico foi usado.
- `provider` deve ser `google` quando a resposta válida vier do LLM e `rules` quando vier do fallback.
- `latency_ms` deve medir a geração completa da recomendação.

## 9. Configuração do provedor LLM

Variáveis de ambiente previstas:

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=
LLM_MODEL=gemini-2.5-flash
LLM_TIMEOUT_SECONDS=8
LLM_FALLBACK_ENABLED=true
```

Regras obrigatórias:

- A chave deve ser lida de `GOOGLE_API_KEY`.
- Não usar variáveis antigas ou alternativas para chave do Gemini; a única variável oficial deve ser `GOOGLE_API_KEY`.
- Não commitar `.env` real.
- Criar futuramente apenas `.env.example` com `GOOGLE_API_KEY` vazio.
- Garantir futuramente que `.env` esteja no `.gitignore`.
- Não imprimir `GOOGLE_API_KEY` em logs.
- Não retornar `GOOGLE_API_KEY` em erro de API.
- Se `GOOGLE_API_KEY` não existir, usar fallback por regras.
- Se a chamada ao Google/Gemini falhar, usar fallback por regras.
- Se a chamada demorar mais que `LLM_TIMEOUT_SECONDS`, usar fallback por regras.
- Se a resposta do LLM vier inválida, usar fallback por regras.

## 10. Prompting e contrato de resposta

O prompt enviado ao LLM deve conter:

- Dados mínimos da disciplina.
- Resultado da simulação acadêmica determinística.
- Conteúdos pendentes.
- Objetivo do usuário.
- Regras de menção da UnB.
- Regra de frequência da UnB.
- Instrução explícita para responder apenas JSON válido.
- Esquema esperado da resposta.

O prompt não deve conter:

- Nome completo do estudante.
- Matrícula.
- Código de verificação.
- PDF bruto.
- Chave de API.
- Dados pessoais desnecessários.

Contrato do prompt:

- O LLM deve tratar nota, menção e frequência como dados fornecidos pelo backend, não como valores a recalcular.
- O LLM deve mencionar incerteza quando faltarem dados.
- O LLM deve priorizar risco por falta antes de recomendações de conteúdo quando frequência estiver abaixo de 75% ou faltas estiverem acima de 25%.
- O LLM deve rejeitar ou redirecionar pedidos para avaliar professor, prever taxa de reprovação sem fonte ou sair do escopo acadêmico.
- A resposta deve ser apenas JSON válido, sem Markdown e sem texto fora do objeto JSON.

## 11. Fallback baseado em regras

O fallback deve ser determinístico e retornar o mesmo formato do endpoint, com:

```json
{
  "used_fallback": true,
  "provider": "rules"
}
```

Dedicação alta se pelo menos uma condição forte ocorrer:

- Frequência abaixo de 75%.
- Risco por falta alto.
- Faltas acima de 25%.
- Menção projetada MI, II ou SR.
- Nota necessária restante maior que 8.
- Nota necessária restante maior que 10.
- Muitos conteúdos pendentes difíceis.
- Avaliação próxima com peso alto.

Dedicação média se:

- Risco por nota médio.
- Faltas entre 15% e 25%.
- Nota necessária entre 6 e 8.
- Alguns conteúdos pendentes.
- Avaliação em prazo intermediário.

Dedicação baixa se:

- Menção projetada MM, MS ou SS.
- Frequência confortável.
- Risco por nota baixo.
- Poucos conteúdos pendentes.
- Sem avaliação próxima.

O fallback deve gerar:

- Resumo acadêmico curto.
- Situação por menção.
- Situação por falta.
- Ações recomendadas específicas.
- Motivos baseados nos dados disponíveis.
- Lista de informações ausentes.

## 12. Guardrails de entrada

O backend deve:

- Rejeitar `discipline_id` inexistente com erro amigável.
- Validar `difficulty` como `low`, `medium` ou `high`.
- Validar `status` como `not_started`, `in_progress` ou `reviewed`.
- Limitar tamanho de `user_goal`.
- Limitar tamanho dos textos enviados ao LLM.
- Não enviar dados pessoais ao LLM.
- Não aceitar pedido para avaliar professor.
- Não aceitar pedido fora do escopo acadêmico.
- Não aceitar pedido para prever taxa de reprovação sem fonte.
- Sanitizar campos textuais antes de montar prompt e logs.

## 13. Guardrails de saída

A resposta do LLM deve ser validada antes de ser retornada ao frontend.

Regras obrigatórias:

- `dedication_level` deve ser `low`, `medium` ou `high`.
- `confidence` deve estar entre 0 e 1.
- `recommended_actions` deve ser lista não vazia.
- `reasons` deve ser lista não vazia.
- Não pode afirmar aprovação final se houver dados pendentes.
- Não pode afirmar aprovação final se frequência estiver desconhecida.
- Não pode afirmar dado que não existe.
- Não pode mencionar taxa histórica se ela não foi fornecida.
- Não pode avaliar professor como fácil ou difícil.
- Se a saída for inválida, usar fallback por regras.

## 14. Contratos de API

Endpoint futuro:

```http
POST /api/agent/study-recommendation
```

Entrada esperada:

```json
{
  "discipline_id": "uuid",
  "target_average": 5.0,
  "pending_topics": [
    {
      "title": "GQM",
      "difficulty": "medium",
      "status": "not_started"
    }
  ],
  "user_goal": "quero me organizar para a próxima semana"
}
```

O backend deverá buscar internamente:

- Disciplina.
- Avaliações.
- Faltas/frequência.
- Simulação acadêmica.
- Conteúdos pendentes, se existirem.

Saída esperada:

```json
{
  "dedication_level": "low | medium | high",
  "confidence": 0.0,
  "academic_situation_summary": "",
  "grade_status": "",
  "attendance_status": "",
  "recommended_actions": [],
  "reasons": [],
  "missing_information": [],
  "used_fallback": false,
  "provider": "google | rules",
  "latency_ms": 0
}
```

Erros esperados:

- `404`: disciplina inexistente.
- `422`: entrada inválida, como `difficulty`, `status` ou `target_average` inválidos.
- `400`: pedido fora do escopo acadêmico ou pedido para avaliar professor.

Falhas do LLM não devem causar erro 500 quando fallback estiver habilitado.

## 15. Integração com frontend

Na página de detalhe da disciplina, será adicionado futuramente:

- Botão `Gerar recomendação de estudo`.
- Campo opcional `objetivo da semana`.
- Lista simples de conteúdos pendentes.
- Painel de recomendação.
- Dedicação recomendada.
- Resumo da situação acadêmica.
- Situação por menção.
- Situação por falta.
- Ações recomendadas.
- Motivos.
- Aviso quando fallback for usado.

Regras de UX:

- Mostrar carregamento enquanto a recomendação é gerada.
- Mostrar erro amigável se a disciplina não existir.
- Mostrar aviso quando a recomendação veio de fallback por regras.
- Não expor stack trace.
- Não mostrar chave de API ou detalhes internos do provedor.
- Não afirmar aprovação final quando houver dados pendentes.

## 16. Logs e monitoramento

Eventos previstos:

- `agent_recommendation_requested`
- `llm_called`
- `llm_failed`
- `llm_timeout`
- `llm_invalid_response`
- `fallback_used`
- `agent_recommendation_generated`

Logs devem incluir:

- `provider`.
- `used_fallback`.
- `latency_ms`.
- `error_type`, quando houver.
- `discipline_id`, se não for dado sensível no contexto do sistema.
- Quantidade de conteúdos pendentes.
- Nível de dedicação retornado.

Logs não podem incluir:

- `GOOGLE_API_KEY`.
- Prompt completo com dados sensíveis.
- Nome do estudante.
- Matrícula.
- PDF bruto.
- Código de verificação.

## 17. Casos de teste

Testes futuros esperados:

1. Agente com `GOOGLE_API_KEY` ausente usa fallback.
2. Agente com timeout usa fallback.
3. Agente com resposta inválida usa fallback.
4. Disciplina inexistente retorna erro amigável.
5. Menção projetada MM e frequência adequada gera dedicação baixa ou média.
6. Menção projetada MI gera dedicação alta.
7. Frequência abaixo de 75% gera dedicação alta.
8. Frequência desconhecida não permite afirmar aprovação final.
9. Nota necessária maior que 10 gera alerta forte.
10. Conteúdo pendente difícil aumenta prioridade.
11. Pedido para avaliar professor é recusado.
12. Saída do LLM sem JSON válido é rejeitada.
13. Logs não incluem `GOOGLE_API_KEY`.
14. Logs indicam quando fallback foi usado.

## 18. Critérios de aceite

A spec será aceita se:

- `specs/003-agente-recomendacao-estudos.md` existir.
- A spec usar `GOOGLE_API_KEY` como única variável oficial de chave do provedor Google.
- A spec definir `LLM_PROVIDER=google`.
- A spec definir fallback por regras.
- A spec deixar claro que cálculo de nota/frequência é determinístico.
- A spec incluir guardrails de entrada e saída.
- A spec incluir logs e monitoramento.
- A spec incluir contrato de API.
- A spec incluir integração futura com frontend.
- A spec não implementar código.
- A spec não expandir escopo para PDF, SIGAA ou calendário.

## 19. Próximos passos

1. Criar `.env.example` com `GOOGLE_API_KEY` vazio e garantir `.env` no `.gitignore`.
2. Implementar serviço de recomendação no backend com fallback por regras.
3. Adicionar endpoint `POST /api/agent/study-recommendation`.
4. Criar testes unitários para fallback e validação de saída.
5. Criar testes de API para chave ausente, timeout e resposta inválida.
6. Integrar o painel de recomendação na página de detalhe da disciplina.
7. Registrar logs estruturados sem prompt sensível e sem chave de API.

## Regras de domínio da UnB

Menções de aprovação:

- SS
- MS
- MM

Menções de reprovação:

- MI
- II
- SR

Faixas:

- SS: 9.0 a 10.0
- MS: 7.0 a 8.9
- MM: 5.0 a 6.9
- MI: 3.0 a 4.9
- II: 0.1 a 2.9
- SR: 0.0 ou reprovação por falta/sem rendimento

Frequência:

- Frequência mínima: 75%.
- Faltas acima de 25% indicam risco grave/reprovação por falta.
- Se a frequência estiver desconhecida, o agente não pode afirmar aprovação final.
- Se a frequência estiver abaixo de 75%, o risco por falta deve aparecer antes das recomendações de conteúdo.
