# CLAUDE.md - Contexto para Claude Code

Este arquivo é lido AUTOMATICAMENTE pelo Claude Code toda vez que abre este projeto. Serve como memória persistente do projeto.

## 🎯 O que é este projeto

Sistema de IA em tempo real para MTG Arena. Assiste o jogador:
1. **Pré-jogo**: monta o melhor deck baseado nas cartas disponíveis + formato
2. **Durante o jogo**: identifica o deck do oponente e recomenda jogadas
3. **Entre BO3**: ajusta sideboard estrategicamente
4. **Pós-jogo**: aprende com resultados (vetorização de decks)

## 👤 Usuário

Médico e professor de IA aplicada à medicina. O projeto tem propósito duplo:
(1) jogar Magic melhor, (2) servir de material didático de ML/IA aplicado.

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
- ~~Web UI (usuário pediu texto)~~ — **regra revogada em 18/07/2026**, pelo
  próprio usuário. Motivo: ele tem UM monitor (2560×1440), e qualquer janela na
  mesma tela disputa espaço com o Arena. Um servidor local resolve porque pode
  ser aberto **no celular**, ao lado do teclado, sem ocupar um pixel do jogo.
  O painel do terminal continua existindo e funcionando.
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
- Modelo principal: **`claude-opus-4-8`** (decisão estratégica: identificar
  deck, recomendar jogada, sideboard). Poucas chamadas por partida, alto valor.
- Modelo fallback: `claude-haiku-4-5` (tarefas mecânicas e baratas)
- ~~Modelo Vision~~: não é mais usado — a percepção vem do log do Arena

⚠️ **Os modelos NÃO aceitam os mesmos parâmetros.** Testado em 18/07/2026:

| Parâmetro | `claude-opus-4-8` | `claude-haiku-4-5` |
|---|---|---|
| `temperature` | ❌ erro 400 | ✅ aceita |
| `thinking: adaptive` | ✅ | — |
| `output_config.effort` | ✅ | — |

Erro exato ao mandar temperature pro Opus 4.8:
```
400 invalid_request_error: `temperature` is deprecated for this model.
```

**Nunca monte esses parâmetros na mão.** Use sempre:
```python
cliente.messages.create(
    model=config.claude_model_primary,
    max_tokens=config.claude_max_tokens_recommendation,
    messages=[...],
    **config.parametros_de_geracao(),   # escolhe o certo pro modelo
)
```
Coberto por `test_parametros_por_modelo` em `tests/test_day1.py`.

Outro detalhe: com raciocínio adaptativo a resposta pode ter um bloco de
pensamento ANTES do texto. Use `resposta.content[-1].text`, não `[0]`.

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

**Feito no Dia 3** (leitura do log do Arena — ver mudança de arquitetura abaixo):
- `src/services/arena_paths.py` — localiza log/instalação/banco do Arena
- `src/services/arena_card_db.py` — `grpId` → nome en/pt (SQLite do jogo, read-only)
- `src/services/arena_log_service.py` — parser incremental do `Player.log`
- `src/models/game_state.py` — `GameState`, `CartaEmJogo`, `Zona`, `Jogador`
- `tests/test_day3.py` — 12 testes (16 no total, todos passando)
- `src/main.py --partida` e `--acompanhar` (ao vivo)

## 🔄 MUDANÇA DE ARQUITETURA — sem OBS, sem OCR

**Decisão de 18/07/2026.** Os Dias 3 (OBS) e 4 (Claude Vision) do roadmap
original foram **substituídos pela leitura do `Player.log` do MTG Arena**.

**Por quê**: o Arena grava o estado completo da partida em JSON com o `grpId`
numérico de cada carta, e instala junto um SQLite de 26 mil cartas com nomes
em 9 idiomas. OCR custaria ~150k tokens/partida pra descobrir o que o log já
entrega pronto.

| | OCR (plano antigo) | Log (atual) |
|---|---|---|
| Tokens na percepção | ~150.000/partida | **0** |
| Precisão do nome | erra em fonte estilizada | **100% (ID numérico)** |
| Latência | 2-5s | **milissegundos** |
| OBS Studio | obrigatório | **desnecessário** |
| Jogar em português | atrapalhava | **irrelevante** |

**Pré-requisito**: `Ajustes → Conta → Registros detalhados (suporte de plugin)`
ligado dentro do Arena.

**Onde fica o log**: `%USERPROFILE%\AppData\LocalLow\Wizards Of The Coast\MTGA\Player.log`
**Onde fica o Arena**: varia por instalação (Steam, Epic, instalador da Wizards).
Não precisa configurar — `arena_paths.py` descobre sozinho lendo a linha
`Mono path[0]` do próprio log.

### Armadilhas do parser (já resolvidas — material de aula)
1. Mensagens são **incrementais** (`GameStateType_Diff`) — acumular, não sobrescrever
2. **Vários jogos no mesmo log**; cada `GameStateType_Full` inicia um novo, e
   **os assentos trocam entre jogos**
3. `systemSeatIds` é lista de **destinatários**, não "meu assento" — usar de
   qual assento partem as ações do cliente (maioria)
4. Chaves em string (`"{2}{R}{R}"`) quebram extrator de JSON ingênuo
5. **Vida pode ser negativa** (jogador terminou em -3)

**Feito no Dia 5** (camada de IA — primeira das 7 funcionalidades):
- `src/utils/json_solto.py` — extrai JSON de texto solto (serve ao log E às
  respostas da IA; por isso mora em utils)
- `src/services/claude_client.py` — camada única de conversa com a IA:
  parâmetros por modelo, contagem de gasto, leitura de resposta, prompts
  carregados de `prompts/*.md`
- `src/services/deck_identifier.py` — identifica o deck do oponente
- `tests/test_day5.py` — 10 testes (27 no total)
- `src/main.py --analisar [formato]`

Custo medido: ~1.000 tokens de entrada + ~1.300 de saída por análise.

### Fronteira ética do sistema (decisão de projeto)
A IA recebe apenas `cartas_reveladas_do_oponente()` — campo, cemitério,
exílio e pilha. **A mão do oponente nunca entra no prompt**, mesmo em partidas
contra a máquina onde o log a revela. O sistema é assistente de raciocínio
sobre informação pública, não raio-x. Travado por
`test_mao_do_oponente_nunca_entra_na_analise`.

## 🗺️ As 7 funcionalidades pedidas (18/07/2026)

| # | Funcionalidade | Status |
|---|---|---|
| 1 | Identificar deck do oponente | ✅ feito |
| 2 | Ver minhas cartas (coleção) | ⏳ depende de reiniciar o Arena |
| 3 | Montar decks prévios (Standard, Historic…) | ⏳ depende de #2 |
| 4 | Recomendar jogada ao vivo (atacar? descer mana? qual magia?) | ✅ feito |
| 5 | Assistente de Draft/Sealed (escolher carta na hora) | ⏳ próximo |
| 6 | Sideboard entre partidas, aprendendo do jogo anterior | ⏳ |
| 7 | Brawl (deck de comandante) | ⏳ |

## 🚨 A alucinação que custou o Dia 2 (leia antes de mexer em prompt)

**Aconteceu de verdade em 18/07/2026.** A IA recomendou um ataque afirmando:

> "Nest Robber tem **menace**, então o dano de 2 passa garantido" — **90% de confiança**

Verificado no Scryfall: Nest Robber tem **Haste**, não menace. E o bloqueador
(Cloudkin Seer) tinha **Flying**, que ela nem mencionou. A jogada recomendada
seria uma troca 2/1 por 2/1, não dano livre.

**Causa**: a IA raciocinava pela memória que tem das cartas.

**Correção**: `scryfall_service.py` injeta a ficha oficial (texto de regras +
lista de `keywords`) no prompt, com a instrução explícita *"use ESTE texto,
não sua memória; se uma habilidade não estiver listada aqui, a carta NÃO a
tem"*.

**Resultado**: a mesma situação passou a gerar o raciocínio certo — atacar e
usar Shock no bloqueador pra ganhar a troca. Confiança caiu de 90% pra 86%,
que é mais honesto.

**Travado por** `test_recomendacao_real_respeita_as_regras`, que falha se a
palavra "menace" reaparecer no raciocínio.

**Regra do projeto**: nenhum prompt de decisão pode depender da memória do
modelo sobre uma carta. Sempre injetar a ficha oficial.

### Por que Scryfall e não o banco do Arena
O banco do Arena tem o texto (tabela `Abilities`), mas o campo
`Cards.AbilityIds` usa formato não documentado (`"9:101"`). Decodificado
ingenuamente, atribuiu "Evolve" ao Nest Robber e "Bushido" ao Cloudkin Seer.
Texto errado com cara de fonte oficial é pior que texto nenhum.

**Fonte de meta escolhida**: conhecimento do Claude + Scryfall (API aberta).
Sem raspagem de MTGGoldfish — terreno cinzento de termos de uso, e o
conhecimento do modelo já cobre arquétipos bem.

**Modelo**: `claude-opus-4-8` em tudo. Fable 5 foi testado e funciona na conta,
mas o jogador optou pelo Opus por ser o patamar durável e mais barato.

## ⚡ Latência: o que manda é o TAMANHO DA RESPOSTA

**Medido em 18/07/2026** com o prompt real do sistema (5.900 caracteres):

| Configuração | Tempo | Saída | Velocidade |
|---|---|---|---|
| opus-4-8 + effort=high (era o padrão) | 22,4s | 1347 tok | 60 tok/s |
| opus-4-8 + effort=medium | 17,1s | 1053 tok | 62 tok/s |
| opus-4-8 + effort=low | 13,6s | 827 tok | 61 tok/s |
| opus-4-8 sem thinking | 17,6s | 927 tok | 53 tok/s |
| haiku-4-5 | 5,7s | 463 tok | 82 tok/s |
| **opus-4-8 + resposta CURTA + effort=low** | **2,5s** | **93 tok** | 60 tok/s |

**A velocidade é ~60 tok/s em qualquer modelo e qualquer esforço.** Trocar de
modelo ou baixar o esforço muda pouco; o que muda tudo é pedir menos texto.
O erro de projeto era pedir 1.300 tokens de redação pra alguém ler em 10
segundos de turno.

Anotações:
- **Streaming não ajuda** com raciocínio adaptativo: o modelo pensa primeiro e
  só depois escreve (1º texto em 2,9s de 4,2s totais). Não há o que mostrar antes.
- **Fast mode** (`speed="fast"`) devolveu **429** nesta conta — tem limite de
  taxa próprio. Não dá pra contar com ele.
- **Haiku é mais rápido e mais desleixado**: num teste devolveu `"atacar": false`
  no turno do oponente, quando não havia decisão de ataque nenhuma.

**Solução adotada**: dois modos + pré-cálculo.
- `recomendar_rapido()` — ~2,5s, resposta de 12 palavras. Tecla **J**.
- `recomendar()` — ~20s, análise completa. Tecla **C**, pra entre turnos.
- **Pré-cálculo em segundo plano**: assim que o board muda, uma thread já
  calcula. Quando você aperta J, normalmente já está pronto (**0s**). Tecla
  **P** liga/desliga.

## 📌 Pendências

- [ ] **Reiniciar o Arena** uma vez pra capturar a coleção do jogador
  (`PlayerInventory.GetPlayerCardsV3` só é logado no login). Isso torna o
  `data/minhas-cartas.csv` manual desnecessário.
- [ ] Dia 2: SQLite do projeto + Scryfall (oracle text, sinergias, arquétipos).
  O `grpId` do Arena é a ponte pro Scryfall.

**PRÓXIMO PASSO**: Dia 2 (Scryfall) ou Dia 5 (IA). A percepção já está pronta.

## 📦 Repositório

**https://github.com/DACWB/ia-magic** — público, branch `main`.

Ao publicar (19/07/2026), foi feita uma limpeza de dados pessoais. **Antes de
commitar qualquer coisa nova, lembre**:

- `.env` está no `.gitignore` e nunca foi commitado — mantenha assim
- `data/magic-ai.db` (cache do Scryfall) e `logs/` também são ignorados
- Não escreva IP de rede, caminho com nome de usuário, nem nome pessoal nos
  arquivos — os docs usam "o jogador"
- O e-mail dos commits é `DACWB@users.noreply.github.com` (anônimo do GitHub),
  configurado localmente com `git config user.email`. Se clonar em outra
  máquina, refaça essa configuração antes do primeiro commit.

## 🌐 Painel web (para usar no celular)

```bash
venv\Scripts\python.exe -m src.main --web
```

- Neste PC: `http://localhost:8000`
- No celular: o próprio comando imprime o endereço da sua rede ao subir
  (algo como `http://192.168.x.x:8000`). O celular precisa estar no mesmo Wi-Fi.

**Arquitetura**: `src/services/copiloto.py` é o motor — lê o log, decide quando
vale gastar chamada de IA, calcula em segundo plano. O painel do terminal e o
web **compartilham esse motor**, senão viram dois sistemas divergentes.

O servidor escuta em `0.0.0.0` (necessário pro celular). Sem senha. Só trafega
estado de partida e conselho; a chave da API nunca sai do processo do servidor
— travado por `test_pacote_nunca_vaza_a_chave_da_api`. Use em rede doméstica.

**Comandos**:
```bash
venv\Scripts\python.exe -m src.main --web        # painel no navegador/celular
venv\Scripts\python.exe -m src.main              # diagnóstico
venv\Scripts\python.exe -m src.main --partida    # partida atual do log
venv\Scripts\python.exe -m src.main --acompanhar # ao vivo, Ctrl+C pra sair
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
- [ ] O jogador consegue rodar sozinho
- [ ] Código é entendível para os alunos

## 🔗 Links Úteis

- Scryfall API: https://scryfall.com/docs/api
- OBS WebSocket: https://github.com/obsproject/obs-websocket
- Anthropic API: https://docs.claude.com
- MTG Arena data: https://www.mtggoldfish.com

---

**Última atualização**: Início do projeto (Fase de planejamento concluída).  
**Próximo update**: Após Dia 1 do ROADMAP.
