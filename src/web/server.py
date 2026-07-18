"""Servidor local que serve o painel no navegador — e no celular.

## Por que web, se o terminal já funciona

Não é por estética. É porque o jogador tem UM monitor, e qualquer janela na
mesma tela disputa espaço com o Arena — terminal ou navegador, dá no mesmo.

O que muda é que um servidor local pode ser aberto de OUTRO aparelho. Com o
celular apoiado ao lado do teclado, o conselho fica numa tela separada e o
Arena continua ocupando o monitor inteiro. Esse é o ganho real.

## Segurança

O servidor escuta em `0.0.0.0`, ou seja, fica visível pra qualquer aparelho
na mesma rede — é o que permite abrir no celular. Não tem senha.

O que trafega: estado da partida de Magic e conselhos de jogada. Nada
sensível, e a chave da API NUNCA sai daqui (fica só no processo do servidor,
nunca é enviada ao navegador).

Ainda assim: use em rede doméstica. Não rode isso no wifi de um evento.
"""

import asyncio
import json
import socket
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from src.models.game_state import GameState
from src.services.copiloto import Copiloto
from src.utils.config import config

PASTA_ESTATICA = Path(__file__).parent / "static"

# Estado global do servidor. Um copiloto só, compartilhado por todos os
# navegadores conectados — assim celular e PC mostram a mesma coisa, e uma
# chamada de IA serve pros dois.
copiloto: Copiloto | None = None
_config_inicial: dict[str, Any] = {"formato": "standard", "automatico": True}


def descobrir_ip_local() -> str:
    """Descobre o IP da máquina na rede local, pra montar o link do celular.

    O truque do socket UDP: "conectar" a um endereço externo não envia pacote
    nenhum, mas faz o sistema escolher qual interface de rede usaria. Daí a
    gente lê o IP dessa interface. É mais confiável que pegar o primeiro IP
    da lista, que pode ser de um adaptador virtual (VPN, Bluetooth, WSL).

    Returns:
        O IP local, ou "127.0.0.1" se não der pra descobrir.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _carta_para_json(carta: Any) -> dict[str, Any]:
    """Converte uma CartaEmJogo no formato que o navegador espera.

    Args:
        carta: A carta em jogo.

    Returns:
        Dicionário com o que a tela precisa mostrar.
    """
    return {
        "nome": carta.carta.nome(config.idioma_exibicao),
        "nome_en": carta.carta.nome_en,
        "poder": carta.poder_atual,
        "resistencia": carta.resistencia_atual,
        "virada": carta.virada,
        "enjoada": carta.enjoada,
        "atacando": carta.atacando,
        "terreno": carta.eh_terreno,
    }


def _estado_para_json(estado: GameState, copiloto_: Copiloto) -> dict[str, Any]:
    """Monta o pacote enviado ao navegador a cada atualização.

    Args:
        estado: Estado da partida.
        copiloto_: O copiloto, pra puxar conselho e gasto.

    Returns:
        Dicionário pronto pra virar JSON.
    """
    mana = estado.mana_disponivel()

    pacote: dict[str, Any] = {
        "jogo": estado.numero_do_jogo,
        "turno": estado.turno,
        "fase": estado.etapa or estado.fase,
        "meu_turno": copiloto_.e_meu_turno(),
        "minha_vida": estado.minha_vida,
        "vida_oponente": estado.vida_oponente,
        "mana": {c: q for c, q in mana.items() if q},
        "minha_mao": [_carta_para_json(c) for c in estado.minha_mao],
        "meu_campo": [_carta_para_json(c) for c in estado.meu_campo],
        "campo_oponente": [_carta_para_json(c) for c in estado.campo_oponente],
        "cemiterio_oponente": [
            _carta_para_json(c) for c in estado.cemiterio_oponente
        ],
        "calculando": copiloto_.calculando,
        "automatico": copiloto_.automatico,
        "gasto": copiloto_.gasto(),
        "mensagem": copiloto_.mensagem,
        "erro": copiloto_.erro,
        "conselho": None,
        "oponente": None,
        "completa": None,
    }

    if copiloto_.rapida is not None:
        r = copiloto_.rapida
        pacote["conselho"] = {
            "acao": r.acao,
            "motivo": r.motivo,
            "atacar": r.atacar,
            "alerta": r.alerta,
            "segundos": round(r.segundos, 1),
        }

    if copiloto_.analise is not None and copiloto_.analise.principal.nome:
        a = copiloto_.analise
        pacote["oponente"] = {
            "nome": a.principal.nome,
            "confianca": a.principal.confianca,
            "arquetipo": a.principal.arquetipo,
            "cores": a.principal.cores,
            "raciocinio": a.principal.raciocinio,
            "ameacas": [
                {"carta": am.carta, "probabilidade": am.probabilidade}
                for am in a.ameacas[:4]
            ],
        }

    if copiloto_.completa is not None:
        c = copiloto_.completa
        pacote["completa"] = {
            "resumo": c.resumo,
            "confianca": c.confianca,
            "atacar": c.atacar,
            "com_quais": c.com_quais_atacar,
            "motivo_ataque": c.motivo_do_ataque,
            "segurar_mana": c.segurar_mana,
            "motivo_mana": c.motivo_da_mana,
            "alerta": c.alerta,
            "sequencia": [
                {
                    "acao": j.acao,
                    "motivo": j.motivo,
                    "risco": j.risco,
                    "prioridade": j.prioridade,
                }
                for j in c.sequencia
            ],
            "descartadas": c.alternativas_descartadas,
        }

    return pacote


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Cria o copiloto quando o servidor sobe."""
    global copiloto
    copiloto = Copiloto(
        formato=_config_inicial["formato"],
        automatico=_config_inicial["automatico"],
    )
    copiloto.carregar_tudo()
    yield


app = FastAPI(title="Magic AI Advisor", lifespan=ciclo_de_vida)


@app.get("/", response_class=HTMLResponse)
async def pagina() -> str:
    """Serve a página do painel.

    Returns:
        O HTML.
    """
    return (PASTA_ESTATICA / "index.html").read_text(encoding="utf-8")


@app.websocket("/ws")
async def canal(websocket: WebSocket) -> None:
    """Canal que empurra o estado da partida pro navegador.

    Usa WebSocket em vez de o navegador ficar perguntando de segundo em
    segundo: assim a tela atualiza no instante em que algo muda no jogo, sem
    tráfego à toa quando nada acontece.

    Args:
        websocket: A conexão.
    """
    await websocket.accept()
    assert copiloto is not None

    intervalo = max(config.capture_interval_ms / 1000, 0.25)
    ultimo_pacote: str = ""

    async def receber_comandos() -> None:
        """Escuta os botões apertados no navegador.

        CUIDADO QUE JÁ CUSTOU DEPURAÇÃO: exceção dentro de uma task do
        asyncio morre em silêncio. Na primeira versão, um erro aqui matava a
        escuta de comandos sem deixar rastro — os botões simplesmente
        paravam de funcionar, sem mensagem nenhuma na tela nem no terminal.

        Por isso o `except Exception` largo: qualquer falha vira mensagem
        visível pro jogador, e o laço continua escutando.
        """
        acoes = {
            "conselho": copiloto.conselho_rapido,
            "completa": copiloto.analise_completa,
            "oponente": copiloto.analisar_oponente,
        }

        while True:
            try:
                texto = await websocket.receive_text()
            except (WebSocketDisconnect, RuntimeError):
                return  # navegador fechou: encerra a escuta

            try:
                comando = json.loads(texto).get("comando", "")

                if comando == "automatico":
                    copiloto.automatico = not copiloto.automatico
                    copiloto.mensagem = (
                        "Automático ligado." if copiloto.automatico
                        else "Automático desligado."
                    )
                elif comando in acoes:
                    copiloto.erro = ""
                    copiloto.mensagem = "Consultando a IA…"
                    # As chamadas de IA são bloqueantes (a biblioteca da
                    # Anthropic é síncrona). Numa thread separada, o servidor
                    # continua atualizando a tela enquanto a IA pensa.
                    await asyncio.to_thread(acoes[comando])
                else:
                    copiloto.erro = f"Comando desconhecido: {comando!r}"
            except Exception as erro:
                copiloto.erro = f"{type(erro).__name__}: {erro}"
                copiloto.mensagem = "Falhou — veja o erro no rodapé."

    tarefa = asyncio.create_task(receber_comandos())

    try:
        while True:
            copiloto.atualizar()
            copiloto.talvez_calcular()

            pacote = json.dumps(
                _estado_para_json(copiloto.estado, copiloto), ensure_ascii=False
            )
            # Só manda se algo mudou — economiza bateria do celular
            if pacote != ultimo_pacote:
                await websocket.send_text(pacote)
                ultimo_pacote = pacote

            await asyncio.sleep(intervalo)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        tarefa.cancel()


def rodar(
    formato: str = "standard",
    automatico: bool = True,
    porta: int = 8000,
) -> None:
    """Sobe o servidor e imprime os endereços de acesso.

    Args:
        formato: Formato do jogo.
        automatico: Se o conselho aparece sozinho.
        porta: Porta TCP.
    """
    import uvicorn
    from rich.console import Console
    from rich.panel import Panel

    _config_inicial["formato"] = formato
    _config_inicial["automatico"] = automatico

    ip = descobrir_ip_local()
    console = Console()
    console.print(
        Panel(
            f"[bold cyan]🎴 MAGIC AI ADVISOR — painel web[/bold cyan]\n\n"
            f"Neste PC:      [bold]http://localhost:{porta}[/bold]\n"
            f"No celular:    [bold green]http://{ip}:{porta}[/bold green]\n\n"
            f"[dim]Deixe o celular ao lado do teclado e o Arena em tela cheia.\n"
            f"O celular precisa estar no mesmo Wi-Fi.\n"
            f"Ctrl+C aqui pra encerrar.[/dim]",
            border_style="cyan",
        )
    )

    uvicorn.run(app, host="0.0.0.0", port=porta, log_level="warning")
