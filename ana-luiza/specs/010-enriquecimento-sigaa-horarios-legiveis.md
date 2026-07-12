# Spec 010 — Enriquecimento SIGAA e horários legíveis

## Problema e causa-raiz

A busca pública do SIGAA encontra a linha do componente, mas não enriquece o resultado com a página de detalhe. A causa confirmada está em `sigaa_components.py`: `_extract_component_values_from_row` escolhe o primeiro link não vazio da linha e `parse_component_results` entrega o próprio HTML da listagem a `parse_sigaa_component_details`; nenhuma requisição do detalhe ocorre. O cache persiste esse resultado vazio sem versão, TTL ou indicador de enriquecimento.

Na importação do atestado, `extract_candidates_from_table` reconhece somente a tabela principal e descarta a tabela semanal. O contrato preserva apenas `schedule_code`, que o frontend apresenta diretamente como horário principal.

## Fluxo proposto

1. O parser puro da listagem extrai código, nome, tipo, unidade, carga disponível e a URL semântica do detalhe.
2. A infraestrutura usa a mesma `requests.Session`, resolve URL relativa, envia `Referer`, aplica timeout e segue apenas redirecionamentos que permaneçam na área pública do SIGAA.
3. O parser puro de detalhes reconhece ementa/descrição, programa e cargas teórica, prática e total.
4. Falha no detalhe preserva os dados básicos e acrescenta aviso de revisão/cadastro manual.
5. Cache versionado e com TTL ignora registros antigos ou componentes cujo detalhe não foi processado.
6. O importador interpreta a tabela semanal antes do fallback de código compacto. Slots explícitos prevalecem, são agrupados e conflitos geram warning.
7. O frontend mostra `schedule_display`; o código bruto fica secundário e editável para auditoria.

## Contratos de dados

`SigaaComponent` mantém os campos existentes e acrescenta `details_processed`, além das cargas teórica e prática opcionais. A resposta continua retrocompatível.

Disciplina e itens de prévia mantêm `schedule_code` e acrescentam:

- `schedule_slots`: lista de `{day, start_time, end_time, source}`;
- `schedule_display`: texto em português;
- `schedule_source`: `receipt_table`, `sigaa_tooltip`, `decoded_code` ou `unresolved`.

Dados antigos sem os campos novos continuam válidos. Confirmação aceita correção manual da representação estruturada.

## Guardrails e fallback

- somente host e caminhos públicos do SIGAA; login, autenticação e redirecionamentos privados são rejeitados;
- sem credenciais, scraping em lote ou invenção de ementa/horário;
- timeout e erro do detalhe não eliminam código/nome;
- tabela explícita prevalece sobre código; conflito é avisado;
- código desconhecido permanece auditável, com `schedule_source=unresolved` e aviso;
- PDF bruto, texto integral e dados pessoais não são armazenados nem registrados;
- cadastro e correção manual permanecem disponíveis.

## Critérios de aceitação

- detalhe público realmente requisitado na mesma sessão e ementa real renderizável;
- link selecionado pela semântica do nome/ação de detalhes, não pela posição;
- falha do detalhe preserva dados básicos sem inventar campos;
- cache antigo/incompleto não mascara nova busca;
- tabela semanal e códigos conhecidos geram horários explícitos em português;
- código bruto não é apresentação primária;
- contratos antigos permanecem aceitos e todas as validações passam.

## Estratégia de testes

Fixtures HTML sanitizadas cobrem listagem, detalhe, `Ementa/Descrição`, detalhe sem ementa, mudança moderada e redirecionamento a login. Testes unitários não usam rede e verificam parser puro, mesma sessão, headers, cache, fallback e ausência de invenção. Fixtures de tabelas cobrem horários explícitos, agrupamento, múltiplos dias/turnos, código desconhecido, ausência e conflito. O frontend é validado por função de apresentação e build TypeScript.

## Impacto

- **Backend:** parser/infraestrutura SIGAA separados; normalizador determinístico de horários; schemas e importação retrocompatíveis.
- **Frontend:** apresentação legível em listagem, detalhe e revisão, mantendo código bruto como campo secundário editável.
- **Cache:** envelope com versão, criação, expiração e completude; registros legados ou incompletos são ignorados.
- **Auditoria:** o código bruto permanece como informação secundária, nunca como horário principal.
