# 🧠 Fluxo de Decisão da IA

Como o sistema decide o que recomendar em cada momento do jogo.

## 🎯 Filosofia

A IA NÃO decide POR você - ela **calcula probabilidades** e **sugere**. Você mantém autonomia total. Isso é importante porque:

1. **Você aprende jogando** (não vira dependente da IA)
2. **A IA pode errar** (você tem contexto que ela não vê)
3. **Assistência ≠ automação** (mesmo princípio da IA na medicina)

## 🔄 Ciclo de Decisão (a cada mudança no board)

```
┌─────────────────────────────────────────────────────┐
│  1. CAPTURA DE ESTADO (< 100ms)                     │
├─────────────────────────────────────────────────────┤
│  - OBS envia frame                                  │
│  - Diff detector: mudou?                            │
│  - Se sim: OCR das mudanças (Claude Vision)         │
│  - Atualiza GameState                               │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  2. IDENTIFICAÇÃO DE DECK (< 500ms)                 │
├─────────────────────────────────────────────────────┤
│  Consulta base de arquétipos:                       │
│  - Match cards visíveis ↔ decks conhecidos          │
│  - Score de similaridade                            │
│  - Retorna: {deck_name, confidence, threats}        │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  3. ANÁLISE DE JOGADA (< 1s)                        │
├─────────────────────────────────────────────────────┤
│  Claude API recebe:                                 │
│  - Seu deck (conhecido, você importou)              │
│  - Sua mão (cartas na mão)                          │
│  - Seu battlefield                                  │
│  - Deck do oponente (identificado)                  │
│  - Battlefield do oponente                          │
│  - Vidas e mana                                     │
│  - Turno e fase                                     │
│                                                     │
│  Claude retorna:                                    │
│  - Top 3 cartas a jogar                             │
│  - Reasoning (por que essa carta)                   │
│  - Alertas (ameaças a considerar)                   │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  4. APRESENTAÇÃO (< 100ms)                          │
├─────────────────────────────────────────────────────┤
│  Formata resposta pro terminal:                     │
│  - Emojis pra clareza                               │
│  - Números pra escolha rápida                       │
│  - Reasoning conciso (< 30 palavras)                │
│  - Alertas em destaque                              │
└─────────────────────────────────────────────────────┘

TEMPO TOTAL: < 2 segundos
```

## 🎯 Prompts (System) para cada Fase

### Fase 1: Deck Builder (pré-jogo)
```
Você é o melhor deck builder de Magic do mundo.

Recebe:
- Formato: {standard, historic, draft, etc}
- BO: {1 ou 3}
- Cartas disponíveis do jogador (CSV)
- Meta atual (do MTGGoldfish + 17Lands)

Retorna JSON:
{
  "deck_name": "Mono Red Aggro",
  "confidence": 0.85,
  "mainboard": [{"name": "Monastery Swiftspear", "quantity": 4}],
  "sideboard": [{"name": "Roiling Vortex", "quantity": 3}] (só se BO3),
  "reasoning": "Escolhi porque...",
  "matchup_predictions": {
    "vs Domain Ramp": 0.65,
    "vs Golgari Midrange": 0.58
  },
  "alternatives": [
    {"deck": "Azorius Control", "coverage": 0.87, "reason": "Falta Teferi"}
  ]
}
```

### Fase 2: Deck Identifier (durante jogo)
```
Você é um especialista em identificar decks de Magic.

Recebe:
- Formato: {standard, etc}
- Cartas VISÍVEIS do oponente (jogadas nos últimos turnos)
- Ordem em que jogou (importante!)
- Cartas no battlefield agora
- Meta atual (top decks)

Retorna JSON:
{
  "archetype": "Ramp",
  "sub_archetype": "Simic Ramp",
  "confidence": 0.87,
  "probable_deck": "Simic Uro Ramp",
  "expected_threats": [
    {"card": "Uro, Titan of Nature's Wrath", "when": "Turn 4"},
    {"card": "Cavalier of Thorns", "when": "Turn 5"},
    {"card": "Emrakul", "when": "Turn 7+"}
  ],
  "win_condition": "Big creatures + card advantage",
  "how_to_counter": [
    "Ser mais rápido (Aggro T5)",
    "Remoção prioritária no Uro",
    "Discard early"
  ]
}
```

### Fase 3: Play Recommender (a cada turno)
```
Você é o melhor jogador de Magic do mundo.

Recebe:
- GameState completo (JSON)
- Deck do oponente (identificado)
- Sua mão de cartas
- Sua fase atual do turno

CRITÉRIOS (nesta ordem):
1. Sobreviver (não morrer)
2. Pressionar oponente
3. Otimizar recursos (mana, cartas)
4. Maximizar chances de vitória em N turnos

Retorna JSON:
{
  "primary_recommendation": {
    "action": "Play Lightning Bolt on opponent's Uro",
    "cards_used": ["Lightning Bolt"],
    "targets": ["Uro"],
    "reasoning": "Uro é a peça principal do deck deles. Removendo agora, evita ramp exponencial e ganho de vida.",
    "expected_impact": "Delay opponent's game plan by 2-3 turns"
  },
  "alternatives": [
    {"action": "Attack all-in", "risk": "medium", "reward": "high"},
    {"action": "Play Monastery Swiftspear", "risk": "low", "reward": "medium"}
  ],
  "warnings": [
    "⚠️ Oponente tem 3 mana disponível - pode ter counterspell",
    "⚠️ Você está com 8 de vida - cuidado com burn deles"
  ],
  "win_probability_after_action": 0.68
}
```

### Fase 4: Sideboard Advisor (entre BO3)
```
Você é um especialista em sideboarding.

Recebe:
- Seu deck (60 mainboard + 15 sideboard)
- Deck do oponente (identificado do Game 1)
- Resultado do G1 (venceu/perdeu, como)
- Cartas específicas que oponente jogou

Retorna JSON:
{
  "remove_from_main": [
    {"card": "Slickshot Show-Off", "quantity": 2, "reason": "Ruim contra criaturas grandes"}
  ],
  "add_from_sideboard": [
    {"card": "Roiling Vortex", "quantity": 2, "reason": "Prevenir life gain do Uro"}
  ],
  "reasoning": "Deck deles tem muitas criaturas 4/5+. Suas Slickshot morrem no ataque. Vortex previne life gain do Uro e Cavalier.",
  "new_gameplan": "Ser MAIS agressivo T1-T3. Vencer antes deles resolverem T5 bomb."
}
```

## 🎓 Como Claude "Pensa" (Chain of Thought)

Exemplo real de análise:

```
CONTEXTO:
- Turno 4, sua vez, Main 1
- Você: 15 vidas, 4 mana RRRR
- Sua mão: Lightning Bolt (1), Monastery Swiftspear (1), Play with Fire (1), Mountain
- Battlefield seu: 2 Monastery Swiftspear, 3 Mountain
- Oponente: 20 vidas, 3 mana G,G,G
- Battlefield oponente: 1 Uro (recém jogado)

CLAUDE PENSA:
1. Ameaça imediata: Uro. Se ficar T4-T5, ele:
   - Attack me pra 6 dano (Uro faz +5 damage)
   - Ganha 3 de vida (subiu pra 23)
   - Recupera land (ramp)
2. Meu win condition: dano constante. Preciso fazer 20 antes T6-T7.
3. Se removo Uro agora:
   - Uso Lightning Bolt (1 dano ao Uro = 6 dano necessário)
   - Ou Play with Fire (2 dano = ainda precisa +4)
   - Ou combo (Bolt + Play = 5 dano total - falta 1)
4. Opção A: Remover Uro (Bolt + Play with Fire = 5 dano em Uro)
5. Opção B: Ignorar Uro e attack full
   - Attack 2 Swiftspears = 4 dano
   - Se Uro block = ele morre em blocked (Uro tem 3 tough)
   - Mas eu perco 1 Swiftspear pra remoção
6. Opção C: Play mais Swiftspear + attack todos
   - Mais dano constante
   - Mas Uro fica vivo

DECISÃO: Opção A é melhor
Razão: Removendo Uro AGORA:
- Perde 6 dano futuro
- Perde ganho de vida
- Deck deles perde ramp exponencial
- Meu clock fica MUITO melhor pros próximos turnos

RESPOSTA:
✅ Jogue Lightning Bolt + Play with Fire no Uro (5 dano = mata Uro)
⚠️ Cuidado: Se ele tiver Counterspell, você perdeu 2 cartas
Alternativa: Jogar Monastery Swiftspear + attack (menos comprometido)
```

## 🎯 Métricas de Sucesso

Sistema mede:
- **Latência**: quanto tempo entre mudança no board → recomendação
- **Precisão de identificação**: qual % das identificações de deck estavam certas?
- **Winrate com IA**: você ganha mais seguindo?
- **Confiança calibrada**: quando IA diz 80% de vitória, isso se confirma?

Objetivo: latência < 2s, winrate ↑ +10-20%, calibração ± 5%.
