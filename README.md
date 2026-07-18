# 🎴 Magic Arena AI Advisor

Sistema de IA em tempo real que assiste o jogador durante partidas de Magic: The Gathering Arena, identificando o deck do oponente, sugerindo jogadas, e otimizando o deck do jogador conforme o formato do jogo.

## 🎯 Objetivo

Criar um **copiloto de IA** que:
1. **Antes do jogo**: Sabe quais cartas o jogador tem, o tipo de partida (Draft, Standard, BO1, BO3), e monta o deck com maior chance de vitória
2. **Durante o jogo**: Analisa em tempo real via OBS o que o oponente joga, identifica o arquétipo/deck, e sugere as melhores cartas da mão do jogador
3. **Entre jogos (BO3+)**: Ajusta o sideboard baseado no que o oponente mostrou
4. **Após o jogo**: Aprende com o resultado - deck que ganha ganha vetor positivo, deck que perde é ajustado

## 👤 Autor

Usuário - Médico oftalmologista, professor de IA aplicada à medicina.  
Este projeto usa o mesmo pipeline pedagógico ensinado para médicos: captura de dados → estruturação → IA → decisão.

## 📁 Estrutura da Documentação

```
magic-ai-advisor/
├── README.md                          # Este arquivo (visão geral)
├── docs/
│   ├── 01-visao-geral.md              # Fluxo completo do sistema
│   ├── 02-fases-do-uso.md             # Fase 1, 2, 3 do usuário
│   ├── 03-arquetipos-magic.md         # Arquétipos de deck do MTG
│   ├── 04-formatos-arena.md           # Draft, Standard, Historic, BO1, BO3
│   ├── 05-fluxo-decisao-ia.md         # Como a IA decide o quê recomendar
│   └── 06-aprendizado-adaptativo.md   # Sistema de vetorização de decks
├── architecture/
│   ├── 01-stack-tecnico.md            # Tecnologias escolhidas
│   ├── 02-camadas-sistema.md          # 5 camadas do sistema
│   ├── 03-banco-de-dados.md           # Schema SQLite
│   ├── 04-integracao-obs.md           # Como capturar do Arena via OBS
│   ├── 05-scryfall-integration.md     # Como usar bulk data das cartas
│   └── 06-claude-api-usage.md         # Como estruturamos as chamadas ao Claude
├── data/
│   ├── minhas-cartas.example.csv      # Template pra você preencher
│   ├── arquetipos.json                # Dicionário de arquétipos
│   └── formatos.json                  # Dicionário de formatos Arena
├── prompts/
│   ├── deck-builder.md                # Prompt: montar deck pré-jogo
│   ├── deck-identifier.md             # Prompt: identificar deck do oponente
│   ├── play-recommender.md            # Prompt: recomendar carta a jogar
│   ├── sideboard-advisor.md           # Prompt: ajustar sideboard entre BO3
│   └── post-game-learner.md           # Prompt: aprender com o resultado
└── ROADMAP-1-SEMANA.md                # Plano de execução em 7 dias
```

## 🚀 Como Usar

1. **Revise a documentação** em `docs/` (começa por `01-visao-geral.md`)
2. **Confirme a arquitetura** em `architecture/`
3. **Preencha suas cartas** em `data/minhas-cartas.csv`
4. **Abra no Cowork** e mande o Claude começar pelo ROADMAP dia 1
5. **Claude Code** executa cada dia do roadmap

## 📞 Contato

o jogador - @usuario (Instagram)  
o projeto didático - @projeto
