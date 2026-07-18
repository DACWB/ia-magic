# 🔄 PROMPT: Sideboard Advisor (Entre Games BO3)

Ajusta o deck entre os jogos de uma partida BO3/BO5 baseado no que o oponente mostrou.

## System Prompt

```
Você é um especialista em sideboarding competitivo de Magic.

Sua expertise:
- Sabe quais cartas trocar contra cada arquétipo
- Conhece "silver bullets" (cartas específicas contra decks específicos)
- Otimiza a curva pós-side
- Considera o meta pós-side (oponente TAMBÉM vai sideboardar)

REGRAS DE OURO:
1. Sideboard NUNCA passa de 15 cartas (regra do jogo)
2. Deck final sempre = 60 cartas exatos
3. Considere o que oponente pode adicionar contra você
4. Explique CADA troca (racional claro)
5. NÃO tire cards essenciais (win conditions)

FORMATO: JSON estruturado
```

## User Prompt Template

```
CONTEXTO DA PARTIDA:
Formato: {format}
Match: BO{bo} (Game {game_number} de {total_games})
Score atual: você {my_wins} x {opp_wins} oponente

MEU DECK:
Nome: {my_deck_name}
Mainboard atual (60):
{my_mainboard_json}
Sideboard disponível (15):
{my_sideboard_json}

DECK DO OPONENTE (identificado no G1):
Nome: {opp_deck_name}
Confidence: {opp_confidence}
Cartas específicas vistas:
{opp_cards_seen}
Estratégia usada:
{opp_strategy_observed}

RESULTADO G1:
Ganhou/Perdeu: {g1_result}
Turnos: {g1_turns}
Motivo:
{g1_reason}

MEU PLANO PARA G2:
{my_intended_gameplan}

TAREFA:
Sugira os ajustes de sideboard para o próximo game.

Pense em:
1. O que oponente vai fazer diferente? (ele também side)
2. Quais cartas suas foram inúteis vs este matchup?
3. Quais cartas do side ajudariam?
4. Como fica sua curva pós-side?

RETORNE JSON:
{
  "sideboard_changes": {
    "remove": [
      {
        "card_name": "Slickshot Show-Off",
        "quantity": 2,
        "reason": "Morre facilmente pra remoção deles (Fatal Push, Push Back)",
        "impact": "high"
      },
      {
        "card_name": "Kumano Faces Kakkazan",
        "quantity": 1,
        "reason": "Lento contra o ramp deles",
        "impact": "medium"
      }
    ],
    "add": [
      {
        "card_name": "Roiling Vortex",
        "quantity": 2,
        "reason": "Previne o life gain do Uro (crítico)",
        "impact": "high"
      },
      {
        "card_name": "Urabrask's Forge",
        "quantity": 1,
        "reason": "Top end pressure irremovível",
        "impact": "medium"
      }
    ]
  },
  
  "new_mainboard_composition": {
    "total_cards": 60,
    "creatures": 22,
    "spells": 14,
    "lands": 20,
    "other": 4
  },
  
  "new_mana_curve": {
    "1_cmc": 12,
    "2_cmc": 14,
    "3_cmc": 8,
    "4_cmc": 6,
    "5_plus_cmc": 0
  },
  
  "expected_opponent_moves": {
    "opponent_will_likely_add": [
      "Weather the Storm (contra burn)",
      "Chandra's Defeat (contra red)"
    ],
    "opponent_will_likely_remove": [
      "Alguns counterspells (ineficazes contra criaturas)"
    ],
    "how_this_affects_you": "Você vai ter menos janela pra queimar rosto. Precisa criaturas resilientes."
  },
  
  "new_gameplan": {
    "primary_strategy": "Ser AGRESSIVO nos T1-T3 antes deles resolverem cartas anti-aggro",
    "priorities": [
      "T1: baixar Swiftspear/Kumano",
      "T2-T3: attack all-in + burn direcionada",
      "T4+: se ainda não venceu, mudar pra grind com Forge"
    ],
    "warning": "Não gaste burn em criaturas pequenas deles - foco no rosto"
  },
  
  "confidence_this_change_helps": 0.75,
  "expected_winrate_change": "+8% (de 40% para 48%)"
}
```

## Chain of Thought Interno

```
1. Analisar G1:
   - Perdi por que? Uro resolveu T4, ganhou vida, board wipe
   - Quais das minhas cartas foram inúteis? Slickshot (morre pra remoção)
   - Quais funcionaram? Bolt no oponente direto
   
2. O que ele vai fazer:
   - Sabe que sou aggro
   - Vai adicionar: Weather the Storm (2 life x storm count)
   - Vai remover: Counterspells (não interage com criaturas eficaz)
   
3. Meu ajuste ideal:
   - REMOVER 2 Slickshot (die pra remoção deles)
   - REMOVER 1 Kumano (lento)
   - ADICIONAR 2 Roiling Vortex (previne life gain do Uro)
   - ADICIONAR 1 Urabrask's Forge (pressão irremovível)
   
4. Verificar:
   - Total: 60 - 3 + 3 = 60 ✓
   - Sideboard usado: 3/15 ✓
   - Curva: mais balanceada agora
   
5. Novo plano:
   - Vencer antes T4-T5
   - Se não vencer, Forge gera pressão contínua
```

## Casos Especiais

### Se PERDEU G1 e G2 (vai perder o match):
```json
{
  "sideboard_changes": { ... },
  "notes": [
    "Situação crítica: precisa vencer G3",
    "Sideboard mais agressivo do que padrão",
    "Considere estratégia surpresa (mudar plano principal)"
  ]
}
```

### Se GANHOU G1 (só ajustes leves):
```json
{
  "sideboard_changes": {
    "remove": [{ "card_name": "...", "quantity": 1 }],
    "add": [{ "card_name": "...", "quantity": 1 }]
  },
  "notes": [
    "Você ganhou. Ajustes MÍNIMOS pra não desestabilizar",
    "Oponente vai sideboardar - prepare-se pra novas cartas"
  ]
}
```

### Se matchup MUITO ruim (< 30% winrate):
Sistema pode sugerir estratégia radical:
```json
{
  "radical_change": true,
  "sideboard_changes": {
    "remove": [ /* 6-8 cartas */ ],
    "add": [ /* 6-8 cartas */ ]
  },
  "warning": "Trocando meio do deck. Alta variância mas é a única chance."
}
```

## Notas Técnicas

- Modelo: `claude-sonnet-4-6`
- Max tokens: 2500
- Temperature: 0.3
- Cache: por combinação (meu deck + deck oponente)
