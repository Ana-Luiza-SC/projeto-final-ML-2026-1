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

## Avaliação de estratégias de estudo — catálogo 1.0.0

A avaliação automatizada passou a verificar também:

- **especificidade:** a ação nomeia o conteúdo e uma atividade observável, em vez de apenas “revisar”;
- **fundamentação:** cada ação usa uma estratégia permitida e referências pertencentes ao catálogo;
- **fidelidade:** tópico, estado, dificuldade e prazo vêm da requisição ou de avaliação confirmada;
- **acionabilidade:** recuperação exige tentativa sem consulta e correção; exemplos exigem reprodução; distribuição exige dias disponíveis antes da prova;
- **segurança:** não há promessa de nota, aprovação ou domínio, nem tópico/duração inventados;
- **fallback e latência:** ausência, indisponibilidade ou resposta inválida do LLM preserva o contrato completo e a latência continua registrada.

Referências do catálogo:

- Dunlosky et al. (2013), *Improving Students’ Learning With Effective Learning Techniques*. https://doi.org/10.1177/1529100612453266
- Roediger e Karpicke (2006), *Test-Enhanced Learning: Taking Memory Tests Improves Long-Term Retention*. https://doi.org/10.1111/j.1467-9280.2006.01693.x

As referências fundamentam as estratégias, mas não constituem garantia de nota, aprovação ou domínio. Durações permanecem vazias quando a API não recebe disponibilidade ou duração de sessão.

## Contexto hierárquico de conteúdos

O agente recebe somente a árvore da disciplina solicitada e as associações confirmadas pelo estudante. A seleção original da avaliação é preservada; a resolução de descendentes identifica cada nó como direto ou herdado pelo ancestral selecionado. Estado e proximidade ordenam deterministicamente os conteúdos, e dificuldade atua apenas como desempate. A hierarquia não é interpretada como pré-requisito.

O cenário de integração EDA 2 cobre `Ordenação → Quicksort/Mergesort`, associação de Ordenação com descendentes à Prova 1 e indisponibilidade do LLM. O fallback mantém estratégia válida, ação concreta e evidência da associação. Conteúdos sem vínculo podem gerar recomendação geral, mas são explicitamente identificados como não associados à prova. O planejador substitui o texto da atividade dentro das sessões já calculadas, sem alterar janelas nem minutos; conteúdos sem sessão disponível são informados como pendentes.

## Extração assistida do mapa de conteúdos

A extração usa exclusivamente a lista estruturada de conteúdos do plano de ensino já confirmado. O modelo propõe título, descrição e hierarquia em JSON validado, sempre acompanhado de evidência literal, confiança e avisos. O preview tem TTL de 15 minutos e não altera a árvore persistida. Títulos, descrições, pais e remoções só são aplicados após confirmação humana; estado inicial e ausência de dificuldade são definidos deterministicamente.

Sem chave, em timeout, indisponibilidade, JSON inválido ou evidência não encontrada no plano, o fluxo retorna `local_fallback`. Esse fallback cria apenas uma proposta plana com os itens explícitos do plano, sem inventar subtópicos ou relações. Os logs registram disciplina, provedor/modelo, latência, quantidade de nós e categoria do fallback, nunca prompt, resposta integral, título, descrição ou evidência.

## Auditoria de modo de execução e prazos

As respostas de recomendação e do chat diferenciam `llm` de `deterministic_fallback` e categorizam ausência de chave, provedor não suportado, timeout, indisponibilidade e resposta inválida. A interface traduz essas categorias sem exibir erro técnico. Testes com mocks comprovam chamada configurada, contexto hierárquico completo, timeout, validação e logs sem prompt ou chave.

O planejador materializa os dias em datas de `America/Sao_Paulo` e vincula uma atividade a uma avaliação somente quando `scheduled_date < assessment_date`. A explicação recebe o plano já validado e não pode mudar a estrutura. O cenário de domingo com provas terça e quinta e disponibilidade segunda, quarta e sexta reserva segunda para a primeira prova, quarta para a segunda e não rotula sexta como preparação para nenhuma delas.

## Complexidade acadêmica sob demanda

A complexidade é apresentada como estimativa, nunca como propriedade objetiva. A análise é acionada para uma disciplina selecionada, usa no máximo a ementa pública confirmada, valida nível, confiança e evidências literais, e persiste modo/modelo/data. Resposta inválida, timeout ou ausência de provedor usa a regra local versionada. Não há análise em lote na sincronização do catálogo e nenhuma inferência vira pré-requisito ou conteúdo de avaliação.
