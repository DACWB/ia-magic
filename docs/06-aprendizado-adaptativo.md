# 📈 Sistema de Aprendizado Adaptativo

Como o sistema aprende e melhora com cada partida jogada.

## 🎯 Filosofia

Cada jogo é um **datapoint**. Após 10, 50, 100 jogos, temos padrões claros:
- Quais decks funcionam pra você
- Contra quais arquétipos você tem dificuldade
- Quando a IA errou (pra ela aprender também)

## 📊 Vetor de Deck (Sistema de Pontuação)

Cada deck que você usa tem um **vetor de performance**:

```json
{
  "deck_name": "Mono Red Aggro",
  "sessions_played": 15,
  "total_games": 47,
  "wins": 32,
  "losses": 15,
  "winrate": 0.68,
  "matchup_vectors": {
    "vs Domain Ramp": {
      "games": 12,
      "wins": 9,
      "vector": +0.75,
      "trend": "positive"
    },
    "vs Azorius Control": {
      "games": 8,
      "wins": 3,
      "vector": -0.375,
      "trend": "negative"
    }
  },
  "confidence_score": 0.85,
  "last_played": "2026-01-18",
  "recommended_for": ["Standard BO1", "Standard BO3"]
}
```

## 🔄 Como Vetores Evoluem

### Ganha:
```
Deck: Mono Red Aggro
Antes: winrate 68%, vector +0.36
Ganhou contra: Simic Ramp

Atualização:
- winrate: 32+1 / 47+1 = 33/48 = 0.6875
- Vector aumenta: +0.375
- Matchup vs Simic Ramp: +0.10
- Confiança nas suas jogadas: +0.02
```

### Perde:
```
Deck: Mono Red Aggro
Antes: winrate 68%, vector +0.36
Perdeu para: Azorius Control

Atualização:
- winrate: 32 / 48 = 0.6667
- Vector diminui: +0.35
- Matchup vs Azorius Control: -0.15
- Sistema aprende: "vs Control, precisa mudar approach"
```

## 🎯 Quando o Sistema TROCA de Deck

Sistema muda deck quando:

1. **Vector total < 0.4** por 5 sessões seguidas
2. **Matchup vs deck do meta atual** < 0.30
3. **Você pergunta**: `> qual meu melhor deck agora?`

Exemplo:
```
📊 ANÁLISE DE SESSÕES ÚLTIMAS 2 SEMANAS:

Mono Red Aggro:
- Winrate geral: 45% (⬇️ era 68%)
- vs Domain Ramp: 30% (piorando)
- Sistema detectou: meta mudou, mais controle

RECOMENDAÇÃO: Mudar para Azorius Control
- Você tem 92% das cartas
- Winrate esperado: 60%+ no meta atual

Quer trocar? (y/n)
```

## 🧠 Aprendizado da IA (Fine-Tuning Prático)

Sistema salva:
```sql
CREATE TABLE ia_decisions (
    id INTEGER PRIMARY KEY,
    game_id INTEGER,
    turn INTEGER,
    context_json TEXT,
    ia_recommendation TEXT,
    user_action TEXT,
    followed_recommendation BOOLEAN,
    outcome_win BOOLEAN,
    outcome_at_turn INTEGER,
    created_at DATETIME
);
```

Depois de N decisões, sistema analisa:
```
📊 ANÁLISE DE DECISÕES DA IA (últimos 30 dias):

Total: 342 recomendações
Você seguiu: 227 (66%)
Você ignorou: 115 (34%)

QUANDO SEGUIU: 158 ganhos / 227 = 70%
QUANDO IGNOROU: 76 ganhos / 115 = 66%

Conclusão: IA está +4% acima da sua intuição

MELHORES RECOMENDAÇÕES DA IA:
1. Turno 2: 87% acerto (quando joga hand disruption)
2. Turno 4: 82% acerto (removals prioritários)
3. Turno 6+: 75% acerto (finishers)

PIORES RECOMENDAÇÕES DA IA:
1. Combat matemática: 60% (precisa melhorar)
2. Sideboarding: 55% (precisa refinar)
```

## 🎯 Auto-Refinamento

Sistema pode:

1. **Adicionar exemplos ao system prompt** baseado em erros
```
"Baseado em jogos anteriores, quando você tem Lightning Bolt + Play with Fire
na mão contra Ramp, priorize matar creatures 2-3 CMC (custo médio) em vez do
oponente."
```

2. **Ajustar confiança** por tipo de recomendação
```json
{
  "recommendation_types": {
    "remove_threat": 0.85,
    "attack_all_in": 0.62,
    "hold_back_defense": 0.78,
    "sideboard_swap": 0.55
  }
}
```

3. **Sugerir tipos de partida** melhor pra você
```
🎯 SUGESTÃO BASEADA NO HISTÓRICO:

Você joga melhor em:
- Standard BO1 (winrate 71%)
- Historic BO3 (winrate 65%)

Você joga pior em:
- Draft (winrate 42%) - considere mais prática ou pausar
- Explorer (winrate 38%) - meta hostil pro seu deck
```

## 📊 Dashboard de Progresso (semanal)

```
📈 PROGRESSO SEMANAL - Semana 03/2026

Winrate geral: 63% (⬆️ +5% vs semana anterior)
Jogos: 42
Vitórias: 26 | Derrotas: 16

DECK MAIS USADO: Mono Red Aggro (18 jogos)
- Winrate: 66% (⬆️)
- Melhor matchup: vs Domain Ramp (8-3)
- Pior matchup: vs Azorius Control (2-4)

DECK NOVO EXPERIMENTADO: Golgari Midrange (5 jogos)
- Winrate: 60%
- Vale continuar testando

RECOMENDAÇÃO PRÓXIMA SEMANA:
- Continuar Mono Red em BO1
- Testar Azorius Control em BO3 (sideboard difícil)
- Praticar combate matemática (queria aula específica?)

CONQUISTAS:
✨ Primeira sessão com 10+ vitórias seguidas
✨ Winrate acima de 60% em 3 formatos diferentes
```

## 🎓 Como Isso Se Traduz para Medicina

Esse mesmo sistema serve pra ensinar:

**Machine Learning na Prática**:
- Vetores = features
- Winrate = target variable
- Ajuste de vetores = gradient descent (simplificado)
- Refinamento de prompt = fine-tuning

**Sistemas de Recomendação Clínica**:
- Deck = protocolo terapêutico
- Vetor = eficácia observada
- Matchup = perfil do paciente
- Trocar deck = ajustar protocolo

**Análise de Performance Médica**:
- Winrate = sucesso terapêutico
- Sessões = casos clínicos
- Feedback loop = revisão de conduta

Esse projeto é literalmente **um curso prático de ML aplicado**, disfarçado de assistente de Magic.
