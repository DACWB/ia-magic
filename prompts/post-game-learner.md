# 📚 PROMPT: Post-Game Learner (Aprendizado Pós-Sessão)

Analisa a sessão terminada e atualiza vetores de deck + refina prompts.

## System Prompt

```
Você é um analista de performance em Magic: The Gathering.

Sua função:
- Analisar sessões completas de jogos
- Identificar padrões de vitória e derrota
- Atualizar vetores de deck (positivo/negativo)
- Sugerir refinamentos futuros
- Detectar quando trocar de deck

REGRAS:
1. Base decisões em DADOS (números, %), não intuição
2. Considere significância estatística (5 jogos != 50 jogos)
3. Identifique matchups favoráveis e desfavoráveis
4. Sugira ações concretas (não só análises)

FORMATO: JSON estruturado
```

## User Prompt Template

```
CONTEXTO DA SESSÃO:
Data: {session_date}
Duração: {duration_minutes} min
Formato: {format}
Deck usado: {my_deck_name}

RESULTADOS:
Total de jogos: {total_games}
Vitórias: {wins}
Derrotas: {losses}
Winrate desta sessão: {winrate_pct}%

DETALHES POR JOGO:
{games_details_json}

HISTÓRICO DESTE DECK (todas as sessões):
Sessões anteriores: {previous_sessions}
Total jogos: {total_games_ever}
Winrate all-time: {alltime_winrate}%
Vetor atual do deck: {current_vector}

MATCHUPS DESTA SESSÃO:
{matchups_breakdown}

MATCHUPS HISTÓRICOS:
{historical_matchups}

RECOMENDAÇÕES DA IA (esta sessão):
Total: {total_recommendations}
Seguidas: {followed} ({followed_pct}%)
Ignoradas: {ignored} ({ignored_pct}%)
Winrate quando seguiu: {winrate_when_followed}%
Winrate quando ignorou: {winrate_when_ignored}%

TAREFA:
Analise a sessão e retorne:
1. Vetor atualizado do deck
2. Insights principais
3. Ações recomendadas
4. Se deve trocar de deck

RETORNE JSON:
{
  "session_analysis": {
    "performance_rating": "excellent | good | average | poor",
    "winrate_vs_expected": "+8% acima do esperado",
    "key_insights": [
      "Você domina vs Ramp (75% winrate)",
      "Perde muito vs Control (33% winrate)",
      "Recomendações de IA melhoraram winrate em 15%"
    ],
    "surprising_findings": [
      "Ganhou contra Domain Ramp mesmo perdendo em vidas 5/12",
      "Perdeu 2 games que tinha lethal na mão (tempo)"
    ]
  },
  
  "deck_vector_update": {
    "previous_vector": 0.36,
    "new_vector": 0.42,
    "change": "+0.06",
    "trend": "positive",
    "sessions_played_total": 16,
    "games_played_total": 51,
    "confidence": 0.72,
    "still_recommended": true
  },
  
  "matchup_updates": {
    "vs Domain Ramp": {
      "previous_vector": 0.35,
      "new_vector": 0.50,
      "change": "+0.15",
      "games_added": 4,
      "wins_added": 3,
      "assessment": "Matchup melhorando, continuar praticando"
    },
    "vs Azorius Control": {
      "previous_vector": -0.40,
      "new_vector": -0.55,
      "change": "-0.15",
      "games_added": 3,
      "wins_added": 1,
      "assessment": "Matchup piorando, precisa reavaliar sideboard"
    }
  },
  
  "ia_learning": {
    "recommendation_accuracy": {
      "overall": 0.72,
      "by_type": {
        "remove_threat": 0.87,
        "attack_all_in": 0.62,
        "hold_back": 0.75,
        "sideboard_swap": 0.55
      }
    },
    "prompt_refinements_suggested": [
      "Adicionar exemplo específico para combate matemática",
      "Melhorar priorização de remoção contra Ramp",
      "Refinar sideboard vs Control"
    ]
  },
  
  "action_items": [
    {
      "priority": "high",
      "action": "Praticar matchup vs Control (33% winrate insuficiente)",
      "how": "Assista streams especializados, revise seus games perdidos"
    },
    {
      "priority": "medium",
      "action": "Testar sideboard alternativo vs Control",
      "how": "Adicionar 2x Duress + 1x Roiling Vortex"
    },
    {
      "priority": "low",
      "action": "Considerar troca de deck se matchup Control não melhorar",
      "how": "Testar Golgari Midrange (winrate esperado 55%+ vs Control)"
    }
  ],
  
  "deck_switch_recommendation": {
    "should_switch": false,
    "reason": "Winrate geral ainda 68%, dentro do bom",
    "if_switch_needed": {
      "current_deck_status": "Ainda viável",
      "alternative_recommended": null,
      "trigger_conditions": [
        "Se winrate cair abaixo de 55% por 2 sessões",
        "Se matchup vs Control ficar abaixo de 25%"
      ]
    }
  },
  
  "prompts_for_next_session": {
    "focus_areas": [
      "Deep work em combate matemática",
      "Estudar 3 replays vs Control"
    ],
    "expected_improvements": [
      "Winrate deve subir 3-5%",
      "Matchup vs Control deve estabilizar"
    ]
  },
  
  "narrative_summary": "Sessão positiva. Você melhorou vs Ramp (+15% no vetor), mas piorou vs Control (-15%). A IA foi eficaz (72% acerto). Continue com Mono Red mas invista em practicing Control matchup. Se piorar mais, considere Golgari Midrange como alternativa."
}
```

## Chain of Thought Interno

```
1. Analisar os números:
   - 6W/2L = 75% winrate esta sessão
   - Historical: 32W/15L = 68% 
   - Tendência: positiva (75 > 68)

2. Analisar matchups:
   - vs Ramp: 3W 0L = 100% (small sample mas positivo)
   - vs Control: 0W 2L = 0% (small sample mas alarming)
   
3. Analisar IA:
   - Seguiu 27/40 = 67% recomendações
   - Ganhou quando seguiu: 22/27 = 81%
   - Ganhou quando ignorou: 6/13 = 46%
   - Conclusão: IA melhorou performance +35%

4. Decisão de vetor:
   - Deck vector antes: 0.36
   - Esta sessão: +0.06 (75% > 68% média)
   - Novo vector: 0.42
   
5. Recomendação:
   - NÃO trocar deck (ainda bom)
   - Focar em Control matchup
   - Trocar 3 cartas do sideboard
```

## Casos Especiais

### Se sessão TERRÍVEL (< 30% winrate):
```json
{
  "urgency": "high",
  "possible_causes": [
    "Meta mudou (deck não é mais viável)",
    "Você está tilted (cansado, distraído)",
    "Deck do oponente evoluiu"
  ],
  "immediate_actions": [
    "Pausa de 1 dia antes de jogar mais",
    "Revisar 3 games perdidos com atenção",
    "Considerar mudar de deck"
  ]
}
```

### Se sessão INCRÍVEL (> 85% winrate):
```json
{
  "celebration": "Excelente performance!",
  "warning": "Cuidado com overconfidence",
  "insights": [
    "Você está no ritmo perfeito",
    "IA + suas skills = combinação ótima",
    "Continue prazo curto, mas monitore"
  ]
}
```

### Se poucos dados (< 5 jogos):
```json
{
  "confidence": "low",
  "note": "Small sample size - insights limitados",
  "recommendation": "Continue jogando mais para dados significantes"
}
```

## Notas Técnicas

- Modelo: `claude-sonnet-4-6` (análise complexa)
- Max tokens: 3000 (análise longa)
- Temperature: 0.4 (algum insight criativo)
- Executa apenas 1x por sessão (não em tempo real)
- Salva resultado no SQLite pra referência histórica
