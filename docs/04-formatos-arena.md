# 🎮 Formatos do MTG Arena

Cada formato tem regras diferentes que MUDAM a estratégia de deck. A IA precisa saber qual formato pra sugerir o deck certo.

## 📋 Formatos Suportados

### 1. STANDARD
**O que é**: Cartas dos ~2 anos mais recentes (5 sets rotacionando).

**Meta atual (verificar antes de cada sessão)**:
- Mono Red Aggro
- Domain Ramp
- Azorius Control
- Golgari Midrange

**Deck ideal**: Aggro (mais barato + winrate no meta atual).

**BO1 vs BO3**:
- BO1: sem sideboard, otimizar mainboard contra meta
- BO3: main + sideboard estratégico

---

### 2. HISTORIC
**O que é**: Todas as cartas já lançadas no Arena (não rotaciona).

**Meta atual**:
- Jund Sacrifice
- Enigmatic Incarnation
- Neoform Combo

**Deck ideal**: Combo (mais poderoso em histórico).

---

### 3. EXPLORER
**O que é**: Cartas do Arena, mas com regras de banimento diferentes.

**Meta atual**:
- Rakdos Aggro
- Ecliptic Anthem

---

### 4. DRAFT (Limited)
**O que é**: Você abre 3 boosters e monta um deck de 40 cartas.

**Estratégia**:
- Não segue meta - você joga com o que abriu
- Curva mais alta (tempo mais lento)
- Priorizar bombs (criaturas grandes)
- Sinergias com o set atual

**Deck ideal**:
- Foco em removals + finishers
- Curva média 2.5-3.0
- 17 lands (não 24 como Constructed)

**Sub-formatos**:
- **Traditional Draft** (BO3)
- **Quick Draft** (BO1 vs bots)
- **Premier Draft** (BO1 vs humanos)

---

### 5. SEALED
**O que é**: Você abre 6 boosters e monta deck de 40 cartas.

**Diferença do Draft**: você tem MAIS cartas pra escolher, mas pior qualidade individual.

**Estratégia**:
- 2 cores só (não 3+)
- Curva alta (3.0)
- Muito removal
- 17 lands

---

### 6. BRAWL
**O que é**: Formato Comandante (1 general + 59 cartas).

**Sub-formatos**:
- **Standard Brawl**: 60 cartas Standard
- **Historic Brawl**: 100 cartas todas do Arena

**Estratégia**: totalmente diferente. Precisa focar no general.

---

### 7. PAUPER (Se disponível no Arena)
**O que é**: Só cartas Common.

**Meta atual**:
- Kuldotha Red
- Grixis Affinity
- Faerie Tempo

---

## 🎯 BO1 vs BO3

### Best of 1 (BO1)
- **Sem sideboard**
- Um jogo só decide
- Estratégia: otimizar mainboard contra META médio
- Mais rápido (10-15 min)

**Deck ideal**: Aggro consistente OU Combo linear.

### Best of 3 (BO3)
- **Sideboard de 15 cartas**
- Melhor de 3 jogos
- Estratégia: sideboard reativo baseado no que oponente mostrou
- Mais longo (30-45 min)

**Deck ideal**: Midrange flexível OU Control com sideboard versátil.

---

## 📊 Tabela de Decisão

Quando o jogador diz `> jogar [formato] [bo]`, sistema segue este fluxograma:

```
STANDARD BO1:
├─ Verifica meta (MTGGoldfish)
├─ Cruza com cartas do jogador
└─ Sugere: Mono Red se tem 100% ou Golgari Midrange

STANDARD BO3:
├─ Verifica meta + winrates
├─ Cruza com cartas do jogador (deck + sideboard)
└─ Sugere: Azorius Control (mais versátil em BO3)

HISTORIC BO1:
├─ Foca em decks lineares (Jund Sacrifice)
└─ Sugere Combo se tem as peças

DRAFT (qualquer):
├─ Sistema NÃO pode sugerir deck (você monta)
├─ MAS sistema PODE ajudar no pick order:
│   ├─ Analisa cartas do booster aberto
│   ├─ Sugere qual pegar (baseado em winrate 17Lands)
│   └─ Adapta conforme cores do deck
└─ Depois, ajuda com as jogadas

SEALED:
├─ Você fotografa/lista os boosters
├─ Sistema monta os 40 cartas ideais
└─ Sugere lineup + curvas

BRAWL:
├─ Você escolhe o general
├─ Sistema monta o resto do deck
└─ Sugere estratégia
```

## 🎯 Cases Práticos

### Case 1: jogando Draft
```
> jogar draft

📋 DRAFT MODE ATIVADO

Como funciona:
1. Você abre o pack no Arena
2. Foto/screenshot o pack
3. Sistema analisa e sugere pick
4. Repete pra cada carta

Sistema conhece o set atual: {set_name}
Winrates médios: {source: 17Lands}

Comece o Draft no Arena e me avise!
```

### Case 2: jogando Standard BO3
```
> jogar standard bo3

🎯 ANALISANDO SEU DECK POOL...
✅ Você tem 100% de Mono Red Aggro
⚠️  Você tem 87% de Azorius Control (falta 4x Teferi)
❌ Você tem 20% de Domain Ramp

RECOMENDAÇÃO: Mono Red Aggro

📊 MATCHUPS ESPERADOS (baseado no meta):
✅ vs Domain Ramp (32% do meta): 65% winrate
✅ vs Golgari Midrange (18%): 58% winrate  
⚠️  vs Azorius Control (12%): 45% winrate
❌ vs Boros Convoke (8%): 38% winrate

Sideboard: incluir 3x Roiling Vortex vs life gain

Confirmar? (y/n)
```

### Case 3: jogando Historic BO1
```
> jogar historic bo1

🎯 HISTORIC BO1 - Meta rápido

RECOMENDAÇÃO: Neoform Combo
Razão: Winrate 68% no meta atual, você tem 100%

Deck otimizado pra BO1 (sem sideboard):
- 4x Neoform
- 4x Allosaurus Rider
- [...]

Estratégia: Vence T3-T4 com Griselbrand.
```

## 📌 Nota Importante

**Meta muda toda semana!** Sistema precisa:
- Buscar dados atualizados de MTGGoldfish/17Lands ANTES de sugerir
- Verificar se cartas foram baneadas
- Considerar sets recém-lançados

Isso é feito via web_search + análise de páginas de meta.
