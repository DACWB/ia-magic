# 🎴 IA Magic — copiloto para MTG Arena

Copiloto de IA que acompanha partidas de **Magic: The Gathering Arena** em
tempo real: identifica o deck do oponente, recomenda a jogada, avisa na hora
de bloquear e revisa a partida no fim.

Roda **local**, lê o log do próprio jogo (sem OCR, sem captura de tela) e usa
a API da Anthropic só onde a inteligência importa.

---

## 📊 Status do projeto

| # | Funcionalidade | Status |
|---|---|---|
| 1 | Identificar o deck do oponente | ✅ funcionando |
| 2 | Ler a coleção do jogador | ⛔ bloqueado — ver *Limitações* |
| 3 | Montar decks a partir da coleção | ⛔ depende de #2 |
| 4 | Recomendar jogada ao vivo (atacar, baixar, segurar mana) | ✅ funcionando |
| 5 | Assistente de Draft / Sealed | ⏳ não iniciado |
| 6 | Análise pós-jogo + sugestão de sideboard | ✅ funcionando |
| 7 | Brawl | ⏳ não iniciado |

**84 testes passando.** Python 3.14, Windows.

---

## 🧠 A decisão que define o projeto: ler o log, não a tela

O plano original era capturar a tela via OBS e usar visão computacional para
reconhecer as cartas. Foi descartado depois de descobrir que **o Arena grava
tudo em JSON**, com o ID numérico exato de cada carta, e ainda instala junto um
SQLite com 26 mil cartas em 9 idiomas.

| | OCR (plano original) | Log (implementado) |
|---|---|---|
| Tokens gastos na percepção | ~150.000 por partida | **0** |
| Precisão do nome da carta | erra em fonte estilizada | **100%** (é um ID) |
| Latência da leitura | 2–5 s | **~3 ms** |
| OBS Studio | obrigatório | **desnecessário** |
| Jogar em outro idioma | atrapalhava | **irrelevante** |

> A lição, que vale para qualquer sistema de extração de dados: **antes de
> extrair, verifique se dá para subir na fonte.** O melhor OCR é o que você
> não precisou escrever.

---

## ⚡ Latência: o tamanho da resposta é o que manda

Medições com o prompt real do sistema:

| Configuração | Tempo | Saída |
|---|---|---|
| `effort=high`, resposta completa | 22,4 s | 1347 tokens |
| `effort=low`, resposta completa | 13,6 s | 827 tokens |
| **`effort=low`, resposta curta** | **2,5 s** | **93 tokens** |

A API entrega ~60 tokens/s em qualquer modelo e qualquer nível de esforço.
Trocar de modelo quase não muda nada; **pedir menos texto muda tudo**.

Daí os dois modos: conselho rápido (~2,5 s, 12 palavras) durante o turno, e
análise completa (~20 s) entre turnos. Um pré-cálculo em segundo plano deixa o
conselho pronto **antes** de você pedir.

---

## 🏗️ Arquitetura

```
Player.log (MTG Arena)
      │  parser incremental, ~3 ms
      ▼
  GameState  ──────────────┐
      │                     │
      │  cartas públicas    │  ficha oficial das cartas
      ▼                     ▼
 Claude Opus 4.8  ◄──── Scryfall (cache SQLite local)
      │
      ├──► Terminal (Rich)
      └──► Navegador / celular (FastAPI + WebSocket)
```

| Módulo | Responsabilidade |
|---|---|
| `arena_paths.py` | Acha log, instalação e banco de cartas do Arena |
| `arena_log_service.py` | Parser incremental do `Player.log` |
| `arena_card_db.py` | `grpId` → nome em inglês e português |
| `scryfall_service.py` | Texto oficial das cartas, com cache local |
| `copiloto.py` | Motor: decide **quando** vale gastar chamada de IA |
| `deck_identifier.py` | Identifica o arquétipo do oponente |
| `play_recommender.py` | Recomenda a jogada |
| `post_game_analyzer.py` | Revisa a partida encerrada |
| `ui/dashboard.py` | Painel no terminal |
| `web/` | Painel no navegador e celular |

---

## 🚀 Como rodar

**Pré-requisito no Arena:** `Ajustes → Conta → Registros detalhados (suporte de
plugin)` **ligado**. Sem isso o log não traz o estado da partida.

```bash
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt

copy .env.example .env      # depois coloque sua ANTHROPIC_API_KEY

venv\Scripts\python.exe -m src.main --web    # painel no navegador e celular
venv\Scripts\python.exe -m src.main          # painel no terminal
venv\Scripts\python.exe -m src.main --ajuda  # todos os comandos
venv\Scripts\python.exe -m pytest tests/ -v  # testes
```

O painel web imprime o endereço da rede local ao subir — abra no celular
(mesmo Wi-Fi) e deixe ao lado do teclado, com o jogo em tela cheia.

---

## 🔒 Fronteira ética

A IA recebe **apenas informação pública**: campo de batalha, cemitério, exílio
e pilha do oponente.

**A mão do oponente nunca entra no prompt** — mesmo em partidas contra a
máquina, onde o log a revela. Isso é um assistente de raciocínio sobre o que
qualquer jogador atento veria numa mesa física, não um raio-x. A regra é
travada pelo teste `test_mao_do_oponente_nunca_entra_na_analise`.

O projeto usa a opção de logs que a própria Wizards criou para plugins
("suporte de plugin"), lê apenas arquivos locais e não automatiza nenhuma
jogada — quem decide e clica é sempre o jogador.

---

## ⚠️ Limitações conhecidas

- **A coleção do jogador não é acessível.** Verificado: não está no log, não há
  cache local, e nem abrir a tela de coleção no jogo dispara o registro. Por
  isso as funcionalidades 2 e 3 estão bloqueadas. Contorno: exportar um deck
  pelo Arena e passar o texto para `identificador_de_cartas.py`.
- **Não responde em velocidade de instantâneo.** O sistema não acompanha a
  janela de prioridade no turno do oponente, que dura segundos.
- **Testado apenas no Windows**, com o Arena instalado via Steam.
- **O painel web não tem autenticação.** Ele escuta em `0.0.0.0` para ser
  alcançável pelo celular. Use em rede doméstica.

---

## 🐛 Alucinações encontradas em uso real

Todas apareceram jogando de verdade, e **nenhuma foi pega por teste** — a saída
era bem formatada, articulada e com alta confiança declarada.

| O que a IA disse | Realidade | Correção |
|---|---|---|
| "Nest Robber tem *menace*" (90% de confiança) | Tem **Haste**. E ignorou o *Flying* do bloqueador. | Injetar a ficha oficial do Scryfall no prompt |
| "Soulblade Djinn é 6/4" | Base impressa 4/3, no board 5/3 — somou as duas fontes | Marcar explicitamente o que é base e o que é atual |
| "Tire *Wanderwine Distracter* do sideboard" | A carta era **do oponente** | Listar no prompt de quem é cada carta |

> **Alucinação confiante é o pior erro em apoio à decisão, porque não parece
> erro.** O padrão que emergiu: sempre que o prompt tem duas fontes para a
> mesma informação, o modelo mistura. A correção nunca é "peça para ter
> cuidado" — é eliminar a ambiguidade na origem.

---

## 🛠️ Stack

Python 3.14 · Pydantic · FastAPI · Rich · httpx · SQLite · pytest
API da Anthropic (`claude-opus-4-8`) · [Scryfall](https://scryfall.com/docs/api)

## 📄 Licença e marcas

Projeto pessoal de estudo, sem vínculo com a Wizards of the Coast.
*Magic: The Gathering* e *MTG Arena* são marcas da Wizards of the Coast LLC.

## 🔗 Referência

Repositórios do autor: [github.com/DACWB](https://github.com/DACWB)
