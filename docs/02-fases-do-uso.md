# 🎬 Fases de Uso (Perspectiva do Usuário)

Do momento que o jogador abre o Arena até salvar os resultados.

## FASE 1: SETUP (uma vez, no início)

### 1.1 Instalação
- Python 3.11+ instalado
- SQLite (nativo)
- OBS Studio 30+ com plugin de WebSocket
- Cartas do Arena exportadas ou preenchidas manualmente em CSV

### 1.2 Primeira execução
- Sistema baixa bulk data do Scryfall (~200MB, uma vez)
- Sistema carrega ~30k cartas no SQLite indexado
- Sistema baixa arquétipos conhecidos (JSON)
- Testa conexão com OBS

### 1.3 Configuração
- o jogador informa: "Sou @jogador, jogo Standard e Draft"
- Sistema pergunta se quer histórico salvo (yes/no)
- Cria pasta `~/magic-ai/` com todos os dados locais

---

## FASE 2: ANTES DA PARTIDA

### 2.1 Atualização de coleção
Duas opções:

**Opção A: Manual (recomendada no início)**
o jogador abre `minhas-cartas.csv` e atualiza:
```csv
card_name,quantity,foil
Lightning Bolt,4,0
Counterspell,2,1
Thoughtseize,3,0
...
```

**Opção B: Auto (futuro)**
Sistema faz OCR das cartas do Arena e detecta o que tem.

### 2.2 Escolha de formato
o jogador digita ou clica no dashboard:
```
> jogar standard bo3
> jogar draft
> jogar historic bo1
```

### 2.3 IA sugere deck
Sistema consulta:
1. Meta atual (MTGGoldfish, 17Lands)
2. Suas cartas disponíveis
3. Arquétipos mais fortes

Retorna:
```
🎯 DECK SUGERIDO: Mono Red Aggro (72% winrate no meta)

MAINBOARD (60):
- 4x Monastery Swiftspear
- 4x Kumano Faces Kakkazan
- 3x Slickshot Show-Off
[...]

SIDEBOARD (15):
- 3x Roiling Vortex
- 2x Urabrask's Forge
[...]

PORQUÊ:
- Você tem 100% das cartas necessárias
- Meta atual tem muitos decks midrange que perdem para aggro rápido
- Alternativa: Azorius Control (você só tem 87%)
```

o jogador confirma ou escolhe alternativa.

### 2.4 Importar no Arena
Sistema gera texto no formato Arena para copiar/colar:
```
4 Monastery Swiftspear (NEO) 138
4 Kumano Faces Kakkazan (NEO) 152
...
```

o jogador cola no Arena e cria o deck.

---

## FASE 3: DURANTE A PARTIDA

### 3.1 Iniciar captura
```
> começar partida
```

Sistema:
1. Ativa captura OBS
2. Verifica frames chegando
3. Abre dashboard em texto no terminal
4. Aguarda início do jogo

### 3.2 Detecção inicial
Quando a partida começa:
```
🎴 PARTIDA INICIADA
📊 Deck em uso: Mono Red Aggro
🎲 Turno 1 - Sua vez
```

### 3.3 Recomendação em tempo real
A cada mudança no board:
```
═══════════════════════════════════════════════════
TURNO 3 - Sua vez (fase: Main 1)
═══════════════════════════════════════════════════
👤 VOCÊ: 20 vidas | Mana: R,R,R (3)
🤖 OPONENTE: 20 vidas | Mana: ??? (3)

🎯 DECK DO OPONENTE:
   Simic Ramp (72% confiança)
   ⚠️  Ameaças esperadas: Cavalier of Thorns, Uro

📋 SUA MÃO:
   [1] Monastery Swiftspear (1 mana)
   [2] Lightning Bolt (1 mana)  
   [3] Play with Fire (1 mana)
   [4] Mountain

💡 RECOMENDAÇÃO:
   ✅ Jogue [1] Monastery Swiftspear
   ✅ Depois [3] Play with Fire no rosto
   
   Por quê: Oponente vai jogar Uro no T4. Você precisa
   fazer 6+ dano até lá pra não perder a corrida.
   
═══════════════════════════════════════════════════
```

### 3.4 Loop contínuo
- Sistema detecta cada carta nova jogada
- Atualiza análise de deck do oponente
- Refina recomendação
- Alerta sobre ameaças

### 3.5 Fim do jogo
```
🏆 VITÓRIA em 7 turnos!
📊 Recomendações seguidas: 8/12 (67%)
✨ Play chave: T3 Swiftspear + burn face

Quer:
[c] Continuar (próxima partida)
[s] Sideboard (se BO3)
[f] Finalizar sessão
```

---

## FASE 4: ENTRE JOGOS (BO3)

### 4.1 Sideboard automático
```
📋 SIDEBOARDING vs Simic Ramp:

REMOVER:
- 2x Slickshot Show-Off (ruim contra criaturas grandes)
- 1x Kumano Faces Kakkazan (lento)

ADICIONAR:
- 2x Roiling Vortex (previne life gain)
- 1x Urabrask's Forge (top end pressure)

Razão: Deck deles vai remover suas criaturas pequenas.
Precisa de ameaças resilientes + queimar life gain.
```

o jogador aplica no Arena e joga próxima partida.

### 4.2 Aprendizado entre partidas
Se ganhou G1:
```
✅ G1 vitória. Ajustes mínimos no sideboard.
Confiança no deck: ⬆️ 82%
```

Se perdeu G1:
```
❌ G1 derrota. Análise:
- Você não conseguiu virar até T5
- Uro dele resolveu T4
- Sugestão: sideboard mais agressivo
```

---

## FASE 5: PÓS-SESSÃO

### 5.1 Resumo
```
📊 SESSÃO DE 18/07 - 19:30 até 21:00

Total: 8 partidas
Vitórias: 6 (75%)
Deck: Mono Red Aggro

MELHORES MATCHUPS:
✅ vs Simic Ramp: 3W 0L
✅ vs Azorius Control: 2W 0L

PIORES MATCHUPS:
❌ vs Boros Convoke: 0W 2L
❌ vs Domain Ramp: 1W 1L

RECOMENDAÇÕES DA IA:
- Seguidas: 43/62 (69%)
- Delas ganhou: 32/43 (74%)
- Ignorou e ganhou: 11/19 (58%)
- IA melhorou seu winrate em +16%

APRENDIZADO:
- Contra Convoke, IA errou 3x no T2
- Vou ajustar prompt pra priorizar remoção de creatures pequenas
```

### 5.2 Salva tudo
- Cada jogo vai pro SQLite
- Recomendações e resultados
- Vetores de deck atualizados
- Pronto pra próxima sessão

---

## 🎯 Comandos Principais

| Comando | O que faz |
|---------|-----------|
| `> jogar [formato] [bo]` | Sugere deck e prepara sessão |
| `> começar partida` | Ativa captura OBS |
| `> pausar` | Pausa captura sem sair |
| `> continuar` | Retoma captura |
| `> sideboard` | Sugere ajustes entre BO3 |
| `> finalizar` | Salva sessão e mostra resumo |
| `> historico` | Mostra winrate por deck |
| `> atualizar cartas` | Reabre CSV pra editar |
