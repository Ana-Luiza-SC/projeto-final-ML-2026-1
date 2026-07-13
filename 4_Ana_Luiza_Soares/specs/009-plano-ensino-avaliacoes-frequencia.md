# Spec 009 — Plano de ensino, avaliações futuras e frequência por disciplina

## 1. Objetivo

Organizar a disciplina em visão geral, avaliações, frequência, plano de ensino e recomendações, permitindo importar um PDF de plano de ensino com revisão humana antes de persistir dados estruturados.

## 2. Escopo

- pré-visualizar e confirmar dados explicitamente presentes em plano de ensino;
- armazenar dados estruturados confirmados, nunca o PDF bruto;
- distinguir avaliações `planned`, `completed` e `cancelled`;
- permitir avaliação futura sem nota e conclusão posterior com nota;
- registrar faltas por ocorrência e ajuste acumulado;
- usar avaliações futuras confirmadas como fator determinístico de prioridade no plano semanal;
- preservar cadastro manual, SIGAA, simulação e recomendação existentes.

OCR é somente fallback opcional para documento sem texto utilizável. Ausência de OCR deve retornar erro amigável.

## 3. Unidade acadêmica

O sistema adota **hora-aula** como unidade da carga horária e das faltas porque o modelo existente já possui `total_class_hours` e `missed_class_hours`. `workload_hours` é interpretado como carga em horas-aula no produto.

Não converter hora-aula em hora-relógio, encontros ou créditos. Uma disciplina de 30 horas-aula admite exatamente `30 × 0,25 = 7,5` horas-aula de ausência. Valores decimais são preservados.

Carga semanal só é exibida quando `term_weeks` for explicitamente informado: `workload_hours / term_weeks`.

## 4. Plano de ensino

`POST /api/disciplines/{id}/course-plan/preview` recebe um PDF, valida tamanho/assinatura, extrai camada textual local e retorna prévia com TTL.

Campos possíveis: código, nome, semestre, carga horária, objetivos, conteúdos, cronograma, avaliações explícitas e bibliografia. Campos ausentes permanecem nulos ou vazios. Avaliação sem data ou peso suficiente recebe `requires_review`.

`POST /api/disciplines/{id}/course-plan/confirm` revalida a prévia editada e persiste somente dados estruturados. `GET` consulta e `DELETE` remove os dados estruturados. Temporários são removidos em `finally`.

## 5. Avaliações

Cada avaliação contém nome, data, peso opcional, nota opcional, tópicos, observação, origem (`manual` ou `course_plan`) e status.

- `planned`: nota deve ser vazia;
- `completed`: nota é obrigatória;
- `cancelled`: não participa da simulação;
- somente avaliações com nota contribuem para a contribuição atual;
- peso ausente gera informação incompleta;
- soma diferente de 100% gera warning.

Endpoints permitem listar, criar, atualizar, concluir e excluir.

## 6. Frequência

Ocorrência: data, quantidade positiva de horas-aula e observação opcional. Data + quantidade iguais não podem se repetir. Ajuste manual acumulado é alternativo às ocorrências e fica explicitamente identificado.

O resumo usa carga horária confirmada e soma das faltas: limite = carga × 25%; frequência = `1 - faltas / carga`; saldo = limite - faltas, sem arredondamento silencioso. Acima de 15% é atenção; acima de 25% é risco alto. Sem carga horária, o estado é desconhecido.

## 7. Planejamento e IA

Prioridade efetiva = prioridade informada mais bônus determinístico, limitada a 5:

- avaliação confirmada em até 7 dias: +2;
- em 8 a 14 dias: +1;
- demais casos: +0.

Avaliações canceladas, concluídas, ambíguas ou sem data não influenciam. A regra não elimina a sessão mínima de outra disciplina quando há disponibilidade suficiente.

O LLM não altera sessões. Pode apenas explicar dados confirmados. Sem chave ou resposta válida, o plano e recomendações usam fallback determinístico.

## 8. Privacidade e persistência

O armazenamento continua em memória e é perdido ao reiniciar o backend. Não persistir PDF, texto integral, prompt ou resposta integral do LLM. Logs contêm apenas IDs, contagens, método e latência.

## 9. Interface

A página da disciplina usa abas: Visão geral, Avaliações, Frequência, Plano de ensino e Recomendações. Formulários são abertos sob demanda. Dados temporários e confirmados têm estados distintos.

## 10. Testes e aceite

Cobrir extração explícita, documento sem avaliação/texto, revisão, temporários, ciclo das avaliações, pesos incompletos, carga de 30 horas-aula, faltas CRUD, duplicação, unidade desconhecida, prioridade por proximidade, fallback e contratos. Validar os fluxos no Docker e navegador sem dados pessoais.
