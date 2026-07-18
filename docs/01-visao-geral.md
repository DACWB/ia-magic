# 📖 Visão Geral do Sistema

## 🎯 Problema que Resolvemos

Quando jogamos MTG Arena, temos três desafios simultâneos:

1. **Escolher o deck certo** para o formato (Draft, Standard, Historic, etc)
2. **Descobrir o deck do oponente** em tempo real (quanto antes, melhor)
3. **Decidir qual carta jogar** considerando: minha mão + battlefield + deck do oponente

Fazer isso simultaneamente é impossível para humanos - mas trivial para IA quando bem estruturada.

## 🔄 Fluxo Completo do Sistema

```
┌─────────────────────────────────────────────────────────────┐
│  FASE 1: PRÉ-JOGO (fora da partida)                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Usuário atualiza planilha "minhas-cartas.csv"           │
│     (ou sistema OCR faz automático das cartas do Arena)     │
│                                                             │
│  2. Usuário informa: "Vou jogar [Formato] [BO1 ou BO3]"     │
│                                                             │
│  3. IA consulta:                                            │
│     - Base de decks do meta atual (MTGGoldfish, 17Lands)   │
│     - Suas cartas disponíveis                              │
│     - Arquétipos vencedores do formato                     │
│                                                             │
│  4. IA sugere o deck com maior chance de vitória           │
│     - Mainboard (60 cartas)                                │
│     - Sideboard (15 cartas, se BO3)                        │
│     - Reasoning: "Escolhi Mono Red Aggro porque..."        │
│                                                             │
│  5. Usuário importa o deck no Arena                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  FASE 2: DURANTE O JOGO                                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. OBS captura a tela do Arena (Game Capture 1903)         │
│     → Python recebe frames em tempo real                    │
│                                                             │
│  2. IA identifica AUTOMATICAMENTE:                          │
│     - Suas cartas na mão (já conhece o deck completo)      │
│     - Suas cartas no battlefield                           │
│     - Cartas do oponente no battlefield                    │
│     - Vidas, mana, turno, fase                             │
│                                                             │
│  3. IA identifica o DECK DO OPONENTE:                       │
│     Turno 1: "Land verde jogada = provavelmente Green"     │
│     Turno 2: "Elfo mana ramp = Deck de Ramp"               │
│     Turno 3: "Cavalo grande = Confirmed Elves Aggro"       │
│     Confiança aumenta com mais informação                  │
│                                                             │
│  4. IA RECOMENDA a próxima carta a jogar:                   │
│     "Jogue Lightning Bolt no elfo mana antes que ele        │
│      te dê vantagem de ramp exponencial"                   │
│                                                             │
│  5. Loop contínuo até fim do jogo                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  FASE 3: ENTRE JOGOS (só em BO3, BO5)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Se ganhou:                                                 │
│  → Deck ganha "vetor de vitória" (+1 na próxima partida)   │
│  → Ajustes mínimos (só sideboard tático)                   │
│                                                             │
│  Se perdeu:                                                 │
│  → Deck ganha "vetor de derrota" (-1)                      │
│  → IA sugere sideboard agressivo baseado no que oponente  │
│    mostrou (ex: "tire 3 Counterspells, coloque 3 Duress") │
│  → Se derrota consistente, propõe TROCAR o deck            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  FASE 4: PÓS-SESSÃO (aprendizado)                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Salva todos os jogos no SQLite:                         │
│     - Deck usado, oponente identificado, resultado         │
│     - Cartas jogadas em cada turno                         │
│     - Recomendações da IA vs decisões do jogador           │
│                                                             │
│  2. Análise de performance:                                 │
│     - Qual deck teve melhor winrate?                        │
│     - Contra quais arquétipos você perde mais?              │
│     - Quando ignoraram a recomendação da IA, ganharam?     │
│                                                             │
│  3. Aprende:                                                │
│     - Refina system prompt de recomendações                │
│     - Atualiza vetores de deck (quais funcionam)           │
│     - Melhora identificação de arquétipos                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🎓 Analogia Médica (para ensino)

Este sistema é isomórfico ao **fluxo clínico**:

| Fase Magic | Fase Clínica |
|-----------|-------------|
| Escolher deck pré-jogo | Escolher protocolo terapêutico pré-consulta |
| Cartas disponíveis | Medicamentos disponíveis (farmácia) |
| Identificar deck oponente | Diagnóstico diferencial |
| Recomendar carta | Recomendar conduta clínica |
| Sideboard entre BO3 | Ajustar conduta na segunda consulta |
| Aprender com vitória/derrota | Aprender com desfecho clínico |

Pode ser usado como material didático para explicar:
- **Modelos preditivos** (deck matching = diagnóstico)
- **Sistemas de recomendação** (carta = conduta)
- **Aprendizado adaptativo** (vetorização = machine learning clínico)
- **Análise em tempo real** (streaming data = monitorização de UTI)
