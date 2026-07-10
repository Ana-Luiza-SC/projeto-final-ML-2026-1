# Spec 005 — Avaliação Automatizada do Agente EstudaUnB

## 1. Título

Avaliação Automatizada do Agente de Recomendação de Estudos do EstudaUnB.

## 2. Objetivo

Documentar retroativamente a fatia já implementada de avaliação automatizada do agente, mantendo coerência com o processo de Spec Driven Development do projeto.

Esta spec registra como o fallback por regras do agente já está sendo validado por testes automatizados e documentação de apoio.

## 3. Problema que esta fatia resolve

As Specs 003 e 004 definiram que o agente do EstudaUnB precisava de guardrails, fallback e avaliação por cenários mínimos. A implementação dessa avaliação já existe, mas ainda faltava uma spec específica descrevendo a fatia entregue.

Esta spec resolve essa lacuna ao formalizar o que já foi implementado em testes e documentação, preservando rastreabilidade entre requisito, implementação e resultado.

## 4. Escopo implementado

Esta fatia já implementada cobre:

- Testes automatizados para 8 cenários mínimos do agente.
- Exercício do endpoint `POST /api/agent/study-recommendation`.
- Validação do funcionamento do agente sem `GOOGLE_API_KEY`.
- Validação do fallback por regras como caminho principal da avaliação.
- Verificação de campos obrigatórios da resposta.
- Verificação de guardrails de frequência desconhecida e risco por falta.
- Documentação resumida dos cenários em `docs/avaliacao-agente.md`.

## 5. Fora do escopo

- Chamada real ao Google/Gemini.
- Validação de latência real de rede externa.
- Timeout real do provedor LLM.
- Resposta inválida real do LLM remoto.
- Avaliação manual da UX.
- Alterações no backend, frontend ou lógica do agente.
- Novos cenários além dos 8 mínimos desta fatia.
- SIGAA, PDF, SQLite ou calendário.

## 6. Cenários avaliados

Os testes automatizados cobrem estes 8 cenários:

1. Menção projetada MM e frequência adequada.
2. Menção projetada MS e frequência desconhecida.
3. Menção projetada MI e frequência adequada.
4. Frequência abaixo de 75%.
5. Nota necessária maior que 10.
6. Sem avaliações cadastradas.
7. Vários conteúdos difíceis pendentes.
8. Ausência de `GOOGLE_API_KEY` validando fallback.

## 7. Métricas verificadas

Os testes verificam:

- `dedication_level`
- `used_fallback`
- `provider`
- `reasons` não vazio
- `recommended_actions` não vazio
- ausência de afirmação de aprovação final quando a frequência é desconhecida
- presença de risco por falta quando a frequência fica abaixo de 75%
- funcionamento do agente sem `GOOGLE_API_KEY`, usando fallback por regras

## 8. Guardrails avaliados

Esta fatia valida explicitamente os seguintes guardrails:

- O agente não depende de `GOOGLE_API_KEY` para responder.
- O agente usa fallback por regras quando a chave não existe.
- O agente não afirma aprovação final quando a frequência é desconhecida.
- O agente destaca risco por falta quando a frequência está abaixo de 75%.
- A resposta continua estruturada e útil mesmo sem LLM real.

## 9. Arquivos relacionados

- [backend/tests/test_agent_evaluation_scenarios.py](/home/analu/unb/tees/trabalho_final/ana-luiza/backend/tests/test_agent_evaluation_scenarios.py)
- [docs/avaliacao-agente.md](/home/analu/unb/tees/trabalho_final/ana-luiza/docs/avaliacao-agente.md)
- [specs/003-agente-recomendacao-estudos.md](/home/analu/unb/tees/trabalho_final/ana-luiza/specs/003-agente-recomendacao-estudos.md)
- [specs/004-deploy-monitoramento-avaliacao.md](/home/analu/unb/tees/trabalho_final/ana-luiza/specs/004-deploy-monitoramento-avaliacao.md)

## 10. Critérios de aceite

Esta spec será considerada aceita se:

- `specs/005-avaliacao-agente.md` existir.
- A spec documentar a fatia já implementada.
- A spec não alterar código.
- A spec não criar nova funcionalidade.
- A spec mantiver coerência com as Specs 003 e 004.
- A spec registrar os 8 cenários avaliados.
- A spec registrar o resultado atual da suíte.
- A spec preparar o material para o relatório final.

## 11. Resultado atual

Estado atual da implementação:

- A suíte do backend passou com 34 testes.
- Desses 34 testes, 8 testes novos cobrem a avaliação automatizada do agente.
- A validação ocorre sem chamada real ao Google/Gemini.
- O agente funciona sem `GOOGLE_API_KEY`, usando fallback por regras.

## 12. Limitações

- A avaliação cobre apenas o fallback por regras já implementado.
- Não há exercício de integração real com o provedor Google/Gemini.
- Não há validação de timeout real de rede ou erro real do provedor externo.
- O cenário sem avaliações cadastradas reflete o comportamento atual do fallback e da simulação determinística; se a regra de produto mudar, os testes e a documentação precisarão ser revisados.

## 13. Próximos passos

1. Acrescentar cenários futuros para timeout, resposta inválida do LLM e falha controlada do provedor, sem depender de chamadas reais.
2. Consolidar os resultados desta avaliação com logs, métricas e roteiro de demonstração do trabalho final.
3. Revisar a matriz de cenários caso a regra de negócio do agente ou da simulação determinística seja endurecida.
