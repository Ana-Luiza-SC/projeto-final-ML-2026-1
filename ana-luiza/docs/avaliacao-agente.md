# Avaliação do Agente EstudaUnB

## Objetivo

Validar os 8 cenários mínimos definidos na Spec 004 para o agente de recomendação de estudos do EstudaUnB.

Nesta etapa, a avaliação cobre apenas o fallback por regras. Não há chamada real ao Google/Gemini e não há dependência de `GOOGLE_API_KEY`.

## Estratégia

- Executar cenários automatizados via `pytest` em [backend/tests/test_agent_evaluation_scenarios.py](/home/analu/unb/tees/trabalho_final/ana-luiza/backend/tests/test_agent_evaluation_scenarios.py).
- Exercitar o endpoint `POST /api/agent/study-recommendation` com dados controlados.
- Forçar o caminho de fallback por regras com `LLM_PROVIDER=google`, `LLM_FALLBACK_ENABLED=true` e ausência de `GOOGLE_API_KEY`.

## Cenários

| Cenário | Entrada resumida | Comportamento esperado | Métrica avaliada | Resultado obtido |
| --- | --- | --- | --- | --- |
| 1. Menção projetada MM e frequência adequada | Disciplina com 20 aulas, 1 falta, avaliação com nota 5.5 | Dedicação `low`, fallback ativo, `reasons` e `recommended_actions` não vazios | `dedication_level`, `used_fallback`, `provider`, completude da resposta | Passou |
| 2. Menção projetada MS e frequência desconhecida | Disciplina sem dados de frequência, avaliação com nota 8.0 | Dedicação `low` ou `medium`, sem afirmação de aprovação final | `dedication_level`, guardrail de frequência desconhecida | Passou |
| 3. Menção projetada MI e frequência adequada | Disciplina com frequência adequada, avaliação com nota 4.0 | Dedicação `high`, fallback ativo | `dedication_level`, `used_fallback`, `provider` | Passou |
| 4. Frequência abaixo de 75% | Disciplina com 20 aulas e 6 faltas, avaliação com nota 9.0 | Dedicação `high` e risco por falta explícito | `dedication_level`, menção a risco por falta | Passou |
| 5. Nota necessária maior que 10 | Avaliação concluída com peso 80 e nota 1.0, peso restante 20 sem nota | Dedicação `high` e alerta de meta inalcançável | `dedication_level`, menção a `maior que 10` | Passou |
| 6. Sem avaliações cadastradas | Disciplina sem nenhuma avaliação, frequência adequada | Resposta com fallback, ação para cadastrar mais avaliações/pesos e informação ausente | completude da resposta, `missing_information`, ação corretiva | Passou |
| 7. Vários conteúdos difíceis pendentes | Três tópicos `high` pendentes, avaliação com nota 8.0 | Dedicação `high` e ação priorizando conteúdos difíceis | `dedication_level`, aderência às ações recomendadas | Passou |
| 8. Ausência de GOOGLE_API_KEY | Provedor `google`, fallback habilitado e chave ausente | `used_fallback=true` e `provider=rules` | fallback e isolamento do LLM | Passou |

## Critérios verificados nos testes

- `dedication_level`
- `used_fallback`
- `provider`
- `reasons` não vazio
- `recommended_actions` não vazio
- ausência de afirmação de aprovação final quando a frequência é desconhecida
- presença de risco por falta quando a frequência está abaixo de 75%

## Resultado obtido

Na validação desta tarefa, os 8 cenários passaram em `pytest` usando apenas o fallback por regras. O endpoint do agente permaneceu funcional sem `GOOGLE_API_KEY`.

## Limitações

- A avaliação desta etapa não cobre chamadas reais ao Google/Gemini, timeout real de rede ou validação de resposta do LLM.
- Os cenários exercitam o comportamento atual do fallback e do cálculo determinístico existentes.
- No cenário sem avaliações cadastradas, o comportamento atual ainda depende da simulação determinística disponível; se o projeto endurecer a regra para não projetar menção sem notas lançadas, os testes e esta documentação precisarão ser revisados.
