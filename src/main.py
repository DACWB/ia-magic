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


def analisar_oponente(formato: str = "standard") -> None:
    """Lê a partida do log e pede à IA pra identificar o deck do oponente.

    Args:
        formato: Formato do jogo, pra IA calibrar a análise.
    """
    from src.services.deck_identifier import IdentificadorDeDeck

    try:
        leitor = LeitorDeLogArena()
    except ArenaNaoEncontrado as erro:
        console.print(Panel(str(erro), title="❌", border_style="red"))
        return

    estado = leitor.ler_arquivo_inteiro()
    reveladas = estado.cartas_reveladas_do_oponente()

    if not reveladas:
        console.print(
            Panel(
                "O oponente ainda não revelou nenhuma carta nesta partida.\n"
                "Nada pra analisar — e não vou gastar chamada de IA à toa.",
                title="⏳ Cedo demais",
                border_style="yellow",
            )
        )
        return

    nomes = sorted({c.carta.nome(config.idioma_exibicao) for c in reveladas})
    console.print(f"[dim]Analisando {len(nomes)} cartas: {', '.join(nomes)}[/dim]\n")

    with console.status("[cyan]Consultando a IA…"):
        identificador = IdentificadorDeDeck()
        analise = identificador.identificar(estado, formato=formato)

    principal = analise.principal
    console.print(
        Panel(
            f"[bold]{principal.nome}[/bold]  "
            f"[dim]({principal.confianca:.0%} de confiança)[/dim]\n\n"
            f"{principal.raciocinio}",
            title=f"🔍 Deck do oponente — {principal.arquetipo or '?'} "
            f"{'/'.join(principal.cores)}",
            border_style="cyan",
        )
    )

    if analise.ameacas:
        tabela = Table(title="⚠️  Ameaças esperadas", show_header=True)
        tabela.add_column("Carta")
        tabela.add_column("Chance", justify="right")
        tabela.add_column("Turno", justify="right")
        tabela.add_column("Impacto")
        for ameaca in analise.ameacas[:5]:
            tabela.add_row(
                ameaca.carta,
                f"{ameaca.probabilidade:.0%}",
                str(ameaca.turno_esperado or "—"),
                ameaca.impacto,
            )
        console.print(tabela)

    if analise.como_enfrentar:
        conselhos = "\n".join(f"• {c}" for c in analise.como_enfrentar)
        console.print(Panel(conselhos, title="💡 Como enfrentar", border_style="green"))

    if analise.alternativas:
        outras = ", ".join(
            f"{h.nome} ({h.confianca:.0%})" for h in analise.alternativas[:3]
        )
        console.print(f"[dim]Outras hipóteses: {outras}[/dim]")

    console.print(f"[dim]{identificador.cliente.resumo_de_gasto()}[/dim]")


def recomendar_jogada(formato: str = "standard") -> None:
    """Lê a partida atual e recomenda a próxima jogada.

    Args:
        formato: Formato do jogo.
    """
    from src.services.deck_identifier import IdentificadorDeDeck
    from src.services.play_recommender import RecomendadorDeJogada

    try:
        leitor = LeitorDeLogArena()
    except ArenaNaoEncontrado as erro:
        console.print(Panel(str(erro), title="❌", border_style="red"))
        return

    estado = leitor.ler_arquivo_inteiro()

    if not estado.minha_mao and not estado.criaturas_que_podem_atacar():
        console.print(
            Panel(
                "Nada pra decidir: mão vazia e nenhuma criatura apta a atacar.",
                title="⏳",
                border_style="yellow",
            )
        )
        return

    mana = estado.mana_disponivel()
    console.print(
        f"[dim]Turno {estado.turno} | {estado.minha_vida} x "
        f"{estado.vida_oponente} | {mana.get('total', 0)} mana | "
        f"{len(estado.minha_mao)} cartas na mão[/dim]\n"
    )

    with console.status("[cyan]Analisando o oponente…"):
        identificador = IdentificadorDeDeck()
        analise = identificador.identificar(estado, formato=formato)

    if analise.principal.nome:
        console.print(
            f"[dim]Oponente: {analise.principal.nome} "
            f"({analise.principal.confianca:.0%})[/dim]"
        )

    with console.status("[cyan]Pensando na jogada…"):
        recomendador = RecomendadorDeJogada(cliente=identificador.cliente)
        rec = recomendador.recomendar(estado, analise, formato=formato)

    if rec is None:
        console.print("[yellow]Sem recomendação.[/yellow]")
        return

    if rec.alerta:
        console.print(Panel(rec.alerta, title="🚨 Atenção", border_style="red"))

    console.print(
        Panel(
            rec.resumo,
            title=f"💡 Recomendação ({rec.confianca:.0%} de confiança)",
            border_style="green",
        )
    )

    if rec.sequencia:
        tabela = Table(show_header=True, header_style="bold")
        tabela.add_column("#", justify="right", width=3)
        tabela.add_column("Fazer", width=34)
        tabela.add_column("Por quê")
        tabela.add_column("Risco", style="yellow")
        for jogada in rec.sequencia:
            tabela.add_row(
                str(jogada.prioridade), jogada.acao, jogada.motivo, jogada.risco
            )
        console.print(tabela)

    if rec.atacar is not None:
        icone = "⚔️  ATACAR" if rec.atacar else "🛡️  NÃO atacar"
        alvos = f" com {', '.join(rec.com_quais_atacar)}" if rec.com_quais_atacar else ""
        console.print(
            Panel(
                f"[bold]{icone}{alvos}[/bold]\n\n{rec.motivo_do_ataque}",
                border_style="cyan",
            )
        )

    if rec.motivo_da_mana:
        icone = "🔒 Segurar mana" if rec.segurar_mana else "💧 Pode gastar tudo"
        console.print(Panel(f"[bold]{icone}[/bold]\n{rec.motivo_da_mana}",
                            border_style="blue"))

    if rec.alternativas_descartadas:
        descartadas = "\n".join(f"• {a}" for a in rec.alternativas_descartadas)
        console.print(
            Panel(descartadas, title="🤔 Considerado e descartado", border_style="dim")
        )

    console.print(f"[dim]{recomendador.cliente.resumo_de_gasto()}[/dim]")


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


def abrir_painel(formato: str = "standard") -> None:
    """Abre o painel de controle — a interface principal do sistema.

    Args:
        formato: Formato do jogo.
    """
    from src.ui.dashboard import Painel

    try:
        Painel(formato=formato).rodar()
    except ArenaNaoEncontrado as erro:
        console.print(Panel(str(erro), title="❌ Arena não encontrado",
                            border_style="red"))


def mostrar_ajuda() -> None:
    """Lista os comandos disponíveis."""
    tabela = Table(title="🎴 Magic AI Advisor — comandos", show_header=True)
    tabela.add_column("Comando", style="bold cyan")
    tabela.add_column("O que faz")

    tabela.add_row("python -m src.main", "Abre o PAINEL (interface principal)")
    tabela.add_row("python -m src.main draft", "Painel calibrado pra Draft")
    tabela.add_row("", "")
    tabela.add_row("--diagnostico", "Confere se está tudo configurado")
    tabela.add_row("--partida", "Mostra a partida atual, sem IA")
    tabela.add_row("--acompanhar", "Acompanha a partida ao vivo, sem IA")
    tabela.add_row("--analisar [formato]", "Só identifica o deck do oponente")
    tabela.add_row("--jogada [formato]", "Só recomenda a jogada")
    tabela.add_row("--ajuda", "Esta lista")

    console.print(tabela)
    console.print(
        "\n[dim]Dentro do painel: [bold]A[/bold] analisa o oponente, "
        "[bold]J[/bold] pede jogada, [bold]Q[/bold] sai.[/dim]"
    )


FORMATOS_CONHECIDOS = (
    "standard", "historic", "explorer", "draft", "sealed", "brawl", "alchemy"
)


if __name__ == "__main__":
    argumentos = sys.argv[1:]

    if "--ajuda" in argumentos or "-h" in argumentos or "--help" in argumentos:
        mostrar_ajuda()
    elif "--diagnostico" in argumentos:
        mostrar_diagnostico()
    elif "--acompanhar" in argumentos:
        mostrar_partida(acompanhar=True)
    elif "--partida" in argumentos:
        mostrar_partida()
    elif "--analisar" in argumentos:
        # Formato opcional: --analisar draft
        posicao = argumentos.index("--analisar")
        seguinte = argumentos[posicao + 1] if len(argumentos) > posicao + 1 else ""
        analisar_oponente(formato=seguinte or "standard")
    elif "--jogada" in argumentos:
        posicao = argumentos.index("--jogada")
        seguinte = argumentos[posicao + 1] if len(argumentos) > posicao + 1 else ""
        recomendar_jogada(formato=seguinte or "standard")
    else:
        # Sem comando = abre o painel. É a interface principal, então é o que
        # acontece quando você só roda `python -m src.main`.
        # Aceita o formato solto: `python -m src.main draft`
        formato_pedido = next(
            (a for a in argumentos if a.lower() in FORMATOS_CONHECIDOS), "standard"
        )
        abrir_painel(formato=formato_pedido)
