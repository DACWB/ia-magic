# CLAUDE.md - Contexto para Claude Code

Este arquivo é lido AUTOMATICAMENTE pelo Claude Code toda vez que abre este projeto. Serve como memória persistente do projeto.

## 🎯 O que é este projeto

Sistema de IA em tempo real para MTG Arena. Assiste o jogador:
1. **Pré-jogo**: monta o melhor deck baseado nas cartas disponíveis + formato
2. **Durante o jogo**: identifica o deck do oponente e recomenda jogadas
3. **Entre BO3**: ajusta sideboard estrategicamente
4. **Pós-jogo**: aprende com resultados (vetorização de decks)

## 👤 Usuário

**Usuário** - Médico oftalmologista, professor de IA aplicada à medicina (o projeto didático).  
Este projeto tem propósito duplo: (1) jogar Magic melhor, (2) material didático de ML/AI aplicado.

**Estilo de trabalho**: TDAH, agilidade, MVP rápido, código didático em português.

## 📁 Estrutura do Projeto

```
magic-ai-advisor/
├── docs/           # Documentação conceitual
├── architecture/   # Documentação técnica
├── prompts/        # Prompts do Claude para cada fase
├── data/           # CSV, JSON de suporte
├── src/            # Código Python (a criar)
├── tests/          # Testes
└── ROADMAP-1-SEMANA.md  # Plano diário
```

## 🛠️ Stack Técnico

- **Python 3.11+**
- **SQLite** (banco local)
- **OBS Studio** + WebSocket (captura)
- **Claude Sonnet 4.6** (IA)
- **Claude Vision** (OCR)
- **Rich** (terminal UI)
- **FastAPI** (backend interno)
- **SQLAlchemy** (ORM)

**NUNCA usar**:
- Web UI (usuário pediu texto)
- Cloud database (SQLite local é suficiente)
- Docker (rodar direto no PC)

## 🎯 Princípios

1. **Simplicidade > Complexidade**: MVP em 1 semana
2. **Local > Cloud**: Roda no PC do jogador
3. **Texto > Visual**: Terminal com Rich
4. **Didático > Otimizado**: Código explicado em português
5. **Testável > Perfeito**: Testa cada camada

## 📚 Documentação Chave

Antes de codificar qualquer coisa, LEIA:

1. `docs/01-visao-geral.md` - Fluxo completo
2. `docs/02-fases-do-uso.md` - Perspectiva do usuário
3. `architecture/01-stack-tecnico.md` - Tecnologias
4. `architecture/02-camadas-sistema.md` - 5 camadas
5. `ROADMAP-1-SEMANA.md` - Plano diário

## 🚀 Como Executar (para Claude Code)

Quando o jogador pedir pra começar, siga o ROADMAP:

**Dia 1**: Setup (venv, requirements, .env, estrutura)  
**Dia 2**: Banco + Scryfall bulk import  
**Dia 3**: Integração OBS  
**Dia 4**: OCR + GameState  
**Dia 5**: IA (Deck ID + Recomendação)  
**Dia 6**: Terminal UI (Rich)  
**Dia 7**: Testes + Refinamento

## ⚙️ Configurações Importantes

### OBS
- Modo: **Game Capture 1903**
- WebSocket porta: **4455**
- Password: definir em `.env`

### Claude API
- Modelo principal: `claude-sonnet-4-6`
- Modelo Vision: `claude-sonnet-4-6` (mesmo, tem vision)
- Modelo simples: `claude-haiku-4-5` (fallback barato)

### SQLite
- Arquivo: `~/magic-ai/data.db`
- ~30k cartas (Scryfall bulk)
- Indexes em name, type_line, cmc

## 🎓 Estilo de Código

- **Comentários em português** (didático pra o projeto didático)
- **Type hints sempre** (Pydantic + typing)
- **Docstrings estilo Google**
- **Nomes descritivos** (não abreviar)
- **Testes primeiro** (TDD leve)

Exemplo:
```python
from pydantic import BaseModel

class Card(BaseModel):
    """Representa uma carta de Magic: The Gathering.
    
    Attributes:
        id: UUID do Scryfall (único global)
        name: Nome oficial da carta em inglês
        mana_cost: Custo em símbolos (ex: '{2}{R}{R}')
        cmc: Custo convertido (soma numérica)
    """
    id: str
    name: str
    mana_cost: str
    cmc: float
```

## ⚠️ Cuidados Especiais

1. **API Key**: SEMPRE em `.env`, nunca em código
2. **Screenshots**: Não commitar (podem ter dados)
3. **SQLite**: Backup automático diário
4. **Rate limits**: Respeitar 50 req/min do Claude
5. **Custos**: Monitorar (~$6/mês esperado)

## 🎯 Estado Atual do Projeto

**FASE**: Dia 1 concluído (falta só a chave da API no `.env`).

**Feito no Dia 1**:
- `venv/` com **Python 3.14.3** + todas as dependências instaladas
- `src/utils/config.py` — configuração via Pydantic Settings, lida do `.env`
- `src/utils/terminal.py` — força UTF-8 na saída (Windows nasce em cp1252 e
  quebra com emoji; o dashboard do Dia 6 depende disso)
- `src/main.py` — diagnóstico do ambiente (`python -m src.main`)
- `tests/test_day1.py` — 4 testes: deps, config, chave, chamada real à API
- `git init` + primeiro commit

**Decisões tomadas durante o Dia 1**:
- Adicionado `pydantic-settings` ao requirements (é pacote separado do `pydantic`)
- `DATABASE_PATH` relativo do `.env` é resolvido para absoluto em `config.py`,
  ancorado na raiz do projeto — senão rodar de outra pasta cria um banco vazio novo

**PENDÊNCIA DO USUÁRIO**: colar a `ANTHROPIC_API_KEY` real no `.env`.
Enquanto não colar, `test_chave_api_presente` falha de propósito.

**PRÓXIMO PASSO**: Dia 2 do ROADMAP (SQLite + import bulk do Scryfall).

**Comandos**:
```bash
venv\Scripts\python.exe -m src.main              # diagnóstico
venv\Scripts\python.exe -m pytest tests/ -v      # testes
```

## 💬 Comunicação

O jogador prefere:
- Respostas em **português**
- **Passo a passo** claro
- **Sem enrolação**
- **Códigos comentados**
- **Explicações didáticas** (ele ensina isso pros alunos)

Se ele parecer perdido:
- Simplificar
- Mostrar exemplo
- Reduzir escopo se necessário

## 📊 Métricas de Sucesso

Ao final da semana 1:
- [ ] Sistema roda sem crash por 30+ minutos
- [ ] Identifica deck do oponente > 80% precisão
- [ ] Latência < 2s por recomendação  
- [ ] o jogador consegue rodar sozinho
- [ ] Código é entendível para os alunos

## 🔗 Links Úteis

- Scryfall API: https://scryfall.com/docs/api
- OBS WebSocket: https://github.com/obsproject/obs-websocket
- Anthropic API: https://docs.claude.com
- MTG Arena data: https://www.mtggoldfish.com

---

**Última atualização**: Início do projeto (Fase de planejamento concluída).  
**Próximo update**: Após Dia 1 do ROADMAP.
