# 🚀 ROADMAP: MVP em 1 Semana

Plano de execução dia-a-dia para ter o sistema rodando em 7 dias.

## 📊 Visão Geral

| Dia | Foco | Entregável | Tempo |
|-----|------|------------|-------|
| 1 | Setup + Infraestrutura | Ambiente funcional | 2-3h |
| 2 | Banco de dados + Scryfall | 30k cartas em SQLite | 2-3h |
| 3 | Integração OBS | Captura de frames | 3-4h |
| 4 | OCR + GameState | Detecção de cartas | 3-4h |
| 5 | IA (Deck ID + Recomendação) | Análise em tempo real | 3-4h |
| 6 | Terminal UI | Dashboard bonito | 2-3h |
| 7 | Testes + Refinamento | Sistema completo | 2-3h |

**Total: ~20-25h em 7 dias.**

---

## 📅 DIA 1: Setup + Infraestrutura

### Objetivo
Ambiente Python funcional com todas as dependências.

### Tarefas
- [ ] Instalar Python 3.11+ (se ainda não tem)
- [ ] Criar virtualenv: `python -m venv venv`
- [ ] Ativar: `venv\Scripts\activate` (Windows) ou `source venv/bin/activate`
- [ ] Criar `requirements.txt` com dependências
- [ ] Instalar: `pip install -r requirements.txt`
- [ ] Configurar `.env` com `ANTHROPIC_API_KEY`
- [ ] Criar estrutura de pastas
- [ ] Fazer `git init` e primeiro commit

### `requirements.txt`
```
anthropic>=0.30.0
obs-websocket-py>=0.6.0
opencv-python>=4.9.0
mss>=9.0.1
httpx>=0.27.0
websockets>=12.0
sqlalchemy>=2.0.0
alembic>=1.13.0
rich>=13.7.0
pydantic>=2.6.0
pandas>=2.2.0
numpy>=1.26.0
python-dotenv>=1.0.0
```

### Estrutura de Pastas
```bash
mkdir magic-ai-advisor
cd magic-ai-advisor
mkdir -p src/{models,services,ui,db,utils}
mkdir -p data tests logs
touch src/__init__.py src/main.py
touch .env .gitignore README.md
```

### Test que deve passar
```python
# test_day1.py
from anthropic import Anthropic
import os
from dotenv import load_dotenv

load_dotenv()

def test_env():
    assert os.getenv("ANTHROPIC_API_KEY"), "❌ API key faltando"
    print("✅ Ambiente configurado")

def test_claude_api():
    client = Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10,
        messages=[{"role": "user", "content": "Say hi"}]
    )
    assert msg.content, "❌ API não respondeu"
    print("✅ Claude API funcionando")

if __name__ == "__main__":
    test_env()
    test_claude_api()
```

---

## 📅 DIA 2: Banco de Dados + Scryfall

### Objetivo
SQLite pronto com todas as ~30k cartas de Magic.

### Tarefas
- [ ] Criar `src/db/database.py` (conexão SQLite)
- [ ] Criar modelos SQLAlchemy (Card, Deck, GameSession)
- [ ] Criar migrations
- [ ] Baixar bulk data do Scryfall
- [ ] Popular SQLite com todas as cartas
- [ ] Criar índices pra queries rápidas
- [ ] Testar busca por nome (fuzzy)

### Código chave
```python
# src/services/scryfall_service.py
import httpx
import gzip
import json
from src.db.database import get_session
from src.models.card import Card

async def download_and_import_scryfall():
    """Baixa todas as cartas do Scryfall e importa"""
    
    print("📥 Baixando Scryfall bulk data...")
    
    async with httpx.AsyncClient(timeout=120) as client:
        # 1. Pega URL do bulk data
        resp = await client.get("https://api.scryfall.com/bulk-data")
        bulk_files = resp.json()["data"]
        
        default_cards = next(
            f for f in bulk_files 
            if f['type'] == 'default_cards'
        )
        
        # 2. Baixa
        resp = await client.get(default_cards['download_uri'])
        
        # 3. Descompacta
        cards_data = json.loads(gzip.decompress(resp.content))
        
        print(f"✅ {len(cards_data)} cartas baixadas")
    
    # 4. Importa pro SQLite
    session = get_session()
    for card_data in cards_data:
        card = Card(
            id=card_data['id'],
            name=card_data['name'],
            mana_cost=card_data.get('mana_cost', ''),
            cmc=card_data.get('cmc', 0),
            type_line=card_data.get('type_line', ''),
            oracle_text=card_data.get('oracle_text', ''),
            colors=json.dumps(card_data.get('colors', [])),
            keywords=json.dumps(card_data.get('keywords', [])),
            # ...
        )
        session.add(card)
    
    session.commit()
    print(f"✅ Salvei {len(cards_data)} cartas no SQLite")

# Rodar: python -m src.services.scryfall_service
```

### Test que deve passar
```python
# test_day2.py
from src.services.card_service import CardService

def test_card_lookup():
    service = CardService()
    card = service.find_by_name("Lightning Bolt")
    assert card, "❌ Lightning Bolt não encontrada"
    print(f"✅ Encontrei: {card.name} - {card.mana_cost}")

def test_fuzzy_search():
    service = CardService()
    results = service.fuzzy_search("Lightning Blt")  # Typo
    assert results, "❌ Fuzzy search não funcionou"
    print(f"✅ Fuzzy encontrou: {[r.name for r in results]}")

if __name__ == "__main__":
    test_card_lookup()
    test_fuzzy_search()
```

---

## 📅 DIA 3: Integração OBS

### Objetivo
Python capturando screenshots do OBS em tempo real.

### Tarefas
- [ ] Instalar `obs-websocket-py`
- [ ] Configurar OBS WebSocket (porta 4455)
- [ ] Criar `src/services/obs_service.py`
- [ ] Testar conexão
- [ ] Testar captura de screenshot
- [ ] Fazer loop de captura contínua
- [ ] Salvar screenshots em `logs/` pra debug

### Código base
```python
# src/services/obs_service.py
from obswebsocket import obsws, requests
import asyncio
import base64
from datetime import datetime

class OBSService:
    def __init__(self):
        self.ws = obsws("localhost", 4455, "MagicAI_2026!")
        self.frame_count = 0
    
    async def connect(self):
        self.ws.connect()
        print("✅ Conectado ao OBS")
    
    async def get_screenshot(self, width=1280, height=720) -> bytes:
        try:
            screenshot = self.ws.call(requests.GetSourceScreenshot(
                sourceName="Game Capture 1903",
                imageFormat="png",
                imageWidth=width,
                imageHeight=height
            ))
            data_url = screenshot.getImageData()
            _, encoded = data_url.split(",", 1)
            return base64.b64decode(encoded)
        except Exception as e:
            print(f"❌ Erro: {e}")
            return None
    
    async def capture_loop(self, interval_ms=300, save_debug=False):
        while True:
            frame = await self.get_screenshot()
            if frame:
                self.frame_count += 1
                if save_debug and self.frame_count % 10 == 0:
                    with open(f"logs/frame_{self.frame_count}.png", "wb") as f:
                        f.write(frame)
                yield frame
            await asyncio.sleep(interval_ms / 1000)

# Test
async def main():
    obs = OBSService()
    await obs.connect()
    
    async for frame in obs.capture_loop(save_debug=True):
        print(f"📸 Frame {obs.frame_count}: {len(frame)} bytes")
        if obs.frame_count >= 20:
            break

if __name__ == "__main__":
    asyncio.run(main())
```

### Test que deve passar
- Rodar Arena
- Rodar OBS com Game Capture 1903
- Rodar script Python
- Deve salvar 2 screenshots em `logs/`
- Ver se as capturas mostram o Arena

---

## 📅 DIA 4: OCR + GameState

### Objetivo
Reconhecer cartas dos screenshots e construir GameState.

### Tarefas
- [ ] Criar `src/services/vision_service.py`
- [ ] Criar `src/models/game_state.py` (Pydantic)
- [ ] Detectar mudanças entre frames (diff)
- [ ] Enviar mudanças pra Claude Vision
- [ ] Fazer matching com SQLite (cache)
- [ ] Atualizar GameState

### Código base
```python
# src/services/vision_service.py
from anthropic import Anthropic
import base64
from src.services.card_service import CardService

class VisionService:
    def __init__(self):
        self.client = Anthropic()
        self.card_service = CardService()
    
    async def identify_cards_in_image(self, image_bytes: bytes) -> list[dict]:
        """Envia frame pra Claude Vision e retorna cartas identificadas"""
        
        image_b64 = base64.b64encode(image_bytes).decode()
        
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_b64
                        }
                    },
                    {
                        "type": "text",
                        "text": """Identifique todas as cartas de Magic visíveis nesta imagem.
                        
                        Para cada carta, retorne JSON:
                        - name: nome exato
                        - location: "player_hand" | "player_battlefield" | "opponent_battlefield"
                        - position: {x, y} no board (aproximado)
                        
                        Também identifique:
                        - my_life: minha vida
                        - opponent_life: vida do oponente
                        - my_mana: minha mana disponível
                        - turn: turno atual
                        - phase: fase atual
                        
                        Retorne JSON estruturado."""
                    }
                ]
            }]
        )
        
        # Parse response
        text = response.content[0].text
        # Extract JSON, etc.
        return parsed_data
```

### Test que deve passar
- Rodar Arena com match em andamento
- Rodar script
- Deve identificar cartas + estado do jogo

---

## 📅 DIA 5: IA (Deck ID + Recomendação)

### Objetivo
Sistema que identifica deck do oponente e recomenda jogada.

### Tarefas
- [ ] Criar `src/services/ia_service.py`
- [ ] Prompts do `prompts/*.md` implementados
- [ ] Deck identification (com histórico)
- [ ] Play recommendation
- [ ] Salvar recomendações no SQLite
- [ ] Feedback loop

### Código base
```python
# src/services/ia_service.py
from anthropic import Anthropic
from src.models.game_state import GameState
import json

class IAService:
    def __init__(self):
        self.client = Anthropic()
    
    async def identify_opponent_deck(self, game_state: GameState):
        """Identifica o deck do oponente"""
        
        system = self._load_prompt("deck-identifier")
        user = self._build_user_prompt(game_state, "identify")
        
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            system=system,
            messages=[{"role": "user", "content": user}]
        )
        
        return self._parse_json(response.content[0].text)
    
    async def recommend_play(self, game_state: GameState, opponent_deck: dict):
        """Recomenda melhor jogada"""
        
        system = self._load_prompt("play-recommender")
        user = self._build_user_prompt(game_state, "play", opponent_deck)
        
        response = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2500,
            system=system,
            messages=[{"role": "user", "content": user}]
        )
        
        return self._parse_json(response.content[0].text)
```

---

## 📅 DIA 6: Terminal UI

### Objetivo
Dashboard bonito e responsivo no terminal.

### Tarefas
- [ ] Instalar `rich`
- [ ] Criar `src/ui/dashboard.py`
- [ ] Layout com painéis (life, mana, hand, recommendation)
- [ ] Cores e ícones
- [ ] Refresh automático quando GameState muda
- [ ] Atalhos de teclado (space = pausa, q = quit)

### Código base
```python
# src/ui/dashboard.py
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.layout import Layout
from rich.live import Live

class Dashboard:
    def __init__(self):
        self.console = Console()
        self.layout = self._build_layout()
    
    def _build_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=3)
        )
        
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=2)
        )
        
        return layout
    
    def update(self, game_state, recommendation):
        # Header: título + status
        self.layout["header"].update(
            Panel("🎴 MAGIC AI ADVISOR", style="bold cyan")
        )
        
        # Left: estado do jogo
        game_info = Table(title="Estado")
        game_info.add_column("Item")
        game_info.add_column("Valor")
        game_info.add_row("👤 Minha vida", str(game_state.my_life))
        game_info.add_row("🤖 Vida oponente", str(game_state.opponent_life))
        game_info.add_row("🎲 Turno", str(game_state.turn))
        self.layout["left"].update(Panel(game_info))
        
        # Right: recomendação
        rec_panel = Panel(
            f"💡 {recommendation['action']}\n\n{recommendation['reasoning']}",
            title="Recomendação",
            border_style="green"
        )
        self.layout["right"].update(rec_panel)
```

---

## 📅 DIA 7: Testes + Refinamento

### Objetivo
Sistema completo, testado, e polido.

### Tarefas
- [ ] Teste end-to-end (Arena → OBS → Python → Recomendação)
- [ ] Ajustar latência (< 2s)
- [ ] Salvar sessão no SQLite
- [ ] Sistema de vetorização de decks
- [ ] Documentar tudo
- [ ] Commit final

### Test end-to-end
1. Abrir Arena com match
2. Abrir OBS
3. Rodar sistema
4. Sistema deve mostrar:
   - Meu deck (que importei)
   - Cartas na minha mão
   - Deck do oponente (identificado)
   - Recomendação da jogada
5. Salvar resultado (win/loss)
6. Winrate atualizado

---

## 🎯 Marcos Importantes

- **Fim do Dia 3**: OBS + Python conectados
- **Fim do Dia 5**: IA funcionando end-to-end
- **Fim do Dia 6**: UI bonita
- **Fim do Dia 7**: Sistema completo

## 🚨 Se Der Problema

**Problema no dia 3 (OBS)**: Usar `mss` como fallback (não precisa de OBS)
**Problema no dia 4 (OCR)**: Reduzir resolução ou usar cache mais agressivo
**Problema no dia 5 (IA)**: Simplificar prompts ou usar `claude-haiku` (mais barato)

## ✅ Success Criteria

- [ ] Sistema roda 30+ minutos sem crash
- [ ] Identificação de deck > 80% de precisão
- [ ] Latência < 2s por recomendação
- [ ] Winrate aumenta > 10% em 20 jogos
- [ ] Você entende cada linha de código
