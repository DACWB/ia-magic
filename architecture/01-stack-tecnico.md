# 🛠️ Stack Técnico

Escolha das tecnologias baseada em:
- **Simplicidade** (fácil de manter)
- **Performance** (baixa latência)
- **Custo** (roda local, sem cloud)
- **Aprendizado** (você entende cada peça)

## 📦 Camada por Camada

### 1. CAPTURA
```
Ferramenta: OBS Studio (você já usa)
Modo: Game Capture 1903 (sua config atual)
Método: WebSocket obs-websocket-plugin
```

**Por que WebSocket?**
- Já vem embutido no OBS 30+
- Python conecta e RECEBE dados estruturados (não só imagem)
- Baixa latência (~50ms)
- Multiplataforma
- Fácil de debugar

**Alternativa se travar**: Screenshot direto via `mss` (Python)

### 2. VISÃO COMPUTACIONAL (OCR)
```
Ferramenta: Claude Vision API (claude-3-5-sonnet)
Estratégia: Só processa REGIÕES QUE MUDARAM
```

**Por que Claude Vision?**
- Melhor OCR pra texto estilizado (Magic tem fontes complexas)
- Entende contexto ("essa carta é uma criatura vermelha")
- Sem setup local complicado (vs. Tesseract)
- Custo: ~$0.003 por imagem = $0.10 por hora de jogo

### 3. LINGUAGEM PYTHON
```
Python: 3.11+
Framework: FastAPI (backend) + Rich (terminal UI)
```

**Bibliotecas principais**:
```
- anthropic          # Claude API
- opencv-python      # Processamento de imagem  
- mss                # Screenshot rápido
- httpx              # HTTP async
- websockets         # Conexão com OBS
- sqlalchemy         # ORM pro SQLite
- rich               # Terminal UI bonito
- pydantic           # Validação de dados
- pandas             # Manipular CSV das cartas
- numpy              # Cálculos numéricos
```

### 4. BANCO DE DADOS
```
Ferramenta: SQLite (nativo, sem servidor)
Localização: ~/magic-ai/data.db
```

**Por que SQLite?**
- Zero setup (arquivo único)
- Rápido pra queries locais (< 10ms)
- Nativo do Python (não precisa instalar)
- Migrations fáceis com SQLAlchemy
- Pode virar Postgres depois se quiser

### 5. INTERFACE (Terminal, não Web)
```
Ferramenta: Rich (Python library)
Estilo: Terminal com cores, tabelas, painéis
```

**Por que Terminal, não Web?**
- Você pediu "texto rápido"
- Zero setup (não precisa Next.js + Vercel)
- Sempre à mostra (sobrepõe qualquer app)
- Você usa 1 tela só (Arena) + 1 monitor pequeno pro terminal

**Layout do terminal**:
```
┌─────────────────────────────────────────────────────┐
│ 🎴 MAGIC AI ADVISOR                    Turno 3      │
├─────────────────────────────────────────────────────┤
│ 👤 Você: 20 vidas | Mana: RRR (3)                  │
│ 🤖 Oponente: 20 vidas | Mana: ??? (3)              │
├─────────────────────────────────────────────────────┤
│ 🎯 DECK OPONENTE: Simic Ramp (87%)                 │
│ ⚠️  Próxima ameaça: Uro (Turn 4)                   │
├─────────────────────────────────────────────────────┤
│ 📋 SUA MÃO:                                        │
│  [1] Monastery Swiftspear (1R)                     │
│  [2] Lightning Bolt (R)                            │
│  [3] Play with Fire (R)                            │
│  [4] Mountain                                       │
├─────────────────────────────────────────────────────┤
│ 💡 RECOMENDAÇÃO:                                    │
│   ✅ Jogue [1] Swiftspear + attack                 │
│   ✅ Depois Bolt + Play with Fire no rosto        │
│   💭 Precisa vencer T5 antes do Uro deles         │
└─────────────────────────────────────────────────────┘
```

### 6. IA / LLM
```
Modelo: Claude Sonnet 4.6 (claude-sonnet-4-6)
Uso:
- Análise estratégica
- Identificação de deck
- Recomendação de jogada
- Aprendizado com histórico
```

**Custo estimado**:
- Análise por turno: ~500 tokens in + 300 out = $0.006
- Turno médio: 10 análises = $0.06 por jogo
- Sessão de 5 jogos: $0.30
- 20 sessões/mês: **$6/mês** 

Muito mais barato que assinar app de análise pronto.

### 7. FONTES DE DADOS EXTERNAS
```
Scryfall API:
- Todas as ~30k cartas de Magic
- Bulk download (200MB) uma vez
- Atualização diária opcional

MTGGoldfish (via web_search):
- Meta atual
- Preços/popularidade dos decks
- Sideboarding guides

17Lands (opcional):
- Winrates de cartas (Draft)
- Meta data por formato
```

## 🏗️ Arquitetura em Camadas

```
┌─────────────────────────────────────────────────────┐
│  USER LAYER                                         │
│  (Terminal Rich UI)                                 │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  APP LAYER                                          │
│  (FastAPI + Async loops)                            │
│  ├─ /game/start                                     │
│  ├─ /game/state                                     │
│  └─ /game/recommend                                 │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  SERVICE LAYER                                      │
│  ├─ ObsService (WebSocket com OBS)                  │
│  ├─ CardService (busca cartas)                      │
│  ├─ DeckService (matching de decks)                 │
│  ├─ IAService (chamadas Claude)                     │
│  └─ LearnService (vetorização)                      │
└──────────────────┬──────────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────────┐
│  DATA LAYER                                         │
│  ├─ SQLite (game state, history, cards)             │
│  ├─ Scryfall cache (JSON files)                     │
│  └─ Redis (opcional, se quiser mais performance)    │
└─────────────────────────────────────────────────────┘
```

## 📁 Estrutura de Diretórios

```
magic-ai-advisor/
├── src/
│   ├── main.py                    # Entry point
│   ├── config.py                   # Configurações
│   ├── models/
│   │   ├── card.py                 # Modelo de carta
│   │   ├── deck.py                 # Modelo de deck
│   │   ├── game_state.py           # Estado do jogo
│   │   └── recommendation.py       # Modelo de recomendação
│   ├── services/
│   │   ├── obs_service.py          # WebSocket OBS
│   │   ├── vision_service.py       # OCR Claude Vision
│   │   ├── card_service.py         # Busca cartas
│   │   ├── deck_service.py         # Identifica decks
│   │   ├── ia_service.py           # Chamadas Claude
│   │   ├── recommend_service.py    # Gera recomendações
│   │   └── learn_service.py        # Sistema de aprendizado
│   ├── ui/
│   │   ├── terminal.py             # Rich UI
│   │   ├── dashboard.py            # Layout principal
│   │   └── prompts.py              # Prompts interativos
│   ├── db/
│   │   ├── database.py             # Conexão SQLite
│   │   ├── migrations/             # Schema
│   │   └── repositories/           # Queries
│   └── utils/
│       ├── logger.py               # Logs
│       └── cache.py                # Cache em memória
├── data/
│   ├── minhas-cartas.csv           # Sua coleção
│   ├── scryfall.json.gz            # Bulk data
│   ├── arquetipos.json             # Base de arquétipos
│   ├── formatos.json               # Info dos formatos
│   └── magic-ai.db                 # SQLite database
├── tests/
│   └── test_*.py                   # Testes
├── requirements.txt
├── .env                            # ANTHROPIC_API_KEY
└── README.md
```

## 🚀 Como Roda

```bash
# Primeira vez
git clone [repo]
cd magic-ai-advisor
pip install -r requirements.txt
cp .env.example .env
# Edita .env: ANTHROPIC_API_KEY=sk-ant-...

# Setup inicial (uma vez)
python src/setup.py

# Uso diário
python src/main.py
```

## 💰 Custo Mensal Estimado

| Item | Custo |
|------|-------|
| Claude API (Vision + Sonnet) | ~$6/mês |
| Scryfall API | Gratuito |
| 17Lands API | Gratuito |
| SQLite | Gratuito |
| Servidor local | Grátis (seu PC) |
| **TOTAL** | **~$6/mês** |

## 🎯 Métricas de Performance

Objetivo:
- **Latência total**: < 2 segundos (frame → recomendação)
- **Precisão de identificação de deck**: > 85% após turno 3
- **Uptime**: 99% durante sessão
- **CPU usage**: < 30% (não trava jogo)
- **RAM**: < 500MB (leve)
