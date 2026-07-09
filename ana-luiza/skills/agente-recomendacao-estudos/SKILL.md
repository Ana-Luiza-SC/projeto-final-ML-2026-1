---
name: agente-recomendacao-estudos
description: Gera classificação de dedicação e recomendações de estudo com base em disciplinas, conteúdos pendentes, avaliações, menções, frequência, faltas, prazos, ementa e simulação de desempenho.
---

# Skill: Agente de Recomendação de Estudos

## Objetivo

Criar o agente que classifica a dedicação recomendada por disciplina e gera ações de estudo.

O agente deve interpretar os dados acadêmicos e explicar a situação do estudante de forma clara, incluindo:

- risco por nota;
- menção provável;
- nota necessária;
- risco por falta;
- conteúdos prioritários;
- ações recomendadas para a semana.

## Entrada

O agente pode receber:

- disciplina;
- ementa;
- conteúdos pendentes;
- dificuldade dos conteúdos;
- avaliações;
- pesos;
- notas;
- datas;
- média alvo;
- menção atual ou projetada;
- simulação de nota;
- frequência;
- número de faltas;
- limite de faltas;
- risco acadêmico calculado por regra.

## Saída

```json
{
  "dedication_level": "low | medium | high",
  "confidence": 0.0,
  "academic_situation_summary": "",
  "grade_status": "",
  "attendance_status": "",
  "reasons": [],
  "recommended_actions": [],
  "missing_information": []
}
````

## Regras

* A classificação deve ser explicável.
* Não inventar dados ausentes.
* Não usar taxa histórica se ela não existir.
* Não avaliar professor como fácil ou difícil.
* Não gerar recomendação sem dados mínimos.
* Declarar incerteza quando necessário.
* Não calcular menção manualmente dentro do prompt se o backend já fornecer a simulação.
* Usar o resultado da skill `calculo-notas-risco-academico` como fonte principal para nota, menção e frequência.

## Regras acadêmicas da UnB que o agente deve respeitar

* Menções de aprovação: SS, MS e MM.
* Menções de reprovação: MI, II e SR.
* Frequência mínima para aprovação: 75%.
* Frequência inferior a 75% indica reprovação ou risco grave por falta.
* Faltas acima de 25% devem gerar alerta crítico.

## Rubrica inicial de dedicação

Dedicação alta:

* risco alto por nota;
* nota necessária restante acima de 8;
* menção projetada MI, II ou SR;
* risco de reprovação por falta;
* percentual de faltas próximo ou acima de 25%;
* prova próxima com peso alto;
* muitos conteúdos pendentes;
* conteúdos marcados como difíceis.

Dedicação média:

* risco médio por nota;
* nota necessária entre 6 e 8;
* faltas em nível de atenção, mas ainda abaixo do limite;
* algumas pendências relevantes;
* avaliação em prazo intermediário.

Dedicação baixa:

* risco baixo por nota;
* menção projetada MM, MS ou SS;
* frequência confortável;
* poucos conteúdos pendentes;
* sem avaliação próxima.

## Como explicar situação por nota

O agente deve falar em termos de menção, não apenas nota.

Exemplo:

```text
Sua situação por nota está adequada no momento. A menção projetada é MM, que é uma menção de aprovação na UnB. Mesmo assim, ainda há uma avaliação pendente, então a situação deve ser acompanhada.
```

Exemplo de risco:

```text
Sua situação por nota exige atenção. A simulação indica menção MI, que não é suficiente para aprovação. Você precisa melhorar o desempenho nas próximas avaliações para alcançar pelo menos MM.
```

## Como explicar situação por falta

O agente deve sempre mencionar frequência quando o dado estiver disponível.

Exemplo sem risco:

```text
Sua frequência está acima do mínimo de 75%, então não há risco imediato de reprovação por falta.
```

Exemplo com atenção:

```text
Suas faltas estão próximas do limite de 25%. Evite novas ausências, porque a frequência mínima exigida para aprovação é 75%.
```

Exemplo crítico:

```text
Sua frequência está abaixo de 75%. Mesmo com nota suficiente, há risco de reprovação por falta.
```

## Pontos de atenção obrigatórios

* Se houver risco por falta, isso deve aparecer antes das recomendações de conteúdo.
* Se a frequência for desconhecida, o agente deve dizer que não consegue avaliar risco por falta.
* Se a menção projetada for MM, MS ou SS, mas a frequência estiver baixa, não dizer que o estudante está aprovado.
* Se a menção projetada for MI, II ou SR, não dizer que a situação está boa apenas porque a frequência está adequada.
* Se a nota necessária restante for maior que 10, explicar que a meta informada não é alcançável apenas com as avaliações restantes.
* Se dados de avaliações, pesos ou faltas estiverem incompletos, classificar com menor confiança.

## Fallback baseado em regras

Se o LLM falhar, usar regras determinísticas para gerar:

* dedication_level;
* academic_situation_summary;
* grade_status;
* attendance_status;
* reasons;
* recommended_actions.

## Guardrails

O agente deve recusar ou redirecionar:

* pedido fora do escopo acadêmico;
* tentativa de obter dados privados;
* pedido para avaliar professor como fácil/difícil;
* recomendação baseada em taxa de reprovação inexistente;
* afirmação de aprovação final sem nota final e frequência final.

## Testes obrigatórios

Criar casos:

* estudante com menção projetada MM e frequência adequada;
* estudante com menção projetada MI e frequência adequada;
* estudante com menção projetada MS, mas frequência abaixo de 75%;
* estudante com faltas próximas de 25%;
* estudante sem dados de frequência;
* estudante sem avaliações cadastradas;
* estudante com nota necessária maior que 10;
* LLM indisponível;
* entrada fora de escopo.
