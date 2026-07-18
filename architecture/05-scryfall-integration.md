# 🃏 Integração com Scryfall API

Como usar o Scryfall para popular o banco de cartas.

## O que é Scryfall?

- **Scryfall** = base de dados oficial de todas as cartas de Magic
- Grátis, sem autenticação necessária
- API REST: https://api.scryfall.com
- Bulk data: baixa TUDO uma vez (200MB descompactado)

## Estratégia

### Uma vez (setup):
1. Baixar bulk data (`default-cards.json.gz`)
2. Descompactar (~200MB JSON)
3. Importar cada carta no SQLite
4. Total: ~30k cartas indexadas

### Diariamente (opcional):
- Verificar se novo bulk foi lançado
- Se sim, sincronizar cartas novas
- Scryfall atualiza a cada 24h

## Implementação

### 1. Descobrir URL do Bulk Data

```python
import httpx
import gzip
import json

async def get_bulk_data_url():
    """Pega URL do arquivo de bulk data mais recente"""
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://api.scryfall.com/bulk-data")
        data = resp.json()
        
        # Pega o "default_cards" (todas as cartas em inglês, únicas)
        default = next(
            item for item in data['data']
            if item['type'] == 'default_cards'
        )
        
        return {
            'url': default['download_uri'],
            'size_mb': default['compressed_size'] / 1024 / 1024,
            'updated_at': default['updated_at']
        }
```

### 2. Download

```python
async def download_bulk(url: str, output_path: str = "scryfall.json.gz"):
    """Baixa o arquivo (200MB)"""
    async with httpx.AsyncClient(timeout=300) as client:
        print(f"📥 Baixando de {url}...")
        
        async with client.stream("GET", url) as response:
            total = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Progress
                    percent = (downloaded / total) * 100
                    print(f"  {percent:.1f}% ({downloaded/1024/1024:.0f}MB)", end='\r')
        
        print(f"\n✅ Baixado: {output_path}")
```

### 3. Import para SQLite

```python
import json
import gzip
from sqlalchemy.orm import Session
from src.models.card import Card
from src.db.database import get_session

async def import_scryfall_to_sqlite(bulk_path: str = "scryfall.json.gz"):
    """Importa todas as cartas do bulk data"""
    
    # 1. Descompacta e lê
    print("📖 Lendo arquivo...")
    with gzip.open(bulk_path, 'rt', encoding='utf-8') as f:
        cards_data = json.load(f)
    
    print(f"📊 {len(cards_data)} cartas encontradas")
    
    # 2. Importa em batches
    session = get_session()
    batch_size = 1000
    imported = 0
    
    for i in range(0, len(cards_data), batch_size):
        batch = cards_data[i:i+batch_size]
        
        for card_data in batch:
            card = Card(
                id=card_data['id'],
                name=card_data['name'],
                mana_cost=card_data.get('mana_cost', ''),
                cmc=card_data.get('cmc', 0),
                type_line=card_data.get('type_line', ''),
                oracle_text=card_data.get('oracle_text', ''),
                colors=json.dumps(card_data.get('colors', [])),
                color_identity=json.dumps(card_data.get('color_identity', [])),
                keywords=json.dumps(card_data.get('keywords', [])),
                power=parse_power_toughness(card_data.get('power')),
                toughness=parse_power_toughness(card_data.get('toughness')),
                loyalty=parse_power_toughness(card_data.get('loyalty')),
                rarity=card_data.get('rarity', 'common'),
                set_code=card_data.get('set', ''),
                set_name=card_data.get('set_name', ''),
                image_url=card_data.get('image_uris', {}).get('normal', ''),
                scryfall_url=card_data.get('scryfall_uri', ''),
                legalities=json.dumps(card_data.get('legalities', {})),
            )
            session.add(card)
        
        # Commit a cada batch
        session.commit()
        imported += len(batch)
        
        print(f"  ✅ Importado: {imported}/{len(cards_data)}", end='\r')
    
    print(f"\n✅ TOTAL: {imported} cartas importadas")

def parse_power_toughness(val):
    """Converte power/toughness (pode ser '*', 'X', número, ou None)"""
    if val is None or val in ('*', 'X'):
        return None
    try:
        return int(val)
    except ValueError:
        return None
```

### 4. Busca Otimizada

```python
# src/services/card_service.py
from sqlalchemy import select
from difflib import get_close_matches
from src.db.database import get_session
from src.models.card import Card

class CardService:
    def __init__(self):
        self.session = get_session()
        # Cache em memória das cartas mais buscadas
        self._name_cache = {}
        self._preload_common_cards()
    
    def _preload_common_cards(self):
        """Carrega as 100 cartas mais comuns em memória"""
        common = ['Lightning Bolt', 'Counterspell', 'Thoughtseize', 
                  'Fatal Push', 'Cultivate', 'Wrath of God']
        for name in common:
            card = self.find_by_name(name)
            if card:
                self._name_cache[name.lower()] = card
    
    def find_by_name(self, name: str) -> Card | None:
        """Busca exata por nome (case insensitive)"""
        # Cache first
        if name.lower() in self._name_cache:
            return self._name_cache[name.lower()]
        
        # DB query
        card = self.session.scalar(
            select(Card).where(Card.name.ilike(name))
        )
        
        if card:
            self._name_cache[name.lower()] = card
        
        return card
    
    def fuzzy_search(self, partial: str, limit: int = 5) -> list[Card]:
        """Busca fuzzy (typo tolerante)"""
        # Pega todos os nomes
        all_names = self.session.execute(
            select(Card.name)
        ).scalars().all()
        
        # Encontra matches próximos
        matches = get_close_matches(
            partial.lower(),
            [n.lower() for n in all_names],
            n=limit,
            cutoff=0.7
        )
        
        # Busca as cartas
        return [self.find_by_name(m) for m in matches if m]
    
    def search_by_type(self, type_line: str) -> list[Card]:
        """Busca por tipo (ex: 'Creature - Human')"""
        return self.session.execute(
            select(Card).where(Card.type_line.ilike(f"%{type_line}%"))
        ).scalars().all()
    
    def search_creatures_by_stats(self, min_power=0, max_cmc=99) -> list[Card]:
        """Busca criaturas por power/CMC"""
        return self.session.execute(
            select(Card).where(
                Card.power >= min_power,
                Card.cmc <= max_cmc,
                Card.type_line.ilike("%Creature%")
            )
        ).scalars().all()
```

### 5. Atualização Diária (opcional)

```python
# src/services/scryfall_sync.py
from datetime import datetime, timedelta

async def check_for_updates():
    """Verifica se há atualização do Scryfall"""
    
    # Última verificação salva
    last_check = get_last_check_timestamp()
    
    if last_check and (datetime.now() - last_check) < timedelta(hours=24):
        print("⏭️  Última check foi há < 24h, pulando")
        return
    
    # Pega info do bulk mais recente
    bulk_info = await get_bulk_data_url()
    updated_at = datetime.fromisoformat(bulk_info['updated_at'])
    
    # Verifica se é mais recente que último import
    last_import = get_last_import_timestamp()
    
    if updated_at > last_import:
        print(f"🔄 Nova versão disponível!")
        await download_bulk(bulk_info['url'])
        await import_scryfall_to_sqlite()
        save_last_import_timestamp(datetime.now())
    else:
        print("✅ Já está atualizado")
    
    save_last_check_timestamp(datetime.now())
```

## 🚀 Performance

### Tempo de import inicial
- Download: ~2-5 min (depends de internet)
- Descompactação: ~10s
- Import SQLite: ~2-3 min (30k cartas)
- **Total: ~5-8 min** (uma vez)

### Tempo de busca
- **find_by_name** com cache: < 1ms
- **find_by_name** sem cache: ~5ms
- **fuzzy_search**: ~50ms
- **search_by_type**: ~20ms

## 📊 Tamanho no Disco

- SQLite DB: ~150MB (com índices)
- Backup: ~50MB (só dados essenciais)

## 🎯 Alternativas ao Scryfall

Caso queira testar outros:

**17Lands** (só Draft/Limited):
- URL: https://www.17lands.com
- Focus: winrates de cartas em Draft
- Use case: pick order

**MTGJSON** (dados mais completos):
- URL: https://mtgjson.com
- Focus: dados detalhados
- Use case: análise avançada

**Recomendação**: **Scryfall** cobre 99% dos casos. Simples e rápido.
