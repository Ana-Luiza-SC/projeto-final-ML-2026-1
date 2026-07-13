# Spec 008 — Importação de disciplinas pelo comprovante de matrícula — MVP

## 1. Título

Importação de disciplinas pelo comprovante de matrícula do SIGAA/UnB — MVP.

## 2. Objetivo

Especificar a próxima fatia do EstudaUnB: permitir que o estudante envie um comprovante de matrícula em PDF, revise as disciplinas reconhecidas e confirme explicitamente o cadastro em lote.

O sistema deve extrair localmente os dados acadêmicos necessários, normalizar códigos e nomes, consultar opcionalmente a fonte pública de componentes do SIGAA para enriquecer ou validar os itens e devolver um resultado auditável. Nenhuma disciplina pode ser cadastrada apenas pelo upload do arquivo.

Esta especificação preserva o cadastro manual existente e a integração pública atual com o SIGAA Componentes.

## 3. Problema que esta fatia resolve

O estudante atualmente precisa cadastrar disciplinas uma a uma, mesmo quando já possui um comprovante de matrícula com a grade do semestre. A importação automática reduz esse trabalho, mas precisa permitir revisão humana porque PDFs podem variar, conter atividades acadêmicas, ter campos ambíguos ou apresentar dados incompletos.

O MVP resolve o fluxo:

```text
PDF enviado
→ validação do arquivo
→ extração local
→ identificação de códigos e nomes
→ normalização
→ enriquecimento/validação opcional no SIGAA público
→ pré-visualização editável
→ confirmação explícita
→ cadastro em lote idempotente
→ relatório de cadastrados, duplicados e rejeitados
```

## 4. Contexto e compatibilidade

Esta spec assume que já existem:

- `POST /api/disciplines` para cadastro manual;
- `GET /api/disciplines` para listagem;
- `GET /api/sigaa/components/search` para consulta pública por código ou nome;
- `PATCH /api/disciplines/{discipline_id}/sigaa-component` para associar dados públicos encontrados;
- armazenamento atual das disciplinas;
- frontend React + Vite + TypeScript com navegação por hash.

A implementação deve reutilizar esses contratos e componentes sempre que possível. Não deve reescrever o parser ou o scraper do SIGAA Componentes já existente, nem introduzir login, senha ou consulta a páginas autenticadas.

## 5. Histórias de usuário

### US-01 — Enviar comprovante

Como estudante, quero enviar meu comprovante de matrícula em PDF para identificar minhas disciplinas sem preencher todos os campos manualmente.

### US-02 — Revisar extração

Como estudante, quero visualizar os itens extraídos antes de qualquer persistência, para corrigir dados incorretos ou remover itens que não desejo cadastrar.

### US-03 — Corrigir item

Como estudante, quero editar o código, nome e metadados acadêmicos de um item reconhecido ou ambíguo antes da confirmação.

### US-04 — Confirmar em lote

Como estudante, quero confirmar vários itens revisados em uma única ação, recebendo um resultado separado para cadastrados, duplicados e rejeitados.

### US-05 — Recuperar de falha

Como estudante, quero continuar usando o cadastro manual quando o PDF for inválido, a extração falhar ou o SIGAA estiver indisponível.

### US-06 — Proteger meus dados

Como estudante, quero que o PDF temporário seja descartado após o processamento e que meu nome, matrícula e conteúdo integral do documento não apareçam nos logs.

## 6. Escopo do MVP

Implementar:

- upload de um PDF por requisição;
- validação de tipo, tamanho, assinatura e estrutura básica do PDF;
- processamento local do conteúdo textual;
- identificação de disciplinas regulares na tabela principal;
- identificação de código, nome, turma, status e código de horário quando disponíveis;
- distinção entre disciplina regular e atividade acadêmica não disciplinar;
- normalização de código, nome, espaços, acentos e campos opcionais;
- pré-visualização editável e sem persistência automática;
- consulta opcional ao endpoint público existente do SIGAA Componentes;
- confirmação explícita e cadastro em lote;
- detecção de duplicatas por código normalizado;
- sucesso parcial com relatório por item;
- fallback para cadastro manual;
- logs estruturados de operação, latência, resultado e fallback sem dados pessoais;
- testes com fixtures anonimizadas.

## 7. Fora do escopo

Não implementar nesta fatia:

- login no SIGAA ou recebimento de senha;
- scraping de páginas autenticadas;
- importação de histórico escolar, notas, frequência ou dados financeiros;
- armazenamento permanente do PDF original;
- edição ou exclusão de disciplinas já cadastradas;
- calendário completo ou criação de eventos;
- importação automática de atividades acadêmicas como disciplinas;
- confirmação automática após upload;
- processamento de múltiplos PDFs na mesma requisição;
- OCR como caminho principal ou aplicado quando a camada textual já for utilizável;
- sincronização contínua com o SIGAA;
- mudança do contrato dos endpoints existentes;
- novo banco de dados ou framework de parsing sem necessidade concreta.

## 8. Regras de negócio

### 8.1 Fonte de verdade e confirmação

- O PDF é uma fonte de entrada, não uma autorização para cadastrar.
- O sistema deve sempre produzir uma pré-visualização antes do cadastro.
- O cadastro somente ocorre após uma chamada explícita de confirmação que referencia a pré-visualização válida.
- O frontend deve deixar claro que a confirmação é a etapa que persiste os itens.
- O cadastro manual continua disponível em qualquer etapa de erro ou revisão.

### 8.2 Código e nome

- Quando houver código no documento, ele é o identificador principal de reconciliação.
- O nome sozinho não pode substituir silenciosamente um código reconhecido.
- Item sem código pode ser exibido como `ambiguous` ou `recognized_without_code`, mas não deve ser cadastrado automaticamente.
- Nome e código corrigidos pelo usuário devem ser validados antes da confirmação.
- O sistema não deve inventar código, nome, professor, turma ou horário.

### 8.3 Disciplinas versus atividades acadêmicas

- Disciplinas regulares devem ser separadas de monitoria, orientação, estágio, atividade de extensão e outras atividades acadêmicas quando a estrutura do comprovante permitir.
- Atividades não disciplinares não devem ser cadastradas como `Discipline` sem revisão explícita e sem compatibilidade com o contrato atual.
- Itens classificados como atividade devem aparecer no relatório para que o usuário saiba por que não foram importados.

### 8.4 Duplicatas

- A comparação primária deve usar o código normalizado, ignorando diferenças de caixa, espaços e pontuação irrelevante.
- Uma disciplina já cadastrada com o mesmo código deve ser marcada como `duplicate` e não pode gerar novo registro.
- Se não houver código, a comparação por nome normalizado é apenas auxiliar e deve resultar em `ambiguous` quando houver risco de colisão.
- Itens duplicados não devem sobrescrever dados manuais existentes.
- A confirmação deve ser idempotente para o mesmo identificador de pré-visualização.
- Se dois itens da mesma pré-visualização tiverem o mesmo código após normalização, somente um poderá ser confirmado; os demais serão rejeitados como duplicados internos.

### 8.5 Sucesso parcial

- A falha de um item não deve impedir o cadastro de itens válidos e confirmados.
- O relatório deve informar `created`, `duplicate`, `rejected` e `skipped` por item.
- Uma resposta de sucesso parcial não deve ser apresentada como erro total.
- Se nenhum item for elegível, a confirmação deve retornar um relatório vazio de cadastrados e mensagem amigável, sem criar lista silenciosa.

## 9. Fluxo principal

1. O usuário abre a tela de importação.
2. O frontend permite selecionar um único arquivo PDF.
3. O backend valida tamanho, tipo declarado, assinatura `%PDF-` e estrutura mínima.
4. O backend gera um `preview_id` e processa o conteúdo localmente.
5. O parser extrai candidatos da tabela principal e marca atividades acadêmicas separadamente.
6. O normalizador produz itens estruturados com origem, confiança e warnings.
7. Para candidatos com código ou nome suficiente, o backend pode consultar o endpoint público atual do SIGAA Componentes, usando o cache existente e timeout limitado.
8. O backend retorna a pré-visualização sem cadastrar nada.
9. O frontend mostra todos os itens, seus status, warnings e campos editáveis.
10. O usuário corrige, seleciona ou remove itens.
11. O usuário confirma explicitamente os itens elegíveis.
12. O backend revalida o `preview_id`, os campos editados e as duplicatas contra o armazenamento atual.
13. O backend cadastra os itens válidos em lote, sem sobrescrever registros existentes.
14. O backend retorna relatório de cadastrados, duplicados, rejeitados e warnings.
15. O frontend atualiza a listagem e mantém visível o relatório.

## 10. Fluxos alternativos e erros

### A1 — Arquivo ausente ou inválido

Retornar `422` com mensagem amigável e código de erro estável. Não iniciar extração, não persistir o arquivo e oferecer cadastro manual.

### A2 — PDF válido, mas sem texto extraível

Tentar OCR somente como fallback quando o PDF não possuir camada textual utilizável. Se o OCR não estiver disponível ou também não produzir conteúdo confiável, retornar erro controlado sem stack trace e informar o cadastro manual como alternativa.

### A3 — Nenhuma disciplina reconhecida

Retornar `200` com `status: no_items`, lista vazia e warning explícito. Não interpretar como sucesso de cadastro e não criar disciplinas.

### A4 — Item ambíguo

Exibir o item para correção, mas não permitir sua confirmação enquanto faltar o código ou nome mínimo exigido pelo contrato atual.

### A5 — SIGAA indisponível

Manter a extração local e marcar o enriquecimento como `not_available`. O usuário pode revisar e confirmar dados extraídos; dados não encontrados não devem ser inventados.

### A6 — SIGAA não encontrou componente

Manter o item local com status `not_found`, warning e campos públicos ausentes. O usuário pode corrigir ou continuar somente se o código e nome forem suficientes para o cadastro atual.

### A7 — Usuário cancela ou remove itens

Nenhuma alteração persistente é feita para itens cancelados ou removidos. O PDF e os dados temporários são descartados conforme o ciclo de vida definido nesta spec.

### A8 — Pré-visualização expirada ou desconhecida

Retornar `409` ou `404`, conforme o padrão adotado, com mensagem para repetir a importação. Não aceitar confirmação sem referência válida.

### A9 — Falha durante cadastro em lote

Preservar os resultados já processados de forma transacional por item, retornar sucesso parcial e registrar somente a categoria do erro. Não devolver stack trace.

## 11. Contrato de upload

### Endpoint

```http
POST /api/import/matricula-pdf/preview
Content-Type: multipart/form-data
```

Campo obrigatório:

- `file`: arquivo PDF do comprovante de matrícula.

Limites do MVP:

- exatamente um arquivo;
- extensão `.pdf` apenas como sinal auxiliar, nunca como validação única;
- `Content-Type` aceito: `application/pdf`, sujeito à validação da assinatura;
- tamanho máximo configurável, recomendado `10 MiB`;
- arquivo vazio rejeitado;
- número máximo de páginas configurável, recomendado `30`;
- PDF criptografado, corrompido ou estruturalmente inválido rejeitado;
- o backend deve consumir o stream com limite, evitando leitura ilimitada em memória.

Resposta não deve incluir o texto integral extraído nem dados pessoais do cabeçalho do documento.

## 12. Contrato de pré-visualização

### Endpoint

```http
POST /api/import/matricula-pdf/preview
```

Resposta conceitual:

```json
{
  "status": "success",
  "preview_id": "uuid",
  "expires_at": "2026-07-10T15:30:00Z",
  "items": [
    {
      "preview_item_id": "uuid",
      "item_type": "discipline",
      "status": "recognized",
      "selected": true,
      "code": "FGA0000",
      "name": "Disciplina de Exemplo",
      "class_code": "01",
      "schedule_code": "24M12",
      "source": "pdf_local",
      "sigaa_lookup": "found",
      "confidence": "high",
      "warnings": []
    }
  ],
  "summary": {
    "recognized_count": 1,
    "ambiguous_count": 0,
    "not_found_count": 0,
    "duplicate_count": 0,
    "activity_count": 0,
    "rejected_count": 0
  },
  "warnings": []
}
```

Status de item:

- `recognized`: código e nome suficientes e estrutura coerente;
- `ambiguous`: candidato incompleto, conflitante ou com baixa confiança;
- `not_found`: consulta pública não encontrou enriquecimento, sem significar que o item local seja inválido;
- `duplicate`: código já existe no cadastro atual ou se repete na pré-visualização;
- `activity`: item identificado como atividade acadêmica fora do cadastro de disciplina;
- `rejected`: item não atende às validações mínimas.

`not_found` deve ser diferenciado de `rejected`: a ausência no SIGAA público não autoriza descartar automaticamente um item local válido.

## 13. Contrato de edição e confirmação

### Edição da pré-visualização

O frontend pode editar apenas campos previstos no item: `code`, `name`, `class_code`, `schedule_code`, `local` e seleção. Os valores editados não devem incluir texto livre para criar entidades adicionais, professor ou ementa não presentes.

A implementação pode usar uma operação dedicada ou reenviar os itens no endpoint de confirmação. Em ambos os casos:

- o backend deve validar novamente os campos;
- o `preview_id` deve ser obrigatório;
- itens não pertencentes à pré-visualização devem ser rejeitados;
- a edição deve ser descartável antes da confirmação.

### Endpoint

```http
POST /api/import/matricula-pdf/confirm
Content-Type: application/json
```

Payload conceitual:

```json
{
  "preview_id": "uuid",
  "items": [
    {
      "preview_item_id": "uuid",
      "selected": true,
      "code": "FGA0000",
      "name": "Disciplina de Exemplo",
      "class_code": "01",
      "schedule_code": "24M12",
      "local": null
    }
  ]
}
```

Regras:

- `items` pode conter apenas itens da pré-visualização;
- `selected: false` significa explicitamente não cadastrar;
- itens `activity`, `rejected` ou `ambiguous` sem correção válida não podem ser criados;
- o backend deve reconsultar as duplicatas no momento da confirmação;
- o endpoint não deve aceitar PDF, nome ou código fora do item revisado;
- repetir a mesma confirmação não deve duplicar registros.

Resposta conceitual:

```json
{
  "status": "partial_success",
  "preview_id": "uuid",
  "created": [
    {
      "preview_item_id": "uuid",
      "discipline_id": "uuid",
      "code": "FGA0000",
      "name": "Disciplina de Exemplo"
    }
  ],
  "duplicates": [],
  "rejected": [],
  "skipped": [],
  "warnings": [],
  "summary": {
    "created_count": 1,
    "duplicate_count": 0,
    "rejected_count": 0,
    "skipped_count": 0
  },
  "request_id": "uuid"
}
```

Status de resposta:

- `success`: todos os itens selecionados elegíveis foram cadastrados;
- `partial_success`: ao menos um item foi cadastrado e outro foi duplicado, rejeitado ou falhou;
- `no_items`: nenhum item foi selecionado para cadastro;
- `error`: falha da operação sem cadastro confirmado; mensagem sanitizada.

## 14. Schemas tipados

Os nomes podem ser adaptados ao padrão real do backend, mas devem existir tipos equivalentes para:

- `MatriculaPdfPreviewRequest` ou formulário multipart;
- `ImportPreviewItem`;
- `ImportPreviewSummary`;
- `MatriculaPdfPreviewResponse`;
- `ImportConfirmationItem`;
- `MatriculaImportConfirmRequest`;
- `ImportCreatedItem`;
- `ImportRejectedItem`;
- `MatriculaImportConfirmResponse`.

Validações mínimas:

- código normalizado com tamanho plausível e caracteres permitidos;
- nome não vazio e com limite de tamanho;
- `preview_id` e `preview_item_id` válidos;
- listas com limites de cardinalidade;
- enumerações fechadas para status e origem;
- campos extras rejeitados conforme o padrão tipado atual;
- nenhum campo de autenticação, matrícula ou conteúdo bruto no contrato público.

## 15. Extração local

### Estratégia

- Usar biblioteca já presente ou aprovada pelo projeto, como `pdfplumber` ou `PyMuPDF`.
- Processar páginas localmente no backend.
- Priorizar a tabela principal de componentes, associando colunas de código, componente/docente, turma, status e horário.
- Usar o código de componente, no padrão `[A-Z]{3}\d{4}`, como âncora primária e segmentar o texto entre um código e o código seguinte.
- Reconstruir nomes quebrados em múltiplas linhas dentro do bloco, sem incorporar docente, status ou metadados.
- Validar disciplinas regulares pela presença de `Tipo: DISCIPLINA`; monitoria, orientação e outras atividades devem seguir como itens separados e não selecionáveis.
- Excluir cabeçalhos, rodapés, texto de autenticação e a tabela semanal de horários da criação de candidatos.
- Aplicar OCR somente como fallback para PDF sem camada textual utilizável; indisponibilidade ou baixa confiança deve produzir erro amigável e cadastro manual.

### Candidatos

Um candidato deve guardar internamente apenas o necessário para a pré-visualização:

- código bruto e normalizado;
- nome bruto e normalizado;
- turma;
- código de horário;
- tipo de item;
- página de origem apenas se útil para auditoria interna, sem expor dados pessoais;
- confiança e warnings.

O parser não deve retornar nem registrar o texto integral da página.

### Identificação de código

- Preferir padrões de código curricular existentes no contexto da UnB, com regex configurável e testada.
- Não aceitar qualquer sequência numérica como código sem contexto de coluna.
- Preservar o código original somente quando necessário para revisão, normalizando uma cópia para comparação.
- Se houver mais de um código plausível na linha, marcar como `ambiguous`.

## 16. Normalização

A normalização deve ser determinística, idempotente e testável:

- remover espaços duplicados e espaços nas extremidades;
- normalizar caixa para comparação;
- normalizar Unicode/acentos apenas para comparação de nomes, preservando a forma exibida quando possível;
- normalizar separadores e pontuação de códigos sem alterar o valor acadêmico;
- normalizar `class_code` e `schedule_code` sem inventar valores ausentes;
- converter valores vazios para `null`;
- remover duplicatas internas após normalização;
- manter origem e warnings para que o usuário entenda a transformação.

O nome normalizado serve para comparação e busca; o cadastro deve exibir o nome revisado pelo usuário ou o nome extraído, nunca um nome criado pelo LLM.

## 17. Integração opcional com SIGAA

- Reutilizar `GET /api/sigaa/components/search` e seus tipos existentes.
- Consultar primeiro por código quando houver código confiável.
- Consultar por nome somente quando o código estiver ausente ou quando for necessário validar uma inconsistência.
- Usar cache local já previsto pela integração SIGAA.
- Aplicar timeout e tratar indisponibilidade como fallback, sem bloquear a extração local.
- Considerar `found`, `not_found` e `error` resultados diferentes.
- O retorno público do SIGAA pode preencher nome, carga horária, ementa e programa somente quando realmente encontrados.
- Não substituir silenciosamente o nome extraído por resultado aproximado sem marcar a origem e permitir revisão.
- Não consultar área autenticada, não solicitar credenciais e não implementar novo scraping nesta fatia.

## 18. Persistência e ciclo de vida do arquivo

- O arquivo deve ser recebido em área temporária não pública.
- O processamento deve ocorrer em streaming ou com limite de tamanho.
- O PDF bruto não deve ser salvo no armazenamento permanente.
- Arquivo temporário, buffers e metadados desnecessários devem ser removidos em `finally`, inclusive em erro e cancelamento.
- A pré-visualização deve armazenar apenas dados estruturados mínimos e ter TTL curto, recomendado 15 minutos.
- Após confirmação, expiração ou cancelamento, os dados temporários devem ser descartados.
- A persistência deve conter somente disciplinas confirmadas e campos acadêmicos necessários ao contrato atual.
- Não persistir objetivo, texto integral, cabeçalho do comprovante ou identificadores pessoais sem requisito explícito.
- Fixtures de teste devem ser anonimizadas e PDFs reais não devem ser commitados.

## 19. Guardrails

### Entrada

- rejeitar arquivo ausente, vazio, acima do limite ou com tipo/assinatura incompatíveis;
- rejeitar PDF corrompido, criptografado ou sem estrutura mínima;
- limitar páginas, itens extraídos e tempo de processamento;
- rejeitar confirmação sem `preview_id` válido;
- rejeitar itens de outra pré-visualização;
- rejeitar campos extras ou tipos incorretos;
- validar código e nome antes do cadastro;
- impedir cadastro de atividade acadêmica como disciplina sem regra explícita;
- impedir duplicação por código normalizado;
- manter cadastro manual disponível.

### Saída

- nenhum item cadastrado antes da confirmação;
- nenhum item sem código/nome mínimo persistido;
- nenhuma disciplina fora da pré-visualização confirmada;
- nenhum dado público do SIGAA inventado;
- status de item sempre explícito;
- falhas parciais preservadas no relatório;
- respostas de erro sem stack trace, caminho local, conteúdo do PDF ou segredo;
- logs sem nome, matrícula, código de verificação, texto integral ou PDF.

## 20. Fallbacks

- PDF inválido ou não extraível: cadastro manual.
- Parser sem candidatos: revisão manual/cadastro manual.
- SIGAA indisponível: continuar com dados locais e warning.
- SIGAA sem resultado: manter item como `not_found` e permitir revisão.
- Pré-visualização expirada: solicitar novo upload.
- Falha de um item no lote: cadastrar itens válidos e reportar os demais.
- Falha interna antes de qualquer criação: retornar erro sanitizado e não apresentar sucesso.

## 21. Observabilidade

Registrar eventos estruturados com:

- `request_id` e, quando aplicável, `preview_id` sem associá-los a dados pessoais;
- duração da validação, extração e consulta SIGAA;
- tamanho do arquivo em bytes e número de páginas, sem o conteúdo;
- contagem de candidatos, reconhecidos, ambíguos, não encontrados, duplicados e rejeitados;
- quantidade criada na confirmação;
- uso de cache e fallback do SIGAA;
- categoria do erro: `invalid_file`, `parse_error`, `sigaa_unavailable`, `preview_expired`, `duplicate`, `validation_error` ou equivalente;
- resultado final e sucesso parcial.

Não registrar:

- PDF, nome do arquivo se contiver identificação pessoal, texto extraído ou screenshots;
- nome, matrícula, CPF, código de verificação ou outros dados pessoais;
- headers de autenticação, senhas ou segredos;
- prompts, respostas completas de LLM ou conteúdo acadêmico desnecessário;
- stack trace em resposta ao cliente.

## 22. Frontend mínimo

Adicionar navegação mínima para uma tela de importação, preservando o shell atual.

A tela deve conter:

- seletor de PDF com limite e tipo visíveis;
- estado de envio e processamento;
- mensagem clara para PDF inválido ou extração indisponível;
- tabela/cartões de pré-visualização com código, nome, turma, horário, origem e status;
- checkbox para seleção dos itens elegíveis;
- edição de código e nome, com validação local básica;
- remoção ou desmarcação de item;
- destaque visual para `recognized`, `ambiguous`, `not_found`, `duplicate`, `activity` e `rejected`;
- botão separado “Confirmar cadastro”;
- confirmação desabilitada sem itens válidos selecionados;
- relatório final de cadastrados, duplicados e rejeitados;
- link para cadastro manual quando o PDF falhar;
- preservação da pré-visualização durante erros de confirmação recuperáveis;
- atualização da listagem de disciplinas somente após confirmação.

Não exibir JSON cru, conteúdo integral do PDF, stack trace ou dados pessoais extraídos que não sejam necessários para a revisão.

## 23. Testes esperados

### Backend e parser

1. PDF válido com uma disciplina regular.
2. PDF válido com várias disciplinas.
3. Extração de código, nome, turma e horário.
4. Separação de atividade acadêmica.
5. PDF vazio, truncado, corrompido, criptografado e com tipo incorreto.
6. Arquivo acima do limite e excesso de páginas.
7. PDF sem camada textual.
8. Normalização idempotente de código e nome.
9. Código ausente ou múltiplos códigos ambíguos.
10. Cabeçalhos e linhas repetidas ignorados.
11. Pré-visualização não cria disciplinas.
12. Pré-visualização expirada ou `preview_id` inexistente.
13. Edição válida antes da confirmação.
14. Item removido ou desmarcado não cadastrado.
15. Confirmação com item de outra pré-visualização rejeitada.
16. Duplicata por código já cadastrado.
17. Duplicata interna na mesma pré-visualização.
18. Nome parecido sem código tratado como ambíguo.
19. Cadastro em lote totalmente bem-sucedido.
20. Cadastro em lote com sucesso parcial.
21. Repetição da confirmação não cria duplicatas.
22. Campos extras e tipos inválidos rejeitados.
23. SIGAA encontrado, não encontrado, indisponível e timeout.
24. Cache do SIGAA reutilizado sem nova consulta indevida.
25. Falha de SIGAA não impede revisão local.
26. Arquivo temporário removido em sucesso e em erro.
27. Logs não contêm texto integral, nome, matrícula ou conteúdo pessoal.
28. Respostas de erro não contêm stack trace.

### Frontend

- carregamento e validação do seletor de arquivo;
- loading durante preview;
- renderização de itens reconhecidos e ambíguos;
- edição e exclusão antes da confirmação;
- botão de confirmação separado do upload;
- exibição de duplicados e falhas parciais;
- preservação dos itens após falha de confirmação;
- fallback para cadastro manual;
- atualização da lista após sucesso;
- não exibição de JSON cru ou stack trace.

Usar fixtures anonimizadas. Os testes não devem depender do SIGAA real nem enviar PDF a serviço externo.

## 24. Critérios de aceitação

Esta spec será considerada aceita quando:

- um comprovante PDF válido puder ser enviado;
- o backend validar tipo, tamanho e estrutura antes de extrair;
- as disciplinas extraídas forem exibidas antes de qualquer cadastro;
- o usuário puder corrigir ou excluir um item;
- o usuário precisar confirmar explicitamente o cadastro em lote;
- códigos forem usados como identificador principal quando disponíveis;
- disciplinas já cadastradas não forem duplicadas nem sobrescritas;
- itens reconhecidos, ambíguos, não encontrados e duplicados forem diferenciados;
- falhas parciais forem comunicadas sem perder itens válidos;
- um item sem dados mínimos não for persistido silenciosamente;
- o arquivo temporário for removido após processamento, expiração ou erro;
- o conteúdo integral do PDF e dados pessoais não aparecerem nos logs;
- a integração SIGAA pública atual continuar funcional;
- o cadastro manual continuar disponível como fallback;
- a resposta de confirmação informar cadastrados, duplicados e rejeitados;
- a tela permitir revisão antes da confirmação;
- testes automatizados cobrirem parser, normalização, duplicatas, fallback, privacidade e contrato;
- a aplicação funcionar sem login ou senha do SIGAA.

## 25. Próximos passos

1. Implementar schemas e endpoints de pré-visualização e confirmação.
2. Criar parser local com fixtures anonimizadas do comprovante.
3. Criar normalizador determinístico e detector de duplicatas.
4. Integrar a consulta opcional ao SIGAA Componentes existente.
5. Implementar TTL e limpeza garantida dos temporários.
6. Adicionar a tela de revisão e confirmação no frontend.
7. Executar testes de segurança, contrato e sucesso parcial.
8. Validar o fluxo completo em Docker sem persistir o PDF original.
