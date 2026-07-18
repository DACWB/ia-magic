"""O motor do copiloto — lê o jogo e decide quando pedir conselho.

## Por que este arquivo existe

O painel do terminal e o painel do navegador precisam fazer exatamente a mesma
coisa: ler o log, decidir quando vale gastar uma chamada de IA, calcular em
segundo plano e publicar o resultado.

Se cada um implementasse isso do seu jeito, em duas semanas teriam
comportamentos diferentes e a gente estaria mantendo dois sistemas. Toda a
lógica mora aqui; as telas só desenham.

## A regra de ouro: quando gastar uma chamada

Cada conselho custa dinheiro e ~2,5 segundos. Sem freio, o sistema queimaria
token a cada animação de carta. Os critérios são:

1. É o SEU turno (no turno do oponente você raramente decide algo)
2. Existe decisão a tomar (carta na mão ou criatura apta a atacar)
3. O board está PARADO há pelo menos 1,5 segundo

O terceiro é o menos óbvio e o mais importante. Durante uma jogada o estado
muda várias vezes em sequência — a carta sai da mão, entra na pilha, resolve,
entra em campo. Sem essa espera, o sistema daria conselho sobre situações que
duraram 200 milissegundos, e cobraria por cada uma.
"""

import threading
import time
from typing import Any

from src.models.game_state import GameState
from src.services.arena_log_service import LeitorDeLogArena

# Quanto tempo o board precisa ficar parado antes de valer uma chamada de IA.
ESPERA_BOARD_ESTAVEL = 1.5


class Copiloto:
    """Acompanha a partida e produz conselho quando faz sentido.

    Uso:
        copiloto = Copiloto(formato="standard")
        while True:
            estado = copiloto.atualizar()   # grátis, lê o log
            copiloto.talvez_calcular()      # dispara IA se valer a pena
            if copiloto.rapida:
                print(copiloto.rapida.acao)

    Attributes:
        estado: Estado atual da partida.
        analise: Análise do deck do oponente, se já pedida.
        rapida: Último conselho rápido.
        completa: Última análise completa de jogada.
        automatico: Se o conselho é publicado sozinho.
    """

    def __init__(self, formato: str = "standard", automatico: bool = True) -> None:
        """Prepara o copiloto.

        Args:
            formato: Formato do jogo, pra calibrar a IA.
            automatico: Se True, publica o conselho sem precisar pedir.
        """
        self.formato = formato
        self.automatico = automatico
        self.leitor = LeitorDeLogArena()
        self.estado: GameState = GameState()

        self.analise: Any = None
        self.rapida: Any = None
        self.completa: Any = None
        self.mensagem: str = ""
        self.erro: str = ""

        # Serviços de IA nascem só no primeiro uso, pro sistema abrir
        # instantâneo e funcionar sem internet até você pedir algo.
        self._identificador: Any = None
        self._recomendador: Any = None

        self._thread: threading.Thread | None = None
        self._trava = threading.Lock()
        self._assinatura_calculada: str = ""
        self._assinatura_vista: str = ""
        self._estavel_desde: float = 0.0
        self.calculando: bool = False

    # ------------------------------------------------------------------
    # Leitura (grátis)
    # ------------------------------------------------------------------

    def carregar_tudo(self) -> GameState:
        """Lê o log inteiro. Use uma vez, ao iniciar.

        Returns:
            O estado da partida atual.
        """
        self.estado = self.leitor.ler_arquivo_inteiro()
        return self.estado

    def atualizar(self) -> GameState:
        """Lê só o que o Arena escreveu desde a última vez.

        Returns:
            O estado atualizado.
        """
        self.estado = self.leitor.ler_novidades()
        return self.estado

    # ------------------------------------------------------------------
    # Decisão de gasto
    # ------------------------------------------------------------------

    def ha_decisao_a_tomar(self) -> bool:
        """Se existe alguma jogada possível agora.

        Returns:
            True se há carta na mão, criatura apta a atacar, ou bloqueio a
            decidir.
        """
        return self.estado.ha_algo_a_decidir()

    def e_meu_turno(self) -> bool:
        """Se o turno é do jogador local.

        Returns:
            True se for o meu turno.
        """
        return (
            self.estado.meu_seat is not None
            and self.estado.jogador_ativo == self.estado.meu_seat
        )

    def estou_sendo_atacado(self) -> bool:
        """Se o oponente declarou ataque e eu preciso decidir bloqueios.

        Existe porque a primeira versão do filtro de custo só calculava no
        MEU turno — e isso deixava o sistema mudo justamente na decisão mais
        cara de errar em Magic: quem bloqueia o quê.

        Bloquear acontece no turno DELE. Um copiloto que só fala no seu turno
        perde metade das decisões importantes da partida.

        Returns:
            True se há criatura dele atacando e eu tenho com que bloquear.
        """
        alguem_atacando = any(
            carta.atacando for carta in self.estado.campo_oponente
        )
        if not alguem_atacando:
            return False

        # Só vale conselho se eu tiver escolha. Sem bloqueador, não há decisão.
        tenho_bloqueador = any(
            carta.eh_criatura and not carta.virada
            for carta in self.estado.meu_campo
        )
        return tenho_bloqueador

    def vale_a_pena_calcular(self) -> bool:
        """Se este momento merece uma chamada de IA.

        Dois momentos valem:
        1. Meu turno com algo a fazer (baixar carta, atacar)
        2. Estou sendo atacado e tenho como bloquear

        Returns:
            True se vale gastar.
        """
        if self.estou_sendo_atacado():
            return True
        return self.e_meu_turno() and self.ha_decisao_a_tomar()

    def _assinatura(self) -> str:
        """Resume o board numa string, pra detectar mudança real."""
        from src.services.play_recommender import RecomendadorDeJogada

        return RecomendadorDeJogada._assinatura(self.estado)

    # ------------------------------------------------------------------
    # Serviços de IA
    # ------------------------------------------------------------------

    def _garantir_identificador(self) -> Any:
        """Cria o identificador de deck na primeira vez que for preciso."""
        from src.services.deck_identifier import IdentificadorDeDeck

        if self._identificador is None:
            self._identificador = IdentificadorDeDeck()
        return self._identificador

    def _garantir_recomendador(self) -> Any:
        """Cria o recomendador na primeira vez que for preciso."""
        from src.services.play_recommender import RecomendadorDeJogada

        if self._recomendador is None:
            cliente = self._identificador.cliente if self._identificador else None
            self._recomendador = RecomendadorDeJogada(cliente=cliente)
        return self._recomendador

    def gasto(self) -> dict[str, int]:
        """Quanto foi gasto até agora.

        Returns:
            Dicionário com chamadas e tokens.
        """
        for servico in (self._recomendador, self._identificador):
            if servico is not None:
                cliente = servico.cliente
                return {
                    "chamadas": cliente.chamadas,
                    "tokens_entrada": cliente.tokens_entrada,
                    "tokens_saida": cliente.tokens_saida,
                }
        return {"chamadas": 0, "tokens_entrada": 0, "tokens_saida": 0}

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def analisar_oponente(self) -> Any:
        """Identifica o deck do oponente.

        Returns:
            A análise, ou None se o oponente não revelou nada.
        """
        if not self.estado.cartas_reveladas_do_oponente():
            self.mensagem = "O oponente ainda não revelou nenhuma carta."
            return None

        self.analise = self._garantir_identificador().identificar(
            self.estado, formato=self.formato
        )
        self.mensagem = "Oponente analisado."
        return self.analise

    def conselho_rapido(self) -> Any:
        """Conselho enxuto (~2,5s), pra usar no meio do turno.

        Returns:
            O conselho, ou None se não há nada a decidir.
        """
        rapida = self._garantir_recomendador().recomendar_rapido(
            self.estado, self.analise, formato=self.formato
        )
        if rapida is not None:
            self.rapida = rapida
            self.completa = None
            self.mensagem = f"Conselho em {rapida.segundos:.1f}s."
        return rapida

    def analise_completa(self) -> Any:
        """Análise detalhada da jogada (~20s), pra entre turnos.

        Returns:
            A análise, ou None se não há nada a decidir.
        """
        if self.analise is None:
            self.analisar_oponente()

        completa = self._garantir_recomendador().recomendar(
            self.estado, self.analise, formato=self.formato
        )
        if completa is not None:
            self.completa = completa
            self.mensagem = "Análise completa pronta."
        return completa

    # ------------------------------------------------------------------
    # Cálculo em segundo plano
    # ------------------------------------------------------------------

    def talvez_calcular(self) -> None:
        """Dispara o cálculo em segundo plano, se for a hora.

        Chame a cada volta do laço da interface. Não bloqueia.
        """
        if self._thread is not None and self._thread.is_alive():
            return
        if not self.vale_a_pena_calcular():
            return

        assinatura = self._assinatura()

        # Espera o board parar de mudar
        agora = time.monotonic()
        if assinatura != self._assinatura_vista:
            self._assinatura_vista = assinatura
            self._estavel_desde = agora
            return
        if agora - self._estavel_desde < ESPERA_BOARD_ESTAVEL:
            return

        with self._trava:
            if assinatura == self._assinatura_calculada:
                return  # já calculado pra este board
            self._assinatura_calculada = assinatura

        # Fotografa o estado: o laço da interface continua atualizando o
        # objeto original, e calcular sobre algo que muda no meio daria
        # conselho sobre um board que não existe mais.
        instantaneo = self.estado.model_copy(deep=True)

        def trabalhar() -> None:
            self.calculando = True
            try:
                resultado = self._garantir_recomendador().recomendar_rapido(
                    instantaneo, self.analise, formato=self.formato
                )
                if resultado is not None and self.automatico:
                    self.rapida = resultado
                    self.completa = None
                    self.mensagem = (
                        f"Conselho automático ({resultado.segundos:.1f}s)."
                    )
                elif resultado is not None:
                    with self._trava:
                        self._pronto_aguardando = resultado
            except Exception as erro:
                # Falha no cálculo automático é silenciosa na tela mas fica
                # registrada: é um luxo, não um requisito. Se falhar, o
                # jogador ainda pode pedir na mão.
                self.erro = f"{type(erro).__name__}: {erro}"
            finally:
                self.calculando = False

        self._thread = threading.Thread(target=trabalhar, daemon=True)
        self._thread.start()
