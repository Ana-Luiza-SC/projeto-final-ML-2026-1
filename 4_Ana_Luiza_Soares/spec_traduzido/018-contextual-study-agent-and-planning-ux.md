# Spec 018 — Agente contextual de estudos e UX de planejamento

> Idioma: Português do Brasil
> Fonte canônica: [../specs/018-contextual-study-agent-and-planning-ux.md](../specs/018-contextual-study-agent-and-planning-ux.md)
> Status da tradução: sincronizada
> Última sincronização: 2026-07-13

## Status, propósito e princípios

Esta spec define a experiência canônica de planejamento, calendário, demanda e assistente contextual. Substitui a arquitetura de informação incremental das Specs 007, 013 e 017, preservando contratos compatíveis.

O backend controla cálculos acadêmicos, prioridade, cobertura de evidência, restrições e validação de ações. O estudante controla inclusão, confirmação, override de método e toda mutação. Ausência de evidência gera incerteza. Prioridade, demanda estimada, dificuldade específica do estudante, carga e fit de método permanecem separados. Bloco planejado não é atividade executada. LLM explica resultados validados, não inventa nem grava. Todo fluxo central funciona sem LLM. SIGAA é público, best-effort, cacheado e auditável.

## Diagnóstico histórico resolvido

A implementação anterior tinha `/study-plan` legado com prioridades manuais, horas semanais, duração máxima e sessões, enquanto `/calendar` duplicava janelas/preview. Também havia semana baseada no primeiro dia do mês, avaliação passada como prazo, cursor compartilhado que causava starvation, limite oculto de 90 minutos/um bloco, pendência sem decomposição de capacidade, Week como cartões não temporais, ementa ausente tratada como baixa complexidade, sugestões textuais sem ações validadas, catálogo duplicado e submit JSF de turma ausente.

A implementação atual unifica planejamento, usa semana atual/futura explícita, ignora prazos passados/concluídos, aloca por prioridade sem starvation, permite múltiplos blocos e análise detalhada, usa grid temporal semanal, trata ementa ausente como evidência insuficiente, carrega JSON canônico, oferece ações tipadas confirmáveis e envia o controle dinâmico do formulário público SIGAA.

## Arquitetura de informação e terminologia

- `/study-plan`: disponibilidade, prioridade automática, demanda, capacidade, preview e confirmação;
- `/calendar`: Month/Week, eventos, recorrência e blocos já confirmados;
- drawer contextual nas páginas autenticadas;
- **planned study block**: reserva temporal persistida como evento;
- **study activity**: execução real (ciclo completo ainda parcial pela Spec 015);
- **assessment**: trabalho avaliado; **academic event**: projeção temporal;
- **learner-specific difficulty** não é dificuldade objetiva da disciplina.

## Planejamento e demanda

O frontend envia semana e janelas, não `available_hours_per_week`, prioridade numérica nem `max_session_minutes`. Backend deriva total, reconstrói disciplinas/avaliações/conteúdos/eventos do usuário, calcula prioridade e demanda com confiança/razão/evidência ausente, aloca blocos conflict-free antes de prazos e retorna análise de capacidade por prioridade. Inclusão/exclusão é escolha do usuário; score não é substituído.

Confirmação revalida preview, usuário, expiração, disciplinas, prazos, conflitos e idempotência. Eventos persistidos carregam origem, vínculos, score/faixa/razão e `state=planned`. Não criar atividade real automaticamente.

## Calendário, PDFs e SIGAA

Month/Week usam o intervalo visível correto e Week é grade temporal. Recorrência manual é finita e expandida na leitura. PDF de plano tenta extração inteligente estruturada, valida schema/evidência e usa parser local em falha; nada salva sem revisão. PDF bruto/texto integral são descartados. SIGAA usa sessão JSF/ViewState, descobre semanticamente campos/botão, seleciona resultado, faz POST do detalhe de turma, parseia campos semânticos, cacheia/persiste e preserva dados básicos em fallback.

## Assistente contextual e ações

`POST /api/assistant/contextual/messages` recebe rota e IDs selecionados, nunca fatos acadêmicos livres como autoridade. Backend reconstrói contexto pertencente ao usuário: disciplina, avaliação, conteúdo, prioridade, demanda, janelas, capacidade, eventos, preview e catálogo.

Intenções incluem explicação de prioridade/capacidade, recomendação de janela/método e proposta de bloco. Resposta possui texto, evidências, modo/fallback e ações tipadas. Navegação é somente leitura. Mutação vira proposta temporária ligada ao usuário; `POST /api/assistant/actions/{action_id}/confirm` revalida tudo antes de `create_study_block`. Expiração, ownership, conflito novo e repetição são tratados com erro amigável/idempotência.

## Métodos, baseline e fallback

Recomendações leem `backend/app/knowledge/study_methods/study_methods.json`; PDF é evidência humana e não entra junto na mesma coleção. Sem LLM, respostas contextuais, prioridade, demanda, planejamento, métodos e ações seguras permanecem determinísticos. Saída LLM inválida, sem evidência, com valor inventado ou ação fora da enumeração é rejeitada.

## Guardrails, privacidade e observabilidade

Validar schemas, ownership, rota/IDs, evidência, datas/prazos, capacidade, conflito, expiração e idempotência. Não enviar nome/matrícula/PDF/segredo desnecessário, não registrar prompt/resposta integral e não avaliar professor/diagnosticar/prometer nota. Logs registram modo, versão, latência, contagens, fallback, ação/proposta/confirmação e categoria de erro.

## Testes, aceite e limitações

Testes cobrem catálogo JSON, evidência de método, ação read-only até confirmação, idempotência, conflito novo, expiração/isolamento, prioridade/demanda, planejamento/capacidade, Month/Week, SIGAA dinâmico e fallback. Aceite requer UX unificada sem formulário duplicado, conceitos separados, confirmação humana, fallback completo e dados ausentes como incerteza.

Limitações honestas: ciclo persistente de atividade/timer da Spec 015 é parcial; feedback/adaptação da Spec 016 é planejado; não há calendário externo, notificações nem métricas operacionais consolidadas. Os endpoints públicos têm apenas verificação pontual HTTP; cadastro público depende de `ALLOW_REGISTRATION`.
