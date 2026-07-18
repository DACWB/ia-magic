# 🗄️ Schema do Banco de Dados (SQLite)

Database file: `~/magic-ai/data.db`

## 📊 Tabelas

### 1. `cards` (~30k rows - preenchida do Scryfall)

Todas as cartas de Magic que existem.

```sql
CREATE TABLE cards (
    id TEXT PRIMARY KEY,           -- Scryfall UUID
    name TEXT NOT NULL,
    mana_cost TEXT,
    cmc REAL,                       -- converted mana cost
    type_line TEXT,
    oracle_text TEXT,
    colors TEXT,                    -- JSON array: ["R", "G"]
    color_identity TEXT,            -- JSON array
    keywords TEXT,                  -- JSON array: ["Flying", "Trample"]
    power INTEGER,
    toughness INTEGER,
    loyalty INTEGER,
    rarity TEXT,                    -- common, uncommon, rare, mythic
    set_code TEXT,
    set_name TEXT,
    image_url TEXT,
    scryfall_url TEXT,
    legalities TEXT,                -- JSON: {"standard": "legal", ...}
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_cards_name ON cards(name);
CREATE INDEX idx_cards_type_line ON cards(type_line);
CREATE INDEX idx_cards_cmc ON cards(cmc);
```

### 2. `my_collection` (preenchida pelo jogador via CSV)

Cartas que o jogador tem no Arena.

```sql
CREATE TABLE my_collection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_id TEXT NOT NULL,
    card_name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    is_foil BOOLEAN DEFAULT 0,
    acquired_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (card_id) REFERENCES cards(id)
);

CREATE INDEX idx_collection_card_name ON my_collection(card_name);
```

### 3. `decks` (preenchida de MTGGoldfish + criados)

Decks conhecidos do meta.

```sql
CREATE TABLE decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,             -- "Mono Red Aggro"
    format TEXT NOT NULL,           -- "standard", "historic", etc
    archetype TEXT NOT NULL,        -- "aggro", "control", etc
    sub_archetype TEXT,             -- "burn", "prowess"
    color_identity TEXT,            -- JSON: ["R"]
    winrate_meta REAL,              -- 0.65 = 65%
    popularity REAL,                -- 0.15 = 15% do meta
    source TEXT,                    -- "MTGGoldfish", "manual"
    is_active BOOLEAN DEFAULT 1,    -- se ainda válido no meta
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME
);

CREATE INDEX idx_decks_format ON decks(format);
CREATE INDEX idx_decks_archetype ON decks(archetype);
```

### 4. `deck_cards` (relação deck ↔ cartas)

Cartas que compõem cada deck.

```sql
CREATE TABLE deck_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL,
    card_id TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 4,
    is_sideboard BOOLEAN DEFAULT 0,
    FOREIGN KEY (deck_id) REFERENCES decks(id),
    FOREIGN KEY (card_id) REFERENCES cards(id)
);

CREATE INDEX idx_deck_cards_deck ON deck_cards(deck_id);
```

### 5. `game_sessions` (uma sessão = várias partidas)

Uma sessão de jogo (você se sentou pra jogar).

```sql
CREATE TABLE game_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at DATETIME NOT NULL,
    ended_at DATETIME,
    format TEXT NOT NULL,           -- "standard", "draft", etc
    bo_type INTEGER,                -- 1 or 3
    deck_used_id INTEGER,           -- FK pro deck
    total_games INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    notes TEXT,
    FOREIGN KEY (deck_used_id) REFERENCES decks(id)
);
```

### 6. `games` (cada partida individual)

Cada partida disputada.

```sql
CREATE TABLE games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    game_number INTEGER,            -- 1, 2, 3 (se BO3)
    my_deck_id INTEGER NOT NULL,
    opponent_deck_identified TEXT,  -- "Simic Ramp"
    opponent_confidence REAL,       -- 0.87
    winner TEXT,                    -- "me" or "opponent"
    total_turns INTEGER,
    duration_seconds INTEGER,
    started_at DATETIME,
    ended_at DATETIME,
    FOREIGN KEY (session_id) REFERENCES game_sessions(id),
    FOREIGN KEY (my_deck_id) REFERENCES decks(id)
);
```

### 7. `game_states` (snapshot de cada turno)

Estado do jogo em cada turno.

```sql
CREATE TABLE game_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    turn INTEGER NOT NULL,
    phase TEXT,                     -- "main1", "combat", etc
    my_life INTEGER,
    opponent_life INTEGER,
    my_hand_json TEXT,              -- JSON array de cartas
    my_battlefield_json TEXT,
    opponent_battlefield_json TEXT,
    my_mana_available TEXT,          -- "3,R,R"
    opponent_mana_estimated TEXT,
    captured_at DATETIME,
    FOREIGN KEY (game_id) REFERENCES games(id)
);
```

### 8. `ia_recommendations` (histórico de recomendações)

Cada recomendação da IA e se você seguiu.

```sql
CREATE TABLE ia_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    turn INTEGER,
    recommended_action TEXT,         -- JSON completo da recomendação
    reasoning TEXT,
    followed BOOLEAN,
    actual_action TEXT,              -- o que você fez
    outcome_impact REAL,             -- +/- vetor de impacto
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id)
);
```

### 9. `deck_vectors` (aprendizado adaptativo)

Performance de cada deck.

```sql
CREATE TABLE deck_vectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deck_id INTEGER NOT NULL,
    sessions_played INTEGER DEFAULT 0,
    total_games INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    winrate REAL,
    vector_score REAL,              -- +0.36 = positivo, -0.20 = negativo
    trend TEXT,                     -- "positive", "negative", "stable"
    last_played_at DATETIME,
    confidence_score REAL,          -- 0.85 = confiante
    FOREIGN KEY (deck_id) REFERENCES decks(id)
);
```

### 10. `matchup_vectors` (matriz de matchups)

Como cada deck seu se sai contra cada arquétipo.

```sql
CREATE TABLE matchup_vectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    my_deck_id INTEGER NOT NULL,
    opponent_archetype TEXT NOT NULL,  -- "aggro", "control", etc
    games INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    vector_score REAL,              -- -1.0 to +1.0
    trend TEXT,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (my_deck_id) REFERENCES decks(id)
);

CREATE INDEX idx_matchup_deck_archetype ON matchup_vectors(my_deck_id, opponent_archetype);
```

## 🔍 Queries Frequentes

### Buscar carta por nome (fuzzy):
```sql
SELECT * FROM cards 
WHERE name LIKE ? 
LIMIT 5;
-- Ou usar SIMILAR em SQLite via ext_string
```

### Meu melhor deck no formato Standard:
```sql
SELECT d.name, dv.winrate, dv.vector_score
FROM decks d
JOIN deck_vectors dv ON dv.deck_id = d.id
WHERE d.format = 'standard'
ORDER BY dv.vector_score DESC, dv.games DESC
LIMIT 5;
```

### Sessão atual:
```sql
SELECT * FROM game_sessions
WHERE ended_at IS NULL
ORDER BY started_at DESC
LIMIT 1;
```

### Recomendações da IA (últimos 30 dias):
```sql
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN followed = 1 THEN 1 ELSE 0 END) as followed,
    AVG(outcome_impact) as avg_impact
FROM ia_recommendations
WHERE created_at > DATE('now', '-30 days');
```

### Matchup contra Ramp:
```sql
SELECT 
    d.name as my_deck,
    mv.games,
    mv.wins,
    ROUND(CAST(mv.wins AS REAL) / mv.games * 100, 1) as winrate,
    mv.vector_score
FROM matchup_vectors mv
JOIN decks d ON d.id = mv.my_deck_id
WHERE mv.opponent_archetype = 'ramp'
ORDER BY mv.vector_score DESC;
```

## 🎯 Migrations

Criar em `src/db/migrations/`:
- `001_initial_schema.sql` - todas as tabelas acima
- `002_indexes.sql` - índices adicionais
- `003_scryfall_data.sql` - carrega bulk data

Executar via SQLAlchemy Alembic ou script Python simples.

## 💾 Backup

Sistema faz backup automático:
- Diário: `~/magic-ai/backups/data-2026-01-18.db`
- Retém últimos 7 dias
- Se corromper, restaura do último bom

## 🚀 Performance

Objetivo:
- **Query card por nome**: < 5ms
- **Insert de game state**: < 10ms
- **Query complexa (matchup)**: < 20ms

SQLite comporta isso facilmente com os índices acima.
