# 🏛️ 5 Camadas do Sistema

## Visão Geral

O sistema é dividido em 5 camadas, cada uma com responsabilidade única. Isso facilita:
- Debug (você sabe onde está o problema)
- Manutenção (troca uma camada sem afetar as outras)
- Aprendizado (você entende cada peça)

## Camada 1: CAPTURA (Interface com OBS)

**Responsabilidade**: Pegar frames do Arena e passar para as camadas superiores.

**Componentes**:
- `ObsService`: conecta ao OBS via WebSocket
- `DiffDetector`: identifica quando algo mudou no frame
- `RegionExtractor`: extrai regiões de interesse (mão, board, etc)

**Entrada**: nada (roda sozinha)
**Saída**: frames como bytes de imagem PNG/JPEG

**Frequência**: 3-5 FPS (a cada 200-300ms)

## Camada 2: VISÃO (OCR + Interpretação)

**Responsabilidade**: Transformar imagem em dados estruturados.

**Componentes**:
- `VisionService`: chama Claude Vision API para OCR
- `CardMatcher`: busca cartas identificadas no SQLite
- `StateExtractor`: extrai vida, mana, turno, fase

**Entrada**: frame como bytes
**Saída**: `PartialGameState` (dados brutos identificados)

**Frequência**: apenas quando frame mudou (diff detection)

## Camada 3: LÓGICA DE JOGO (GameState + Regras)

**Responsabilidade**: Manter estado consistente do jogo.

**Componentes**:
- `GameStateManager`: mantém o estado atual
- `GameStateValidator`: valida transições legais
- `HistoryTracker`: guarda histórico de plays

**Entrada**: `PartialGameState` da camada 2
**Saída**: `GameState` completo e validado

**Persistência**: SQLite após cada mudança

## Camada 4: INTELIGÊNCIA (IA + Análise)

**Responsabilidade**: Analisar estado e gerar recomendações.

**Componentes**:
- `DeckIdentifier`: identifica deck do oponente
- `PlayRecommender`: sugere próxima jogada
- `ThreatAnalyzer`: alerta sobre ameaças
- `SideboardAdvisor`: ajustes entre BO3

**Entrada**: `GameState` da camada 3
**Saída**: `Recommendation` (JSON estruturado)

**Modelo**: Claude Sonnet (via API)

## Camada 5: APRESENTAÇÃO (Terminal UI)

**Responsabilidade**: Mostrar tudo pro usuário.

**Componentes**:
- `TerminalUI` (Rich)
- `Dashboard`: layout principal
- `Notifications`: alertas críticos
- `InputHandler`: comandos do usuário

**Entrada**: `GameState` + `Recommendation`
**Saída**: display formatado no terminal

## 🔄 Fluxo de Dados

```
┌─────────────────────────────────────────────────────┐
│  CAMADA 1: CAPTURA                                  │
│  ObsService → frame_bytes                           │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ frame_bytes
                   ▼
┌─────────────────────────────────────────────────────┐
│  CAMADA 2: VISÃO                                    │
│  VisionService.identify(frame_bytes)                │
│  → PartialGameState                                 │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ PartialGameState
                   ▼
┌─────────────────────────────────────────────────────┐
│  CAMADA 3: LÓGICA                                   │
│  GameStateManager.update(partial)                   │
│  → GameState (validated + full)                     │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ GameState
                   ▼
┌─────────────────────────────────────────────────────┐
│  CAMADA 4: IA                                       │
│  DeckIdentifier.identify(game_state)                │
│  PlayRecommender.recommend(game_state)              │
│  → Recommendation                                   │
└──────────────────┬──────────────────────────────────┘
                   │
                   │ Recommendation
                   ▼
┌─────────────────────────────────────────────────────┐
│  CAMADA 5: UI                                       │
│  Dashboard.update(state, recommendation)            │
│  → Display no terminal                              │
└─────────────────────────────────────────────────────┘
```

## 🎯 Vantagens desta Arquitetura

1. **Testável**: Cada camada tem tests próprios
2. **Substituível**: Trocar OBS por MSS = só muda Camada 1
3. **Escalável**: Adicionar camada 6 (Web UI) sem quebrar
4. **Debug**: Sabe exatamente onde está o problema
5. **Aprendizado**: Você entende cada parte

## 🚀 Cronograma vs Camadas

| Dia | Camada Foco | Testes |
|-----|-------------|--------|
| 1 | Setup | Ambiente + API |
| 2 | Camada 3 (SQLite) | Cards funcionando |
| 3 | Camada 1 (OBS) | Frames chegando |
| 4 | Camada 2 (Vision) | OCR funcionando |
| 5 | Camada 4 (IA) | Recomendações |
| 6 | Camada 5 (UI) | Dashboard bonito |
| 7 | Integração | Sistema completo |
