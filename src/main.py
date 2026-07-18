"""Ponto de entrada do Magic AI Advisor.

Modos:
    python -m src.main               # diagnóstico do ambiente
    python -m src.main --partida     # mostra a partida atual do log
    python -m src.main --acompanhar  # acompanha ao vivo (Ctrl+C pra sair)

A camada de IA (Dia 5) ainda não está ligada — por enquanto o sistema lê e
mostra o estado do jogo. O que já é bastante: tudo isso vem do log do Arena,
sem OBS, sem OCR e sem gastar um token.
"""

import sys
import time

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.models.game_state import GameState
from src.services.arena_log_service import LeitorDeLogArena
from src.services.arena_paths import ArenaNaoEncontrado
from src.utils.config import config
from src.utils.terminal import preparar_terminal

# Precisa vir ANTES de criar o Console: no Windows o terminal nasce em cp1252
# e o Rich decide a estratégia de renderização na criação do objeto.
preparar_terminal()

console = Console()


def mostrar_diagnostico() -> None:
    """Imprime o estado atual da configuração e das dependências externas."""
    console.print(Panel("🎴 MAGIC AI ADVISOR", style="bold cyan"))

    tabela = Table(show_header=True, header_style="bold")
    tabela.add_column("Item")
    tabela.add_column("Valor")
    tabela.add_column("Status", justify="center")

    chave_ok = config.chave_api_configurada()
    tabela.add_row(
        "Chave Anthropic",
        "configurada" if chave_ok else "faltando no .env",
        "✅" if chave_ok else "❌",
    )
    tabela.add_row("Modelo principal", config.claude_model_primary, "✅")

    try:
        from src.services.arena_paths import (
            caminho_banco_de_cartas,
            caminho_do_log,
            pasta_de_instalacao,
        )

        tabela.add_row("Arena instalado", str(pasta_de_instalacao()), "✅")
        tabela.add_row("Log do Arena", caminho_do_log().name, "✅")
        tabela.add_row("Banco de cartas", caminho_banco_de_cartas().name[:40] + "…", "✅")
    except ArenaNaoEncontrado as erro:
        tabela.add_row("MTG Arena", str(erro).split("\n")[0], "❌")

    banco_existe = config.database_path.exists()
    tabela.add_row(
        "Banco do projeto",
        str(config.database_path.name),
        "✅" if banco_existe else "⏳ (Dia 2)",
    )
    tabela.add_row("Camada de IA", "recomendação de jogadas", "⏳ (Dia 5)")

    console.print(tabela)

    if not chave_ok:
        console.print(
            Panel(
                "Edite o [bold].env[/bold] e coloque sua chave em "
                "[bold]ANTHROPIC_API_KEY[/bold] (https://console.anthropic.com)",
                title="⚠️  Falta um passo",
                border_style="yellow",
            )
        )


def _painel_de_cartas(titulo: str, cartas: list, cor: str) -> Panel:
    """Monta um painel com uma lista de cartas.

    Args:
        titulo: Título do painel.
        cartas: Lista de CartaEmJogo.
        cor: Cor da borda.

    Returns:
        Painel pronto pro Rich desenhar.
    """
    if not cartas:
        return Panel("[dim](vazio)[/dim]", title=titulo, border_style=cor, width=38)

    linhas = []
    for carta in cartas:
        nome = carta.carta.nome(config.idioma_exibicao)
        corpo = carta.poder_atual and f" [dim]{carta.poder_atual}/{carta.resistencia_atual}[/dim]"
        virada = " [dim]↻[/dim]" if carta.virada else ""
        linhas.append(f"• {nome}{corpo or ''}{virada}")

    return Panel("\n".join(linhas), title=titulo, border_style=cor, width=38)


def montar_tela(estado: GameState) -> Columns:
    """Monta a tela da partida a partir do estado.

    Args:
        estado: Estado atual do jogo.

    Returns:
        Layout pronto pro Rich.
    """
    placar = Table.grid(padding=(0, 2))
    placar.add_row(
        f"[bold cyan]Jogo {estado.numero_do_jogo}[/bold cyan]",
        f"Turno [bold]{estado.turno}[/bold]",
        f"[green]Você: {estado.minha_vida}[/green]",
        f"[red]Oponente: {estado.vida_oponente}[/red]",
        f"[dim]{estado.etapa or estado.fase}[/dim]",
    )

    paineis = [
        _painel_de_cartas("🖐️  Minha mão", estado.minha_mao, "green"),
        _painel_de_cartas("⚔️  Meu campo", estado.meu_campo, "green"),
        _painel_de_cartas("👹 Campo do oponente", estado.campo_oponente, "red"),
        _painel_de_cartas("🪦 Cemitério dele", estado.cemiterio_oponente, "magenta"),
    ]

    return Columns([Panel(placar, border_style="cyan"), *paineis])


def mostrar_partida(acompanhar: bool = False) -> None:
    """Lê o log e mostra a partida.

    Args:
        acompanhar: Se True, fica atualizando ao vivo até Ctrl+C.
    """
    try:
        leitor = LeitorDeLogArena()
    except ArenaNaoEncontrado as erro:
        console.print(Panel(str(erro), title="❌ Arena não encontrado", border_style="red"))
        return

    estado = leitor.ler_arquivo_inteiro()

    if not estado.cartas and not leitor.jogos_anteriores:
        console.print(
            Panel(
                "Nenhuma partida no log ainda.\n\n"
                "Confirme que [bold]Ajustes → Conta → Registros detalhados "
                "(suporte de plugin)[/bold] está ligado, e jogue uma partida.",
                title="⏳ Sem dados",
                border_style="yellow",
            )
        )
        return

    if leitor.jogos_anteriores:
        console.print(
            f"[dim]{len(leitor.jogos_anteriores)} jogo(s) anterior(es) nesta sessão.[/dim]"
        )

    if not acompanhar:
        console.print(montar_tela(estado))
        _mostrar_resultado(estado)
        return

    # Modo ao vivo
    from rich.live import Live

    console.print("[dim]Acompanhando o log… Ctrl+C pra sair.[/dim]\n")
    intervalo = config.capture_interval_ms / 1000

    try:
        with Live(montar_tela(estado), console=console, refresh_per_second=4) as live:
            while True:
                time.sleep(intervalo)
                live.update(montar_tela(leitor.ler_novidades()))
    except KeyboardInterrupt:
        console.print("\n[dim]Encerrado.[/dim]")


def _mostrar_resultado(estado: GameState) -> None:
    """Mostra o resultado da partida, se ela já acabou.

    Args:
        estado: Estado do jogo.
    """
    if estado.resultado is None:
        return

    venceu = estado.resultado.eu_venci
    if venceu is True:
        console.print(Panel("🏆 Você venceu!", border_style="green"))
    elif venceu is False:
        console.print(Panel("💀 Você perdeu.", border_style="red"))


if __name__ == "__main__":
    argumentos = sys.argv[1:]
    if "--acompanhar" in argumentos:
        mostrar_partida(acompanhar=True)
    elif "--partida" in argumentos:
        mostrar_partida()
    else:
        mostrar_diagnostico()
