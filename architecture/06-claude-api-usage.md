# 🤖 Como Usamos a Claude API

Guia de uso otimizado da API para o projeto.

## Modelos Escolhidos

### Claude Sonnet 4.6
```
Uso: análise estratégica, deck ID, recomendação
Custo: $3/M input tokens, $15/M output tokens
Latência: ~800ms típico
```

### Claude Vision (Sonnet)
```
Uso: OCR de cartas do frame
Custo: mesmo que Sonnet
Latência: ~500ms para imagem 1280x720
```

## Estratégia de Uso

### 1. Cache Agressivo
- Mesma pergunta = mesma resposta (Redis/memory)
- Deck já identificado = não re-analisa até mudar
- Cartas no cache = não pede pra Vision de novo

### 2. Batching
- Se identificar 3 cartas em 1 frame, chama Vision 1x (não 3)
- Se estado mudou pouco, aguarda mais mudança

### 3. Streaming (para UI)
- Recomendações streaming pra usuário ver pensamento
- Melhora percepção de velocidade

### 4. Prompt Caching
Anthropic tem prompt caching (economia até 90% em tokens):
```python
# Marcar system prompt como cacheable
messages = client.messages.create(
    model="claude-sonnet-4-6",
    system=[
        {
            "type": "text",
            "text": long_system_prompt,
            "cache_control": {"type": "ephemeral"}  # cachea!
        }
    ],
    ...
)
```

## Estrutura de Chamada Otimizada

```python
# src/services/ia_service.py
from anthropic import Anthropic
import hashlib
import json
from functools import lru_cache

class IAService:
    def __init__(self):
        self.client = Anthropic()
        self._cache = {}
    
    def _cache_key(self, prompt: str, model: str) -> str:
        """Cria chave única pro cache"""
        content = f"{model}:{prompt}"
        return hashlib.md5(content.encode()).hexdigest()
    
    async def call_claude(
        self,
        system: str,
        user: str,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2000,
        temperature: float = 0.3,
        use_cache: bool = True
    ) -> dict:
        """Chamada genérica com cache"""
        
        # Cache check
        if use_cache:
            key = self._cache_key(user, model)
            if key in self._cache:
                return self._cache[key]
        
        # API call
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"}
                }
            ] if len(system) > 1000 else system,
            messages=[{"role": "user", "content": user}]
        )
        
        # Parse JSON response
        text = response.content[0].text
        result = self._extract_json(text)
        
        # Cache
        if use_cache:
            self._cache[key] = result
        
        return result
    
    def _extract_json(self, text: str) -> dict:
        """Extrai JSON de resposta que pode ter markdown"""
        # Remove markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        return json.loads(text.strip())
```

## Uso por Cenário

### Cenário 1: Frame Idêntico (nada mudou)
```
Diff detector: NÃO mudou
Ação: NÃO chama Claude
Latência: 0ms
Custo: 0
```

### Cenário 2: Só vida mudou
```
Diff detector: só vida
Vision: NÃO precisa
IA: só recalcula recommendation (~800ms)
Custo: ~$0.005
```

### Cenário 3: Nova carta apareceu
```
Diff detector: nova região no board
Vision: identifica carta (~500ms)
Card matcher: consulta SQLite (~5ms)
IA: reidentifica deck + recomenda (~1s)
Total: ~1.5s
Custo: ~$0.02
```

### Cenário 4: Grande mudança (novo turno)
```
Diff detector: várias mudanças
Vision: 1 chamada com frame completo (~800ms)
IA: reidentifica tudo (~1s)
Total: ~1.8s
Custo: ~$0.03
```

## Estimativa de Custo Real

### Sessão típica (5 jogos, 30 minutos):
```
Frames capturados: ~5000 (3 FPS x 1800s)
Diffs detectados: ~200
Vision calls: ~50 (só quando novo card)
IA calls: ~150 (recommendation)

Vision: 50 x $0.003 = $0.15
IA: 150 x $0.006 = $0.90
Total: $1.05/sessão
```

### Uso mensal (20 sessões):
```
20 x $1.05 = $21/mês
```

Não caro. Melhor que assinar app pronto.

## Otimizações Adicionais

### 1. Usar Haiku para tarefas simples
```python
# Para tarefas rápidas e simples (deck ID inicial):
model="claude-haiku-4-5"  # 10x mais barato
```

### 2. Prompt engineering
- Prompts curtos = menos tokens
- JSON output = menos verbosidade
- Exemplos in-context = melhor qualidade

### 3. Rate limiting
```python
import asyncio

class RateLimiter:
    def __init__(self, max_per_minute=50):
        self.max = max_per_minute
        self.calls = []
    
    async def acquire(self):
        now = datetime.now()
        # Remove calls > 1 min
        self.calls = [c for c in self.calls if (now - c).seconds < 60]
        
        if len(self.calls) >= self.max:
            wait = 60 - (now - self.calls[0]).seconds
            print(f"⏳ Rate limit, aguardando {wait}s...")
            await asyncio.sleep(wait)
        
        self.calls.append(now)
```

## Monitoramento

```python
# src/utils/api_metrics.py
class APIMetrics:
    def __init__(self):
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.cost = 0
    
    def track(self, response):
        self.calls += 1
        self.tokens_in += response.usage.input_tokens
        self.tokens_out += response.usage.output_tokens
        
        # Custo Sonnet
        cost_in = response.usage.input_tokens * 0.003 / 1000
        cost_out = response.usage.output_tokens * 0.015 / 1000
        self.cost += cost_in + cost_out
    
    def report(self):
        print(f"""
📊 API METRICS:
   Total calls: {self.calls}
   Tokens IN: {self.tokens_in:,}
   Tokens OUT: {self.tokens_out:,}
   Custo total: ${self.cost:.4f}
        """)
```

## 🚨 Limites e Cuidados

- **Rate limit**: ~50 req/min por padrão
- **Max output**: 8192 tokens (mais que suficiente)
- **Timeout**: 60s (nossos calls são < 2s)
- **Retry**: implementar retry com backoff

## 🎯 Segurança

- API key em `.env`, nunca em código
- `.env` em `.gitignore`
- Não commitar screenshots com dados sensíveis
