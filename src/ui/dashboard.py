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

import threading
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

# Quanto tempo o board precisa ficar parado antes de valer uma chamada de IA.
# Durante uma jogada o estado muda várias vezes em sequência (carta sai da
# mão, vai pra pilha, resolve, entra em campo). Sem essa espera, o sistema
# geraria conselho sobre situações que duraram 200 milissegundos.
ESPERA_BOARD_ESTAVEL = 1.5


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

    def __init__(self, formato: str = "standard", automatico: bool = True) -> None:
        """Prepara o painel.

        Args:
            formato: Formato do jogo, usado pra calibrar a IA.
            automatico: Se True (padrão), o conselho aparece sozinho quando
                for sua vez de decidir, sem precisar apertar tecla.
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
        self.rapida: Any = None
        self.mensagem: str = "Pressione [J] pra conselho rápido, [A] pra analisar o oponente."
        self.pensando: bool = False

        # --- Pré-cálculo em segundo plano ---
        #
        # O conselho rápido leva ~2,5s. Parece pouco, mas no meio de um turno
        # com o relógio correndo é uma eternidade. A solução não é deixar mais
        # rápido — é começar ANTES de você pedir.
        #
        # Assim que o board muda, uma thread já vai calculando. Quando você
        # aperta J, a resposta normalmente já está pronta: 0 segundos.
        self._prefetch_thread: threading.Thread | None = None
        self._prefetch_assinatura: str = ""
        self._prefetch_resultado: Any = None
        self._trava = threading.Lock()
        self.prefetch_ligado: bool = True

        # --- Modo automático ---
        #
        # Com UM monitor só, apertar tecla no terminal significa tirar o foco
        # do Arena — ou seja, parar de jogar. Um copiloto que exige isso não
        # serve. No automático o conselho aparece sozinho e você só olha.
        #
        # Para não queimar tokens à toa, só dispara quando REALMENTE há uma
        # decisão sua a tomar: seu turno, e algo jogável na mão ou alguma
        # criatura apta a atacar.
        self.automatico: bool = automatico
        self._board_estavel_desde: float = 0.0
        self._ultima_assinatura_vista: str = ""

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
        # O conselho rápido tem prioridade na tela: é o que você lê no meio
        # do turno. A análise completa aparece embaixo, se existir.
        if self.rapida is not None and self.recomendacao is None:
            partes: list[Any] = []
            if self.rapida.alerta:
                partes.append(Text(f"🚨 {self.rapida.alerta}", style="bold red"))
                partes.append(Text(""))

            partes.append(Text(self.rapida.acao, style="bold green"))
            partes.append(Text(""))
            partes.append(Text(self.rapida.motivo, style="dim"))

            if self.rapida.atacar is not None:
                partes.append(Text(""))
                partes.append(
                    Text(
                        "⚔ ATACAR" if self.rapida.atacar else "🛡 NÃO atacar",
                        style="bold cyan",
                    )
                )

            partes.append(Text(""))
            partes.append(
                Text(
                    f"({self.rapida.segundos:.1f}s · [C] análise completa)",
                    style="dim",
                )
            )
            return Panel(Group(*partes), title="⚡ Conselho rápido",
                         border_style="green")

        if self.recomendacao is None:
            pronto = self._prefetch_resultado is not None
            estado_prefetch = (
                "[green]conselho já calculado — aperte J pra ver[/green]"
                if pronto
                else "[dim]calculando em segundo plano…[/dim]"
                if self._prefetch_thread and self._prefetch_thread.is_alive()
                else "[dim]aguardando mudança no board[/dim]"
            )
            return Panel(
                f"[dim]Pressione [bold]J[/bold] pra conselho rápido.[/dim]\n\n"
                f"{estado_prefetch}",
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
        """Faixa inferior com modo, atalhos, gasto e mensagens."""
        gasto = ""
        for servico in (self._recomendador, self._identificador):
            if servico is not None:
                cliente = servico.cliente
                gasto = (
                    f" · [dim]{cliente.chamadas} chamadas, "
                    f"{cliente.tokens_entrada + cliente.tokens_saida:,} tokens[/dim]"
                )
                break

        if self.automatico:
            modo = "[bold green]🤖 AUTOMÁTICO[/bold green] — o conselho aparece sozinho"
        else:
            modo = "[bold]✋ MANUAL[/bold] — aperte J pra pedir"

        prefetch = "[green]ON[/green]" if self.prefetch_ligado else "[dim]off[/dim]"
        atalhos = (
            "[bold]M[/bold] auto/manual · "
            "[bold]J[/bold] conselho · "
            "[bold]C[/bold] completa · "
            "[bold]A[/bold] oponente · "
            f"[bold]P[/bold] pré-cálculo ({prefetch}) · "
            "[bold]Q[/bold] sair"
        )
        cor = "yellow" if self.pensando else ("green" if self.automatico else "blue")
        return Panel(f"{modo}\n{atalhos}\n{self.mensagem}{gasto}", border_style=cor)

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

    def _garantir_recomendador(self) -> Any:
        """Cria o recomendador na primeira vez que for preciso."""
        from src.services.play_recommender import RecomendadorDeJogada

        if self._recomendador is None:
            cliente = self._identificador.cliente if self._identificador else None
            self._recomendador = RecomendadorDeJogada(cliente=cliente)
        return self._recomendador

    def pedir_jogada_rapida(self, estado: GameState) -> None:
        """Mostra o conselho rápido, usando o pré-cálculo se estiver pronto.

        Args:
            estado: Estado atual.
        """
        from src.services.play_recommender import RecomendadorDeJogada

        assinatura = RecomendadorDeJogada._assinatura(estado)

        # O pré-cálculo já respondeu pra ESTE board? Então é instantâneo.
        with self._trava:
            pronto = self._prefetch_resultado
            assinatura_pronta = self._prefetch_assinatura

        if pronto is not None and assinatura_pronta == assinatura:
            self.rapida = pronto
            self.recomendacao = None
            self.mensagem = "[green]Conselho pronto (pré-calculado).[/green]"
            return

        # Não deu tempo de pré-calcular: calcula agora mesmo.
        recomendador = self._garantir_recomendador()
        rapida = recomendador.recomendar_rapido(
            estado, self.analise, formato=self.formato
        )
        if rapida is None:
            self.mensagem = "[yellow]Nada pra decidir agora.[/yellow]"
            return

        self.rapida = rapida
        self.recomendacao = None
        self.mensagem = f"[green]Conselho em {rapida.segundos:.1f}s.[/green]"

    def pedir_jogada(self, estado: GameState) -> None:
        """Pede a análise COMPLETA da jogada — mais lenta, mais detalhada.

        Leva ~20s, então serve pra revisar entre turnos, não no meio de um.
        Analisa o oponente antes, se ainda não tiver feito.

        Args:
            estado: Estado atual.
        """
        if self.analise is None:
            self.analisar_oponente(estado)

        recomendacao = self._garantir_recomendador().recomendar(
            estado, self.analise, formato=self.formato
        )
        if recomendacao is None:
            self.mensagem = "[yellow]Nada pra decidir agora.[/yellow]"
            return

        self.recomendacao = recomendacao
        self.mensagem = "[green]Análise completa pronta.[/green]"

    def _vale_a_pena_calcular(self, estado: GameState) -> bool:
        """Decide se este momento merece uma chamada de IA.

        Cada chamada custa. Sem esse filtro, o painel gastaria token a cada
        animação de carta virando no turno do oponente — quando você não tem
        decisão nenhuma a tomar.

        Os critérios:
        - É o SEU turno (no turno dele você raramente decide algo)
        - Existe algo a fazer: carta na mão ou criatura apta a atacar

        Args:
            estado: Estado atual.

        Returns:
            True se vale gastar uma chamada.
        """
        if estado.meu_seat is None or estado.jogador_ativo != estado.meu_seat:
            return False
        return bool(estado.minha_mao or estado.criaturas_que_podem_atacar())

    def _talvez_pre_calcular(self, estado: GameState) -> None:
        """Dispara o cálculo do conselho em segundo plano, se o board mudou.

        Chamado a cada volta do laço. Só faz alguma coisa quando:
        - o pré-cálculo está ligado
        - vale a pena (seu turno, com decisão a tomar)
        - o board está ESTÁVEL há pelo menos um instante
        - o board mudou desde o último cálculo
        - não há outra thread já trabalhando

        O "board estável" evita um desperdício bobo: durante uma jogada o
        estado muda várias vezes em sequência (carta sai da mão, entra na
        pilha, resolve, entra em campo). Calcular a cada passo geraria
        conselhos sobre situações que duraram 200 milissegundos.

        A thread é `daemon` pra não segurar o programa se você fechar o
        painel no meio de um cálculo.

        Args:
            estado: Estado atual.
        """
        if not self.prefetch_ligado:
            return
        if self._prefetch_thread is not None and self._prefetch_thread.is_alive():
            return
        if not self._vale_a_pena_calcular(estado):
            return

        from src.services.play_recommender import RecomendadorDeJogada

        assinatura = RecomendadorDeJogada._assinatura(estado)

        # Espera o board parar de mudar antes de gastar uma chamada
        agora = time.monotonic()
        if assinatura != self._ultima_assinatura_vista:
            self._ultima_assinatura_vista = assinatura
            self._board_estavel_desde = agora
            return
        if agora - self._board_estavel_desde < ESPERA_BOARD_ESTAVEL:
            return

        with self._trava:
            if assinatura == self._prefetch_assinatura:
                return  # já calculado (ou em cálculo) pra este board
            self._prefetch_assinatura = assinatura
            self._prefetch_resultado = None

        # Fotografa o estado: o laço principal continua atualizando o
        # `estado` original enquanto a thread trabalha, e calcular em cima
        # de um objeto que muda no meio daria conselho sobre um board que
        # não existe mais.
        instantaneo = estado.model_copy(deep=True)

        def trabalhar() -> None:
            try:
                resultado = self._garantir_recomendador().recomendar_rapido(
                    instantaneo, self.analise, formato=self.formato
                )
            except Exception:
                # Falha no pré-cálculo é silenciosa de propósito: é um luxo,
                # não um requisito. Se falhar, o J calcula na hora e o
                # jogador vê o erro ali.
                resultado = None

            with self._trava:
                if self._prefetch_assinatura == assinatura:
                    self._prefetch_resultado = resultado
                    # No modo automático o conselho já sobe pra tela sozinho.
                    # É o que permite jogar sem tirar o foco do Arena.
                    if self.automatico and resultado is not None:
                        self.rapida = resultado
                        self.recomendacao = None
                        self.mensagem = (
                            f"[green]Conselho automático "
                            f"({resultado.segundos:.1f}s).[/green]"
                        )

        self._prefetch_thread = threading.Thread(target=trabalhar, daemon=True)
        self._prefetch_thread.start()

    # ------------------------------------------------------------------
    # Laço principal
    # ------------------------------------------------------------------

    def rodar(self) -> None:
        """Abre o painel e fica atualizando até você apertar Q."""
        estado = self.leitor.ler_arquivo_inteiro()

        if self.automatico:
            self.mensagem = (
                "[green]Modo automático ligado. Volte pro Arena e jogue — "
                "o conselho aparece aqui sozinho.[/green]"
            )
        elif not TEM_TECLADO:
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

                if tecla == "m":
                    self.automatico = not self.automatico
                    self.mensagem = (
                        "[green]Modo automático: o conselho aparece sozinho.[/green]"
                        if self.automatico
                        else "[yellow]Modo manual: aperte J pra pedir.[/yellow]"
                    )

                elif tecla == "p":
                    self.prefetch_ligado = not self.prefetch_ligado
                    self.mensagem = (
                        "[green]Pré-cálculo ligado.[/green]"
                        if self.prefetch_ligado
                        else "[yellow]Pré-cálculo desligado (economiza tokens).[/yellow]"
                    )

                elif tecla in ("a", "j", "c"):
                    # Mostra "pensando" ANTES de chamar a IA. Sem isso a tela
                    # congela por vários segundos sem explicação, e você não
                    # sabe se travou ou está trabalhando.
                    self.pensando = True
                    self.mensagem = "[yellow]Consultando a IA…[/yellow]"
                    live.update(self.montar(estado))

                    try:
                        if tecla == "a":
                            self.analisar_oponente(estado)
                        elif tecla == "j":
                            self.pedir_jogada_rapida(estado)
                        else:
                            self.pedir_jogada(estado)
                    except Exception as erro:
                        # Falha de IA não pode derrubar o painel no meio de
                        # uma partida. Mostra o problema e segue rodando.
                        self.mensagem = f"[red]Erro: {type(erro).__name__} — {erro}[/red]"
                    finally:
                        self.pensando = False

                self._talvez_pre_calcular(estado)
                live.update(self.montar(estado))
                time.sleep(intervalo)

        self.console.print("[dim]Painel encerrado.[/dim]")
        if self._identificador is not None:
            self.console.print(f"[dim]{self._identificador.cliente.resumo_de_gasto()}[/dim]")
