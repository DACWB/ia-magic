"""Painel de controle — a interface do sistema durante a partida.

## O problema que este arquivo resolve

Antes dele o sistema era quatro comandos soltos: um pra ver a partida, outro
pra analisar o oponente, outro pra pedir jogada. Ninguém joga Magic alternando
entre terminais. Aqui vira uma tela só, que se atualiza sozinha enquanto você
joga.

## A decisão de design que importa: quando chamar a IA

Ler o log é grátis e instantâneo, então o estado da partida atualiza sozinho,
várias vezes por segundo. Já a IA custa dinheiro e leva alguns segundos.

Se o painel chamasse a IA a cada atualização, uma partida de 15 minutos
custaria uma fortuna e a tela viveria travada. Por isso:

- **Estado do jogo**: automático e contínuo (grátis)
- **Análise da IA**: só quando VOCÊ pede, apertando uma tecla

Você continua no controle do gasto, e o painel nunca trava sem você mandar.
"""

import time
from typing import Any

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.models.game_state import GameState
from src.services.arena_log_service import LeitorDeLogArena
from src.utils.config import config

# Leitura de tecla sem travar o programa. É específico do Windows; em outros
# sistemas o painel roda igual, só sem os atalhos.
try:
    import msvcrt

    TEM_TECLADO = True
except ImportError:  # pragma: no cover - só ocorre fora do Windows
    TEM_TECLADO = False


def ler_tecla() -> str:
    """Lê uma tecla se houver alguma pressionada, sem travar.

    A diferença pro `input()` é essencial aqui: `input()` congela o programa
    esperando você digitar, e o painel pararia de atualizar. Este só olha se
    tem tecla no buffer e segue a vida.

    Returns:
        A tecla em minúscula, ou string vazia se nada foi pressionado.
    """
    if not TEM_TECLADO or not msvcrt.kbhit():
        return ""
    try:
        return msvcrt.getch().decode("utf-8", errors="ignore").lower()
    except Exception:
        return ""


class Painel:
    """A tela do Magic AI Advisor.

    Uso:
        Painel(formato="standard").rodar()
    """

    def __init__(self, formato: str = "standard") -> None:
        """Prepara o painel.

        Args:
            formato: Formato do jogo, usado pra calibrar a IA.
        """
        self.console = Console()
        self.formato = formato
        self.leitor = LeitorDeLogArena()

        # Serviços de IA são criados só quando você pede a primeira análise.
        # Assim o painel abre instantâneo, mesmo sem internet.
        self._identificador: Any = None
        self._recomendador: Any = None

        self.analise: Any = None
        self.recomendacao: Any = None
        self.mensagem: str = "Pressione [A] pra analisar o oponente ou [J] pra pedir jogada."
        self.pensando: bool = False

    # ------------------------------------------------------------------
    # Montagem da tela
    # ------------------------------------------------------------------

    def _cabecalho(self, estado: GameState) -> Panel:
        """Faixa superior com o placar da partida."""
        mana = estado.mana_disponivel()
        cores = " ".join(
            f"[bold]{qtd}{cor}[/bold]"
            for cor, qtd in mana.items()
            if cor not in ("total", "incolor") and qtd > 0
        )

        meu_turno = estado.jogador_ativo == estado.meu_seat
        indicador = "[green]SEU TURNO[/green]" if meu_turno else "[dim]turno dele[/dim]"

        grade = Table.grid(padding=(0, 3))
        grade.add_row(
            "[bold cyan]🎴 MAGIC AI ADVISOR[/bold cyan]",
            f"Jogo {estado.numero_do_jogo} · Turno {estado.turno}",
            indicador,
            f"[green]Você {estado.minha_vida}[/green] × [red]{estado.vida_oponente} Oponente[/red]",
            f"Mana: {cores or '[dim]0[/dim]'}",
            f"[dim]{estado.etapa or estado.fase}[/dim]",
        )
        return Panel(grade, border_style="cyan")

    def _lista_de_cartas(self, titulo: str, cartas: list, cor: str) -> Panel:
        """Painel com uma lista de cartas e o estado de cada uma."""
        if not cartas:
            return Panel("[dim](vazio)[/dim]", title=titulo, border_style=cor)

        linhas = []
        for carta in cartas:
            nome = carta.carta.nome(config.idioma_exibicao)
            texto = f"• {nome}"
            if carta.poder_atual:
                texto += f" [dim]{carta.poder_atual}/{carta.resistencia_atual}[/dim]"
            marcas = []
            if carta.virada:
                marcas.append("virada")
            if carta.enjoada:
                marcas.append("enjoada")
            if carta.atacando:
                marcas.append("[red]atacando[/red]")
            if marcas:
                texto += f" [dim]({', '.join(marcas)})[/dim]"
            linhas.append(texto)

        return Panel("\n".join(linhas), title=f"{titulo} ({len(cartas)})",
                     border_style=cor)

    def _painel_do_oponente(self) -> Panel:
        """Mostra a análise do deck do oponente, se já foi pedida."""
        if self.analise is None or not self.analise.principal.nome:
            return Panel(
                "[dim]Ainda não analisado.\nPressione [bold]A[/bold].[/dim]",
                title="🔍 Deck do oponente",
                border_style="dim",
            )

        principal = self.analise.principal
        partes = [
            f"[bold]{principal.nome}[/bold] "
            f"[dim]({principal.confianca:.0%})[/dim]",
            "",
            principal.raciocinio,
        ]

        if self.analise.ameacas:
            partes.append("")
            partes.append("[bold yellow]Ameaças:[/bold yellow]")
            for ameaca in self.analise.ameacas[:3]:
                partes.append(
                    f"  • {ameaca.carta} [dim]({ameaca.probabilidade:.0%})[/dim]"
                )

        return Panel(
            "\n".join(partes),
            title=f"🔍 Oponente — {principal.arquetipo} {'/'.join(principal.cores)}",
            border_style="magenta",
        )

    def _painel_da_jogada(self) -> Panel:
        """Mostra a recomendação de jogada, se já foi pedida."""
        if self.recomendacao is None:
            return Panel(
                "[dim]Nenhuma recomendação ainda.\n"
                "Pressione [bold]J[/bold] pra pedir.[/dim]",
                title="💡 Jogada",
                border_style="dim",
            )

        rec = self.recomendacao
        partes: list[Any] = []

        if rec.alerta:
            partes.append(Text(f"🚨 {rec.alerta}", style="bold red"))
            partes.append(Text(""))

        partes.append(Text(rec.resumo, style="bold green"))

        if rec.sequencia:
            partes.append(Text(""))
            for jogada in rec.sequencia[:3]:
                partes.append(Text(f"{jogada.prioridade}. {jogada.acao}", style="bold"))
                partes.append(Text(f"   {jogada.motivo}", style="dim"))
                if jogada.risco:
                    partes.append(Text(f"   ⚠ {jogada.risco}", style="yellow"))

        if rec.atacar is not None:
            partes.append(Text(""))
            if rec.atacar:
                alvos = ", ".join(rec.com_quais_atacar) or "tudo"
                partes.append(Text(f"⚔ ATACAR com {alvos}", style="bold cyan"))
            else:
                partes.append(Text("🛡 NÃO atacar", style="bold cyan"))
            partes.append(Text(f"   {rec.motivo_do_ataque}", style="dim"))

        if rec.segurar_mana:
            partes.append(Text(""))
            partes.append(Text("🔒 Segurar mana aberta", style="bold blue"))
            partes.append(Text(f"   {rec.motivo_da_mana}", style="dim"))

        return Panel(
            Group(*partes),
            title=f"💡 Jogada ({rec.confianca:.0%} de confiança)",
            border_style="green",
        )

    def _rodape(self) -> Panel:
        """Faixa inferior com atalhos, gasto e mensagens."""
        gasto = ""
        if self._identificador is not None:
            gasto = f" · [dim]{self._identificador.cliente.resumo_de_gasto()}[/dim]"

        atalhos = (
            "[bold]A[/bold] analisar oponente · "
            "[bold]J[/bold] pedir jogada · "
            "[bold]Q[/bold] sair"
        )
        cor = "yellow" if self.pensando else "blue"
        return Panel(f"{atalhos}\n{self.mensagem}{gasto}", border_style=cor)

    def montar(self, estado: GameState) -> Layout:
        """Monta a tela inteira.

        Args:
            estado: Estado atual da partida.

        Returns:
            Layout pronto pro Rich desenhar.
        """
        layout = Layout()
        layout.split_column(
            Layout(self._cabecalho(estado), size=3, name="topo"),
            Layout(name="meio", ratio=1),
            Layout(self._rodape(), size=4, name="baixo"),
        )
        layout["meio"].split_row(
            Layout(name="esquerda", ratio=1),
            Layout(name="centro", ratio=1),
            Layout(self._painel_da_jogada(), ratio=2, name="direita"),
        )
        layout["esquerda"].split_column(
            Layout(self._lista_de_cartas("🖐️  Minha mão", estado.minha_mao, "green")),
            Layout(self._lista_de_cartas("⚔️  Meu campo", estado.meu_campo, "green")),
        )
        layout["centro"].split_column(
            Layout(self._lista_de_cartas("👹 Campo dele", estado.campo_oponente, "red")),
            Layout(self._painel_do_oponente()),
        )
        return layout

    # ------------------------------------------------------------------
    # Ações da IA
    # ------------------------------------------------------------------

    def analisar_oponente(self, estado: GameState) -> None:
        """Pede à IA pra identificar o deck do oponente.

        Args:
            estado: Estado atual.
        """
        if not estado.cartas_reveladas_do_oponente():
            self.mensagem = "[yellow]O oponente ainda não revelou nenhuma carta.[/yellow]"
            return

        from src.services.deck_identifier import IdentificadorDeDeck

        if self._identificador is None:
            self._identificador = IdentificadorDeDeck()

        self.analise = self._identificador.identificar(estado, formato=self.formato)
        self.mensagem = "[green]Oponente analisado.[/green]"

    def pedir_jogada(self, estado: GameState) -> None:
        """Pede à IA a recomendação de jogada.

        Analisa o oponente antes, se ainda não tiver feito: a recomendação
        fica bem melhor sabendo contra o que se joga.

        Args:
            estado: Estado atual.
        """
        from src.services.play_recommender import RecomendadorDeJogada

        if self.analise is None:
            self.analisar_oponente(estado)

        if self._recomendador is None:
            cliente = self._identificador.cliente if self._identificador else None
            self._recomendador = RecomendadorDeJogada(cliente=cliente)

        recomendacao = self._recomendador.recomendar(
            estado, self.analise, formato=self.formato
        )
        if recomendacao is None:
            self.mensagem = "[yellow]Nada pra decidir agora.[/yellow]"
            return

        self.recomendacao = recomendacao
        self.mensagem = "[green]Jogada recomendada.[/green]"

    # ------------------------------------------------------------------
    # Laço principal
    # ------------------------------------------------------------------

    def rodar(self) -> None:
        """Abre o painel e fica atualizando até você apertar Q."""
        estado = self.leitor.ler_arquivo_inteiro()

        if not TEM_TECLADO:
            self.mensagem = (
                "[yellow]Atalhos de teclado indisponíveis fora do Windows. "
                "Use os comandos --analisar e --jogada.[/yellow]"
            )

        intervalo = max(config.capture_interval_ms / 1000, 0.2)

        with Live(
            self.montar(estado),
            console=self.console,
            refresh_per_second=4,
            screen=True,
        ) as live:
            while True:
                estado = self.leitor.ler_novidades()
                tecla = ler_tecla()

                if tecla == "q":
                    break

                if tecla in ("a", "j"):
                    # Mostra "pensando" ANTES de chamar a IA. Sem isso a tela
                    # congela por vários segundos sem explicação, e você não
                    # sabe se travou ou está trabalhando.
                    self.pensando = True
                    self.mensagem = "[yellow]Consultando a IA…[/yellow]"
                    live.update(self.montar(estado))

                    try:
                        if tecla == "a":
                            self.analisar_oponente(estado)
                        else:
                            self.pedir_jogada(estado)
                    except Exception as erro:
                        # Falha de IA não pode derrubar o painel no meio de
                        # uma partida. Mostra o problema e segue rodando.
                        self.mensagem = f"[red]Erro: {type(erro).__name__} — {erro}[/red]"
                    finally:
                        self.pensando = False

                live.update(self.montar(estado))
                time.sleep(intervalo)

        self.console.print("[dim]Painel encerrado.[/dim]")
        if self._identificador is not None:
            self.console.print(f"[dim]{self._identificador.cliente.resumo_de_gasto()}[/dim]")
