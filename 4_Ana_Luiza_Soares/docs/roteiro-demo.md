# Roteiro de demonstração — 4 a 6 minutos

1. Abrir a landing page e explicar o problema: organizar disciplinas, avaliações, conteúdos e prazos.
2. Fazer login com o usuário de demonstração configurado por `EMAIL_TESTE`/`SENHA_TESTE`.
3. Abrir Disciplinas e mostrar uma disciplina com dados de ementa/plano.
4. Mostrar plano de ensino confirmado e avaliações cadastradas.
5. Abrir conteúdos, destacando hierarquia e associação direta/herdada com avaliação.
6. Abrir Calendário: mostrar mês, evento de avaliação sincronizado e evento manual.
7. Usar “Extrair eventos do plano de ensino”, revisar preview e explicar que nada é salvo sem confirmação.
8. Em Planejamento, informar janelas, revisar prioridade/demanda/capacidade, gerar preview e confirmar blocos; mostrar os blocos no calendário antes das provas.
9. Mostrar recomendação/agente e evidências usadas: disciplina, avaliação, data, peso, conteúdo, estado e dificuldade.
10. Demonstrar fallback/guardrail: sem plano confirmado ou sem LLM, o sistema retorna orientação amigável sem inventar dados.
11. Explicar que bloco planejado reserva tempo, mas não comprova uma atividade executada; atividade/timer e adaptação pós-estudo permanecem fora da implementação atual.
