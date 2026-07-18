"""Testes do painel (interface principal).

O painel é o que o jogador vê durante a partida. Um erro aqui não corrompe
dado nenhum, mas derruba a tela no meio de um jogo — que na prática é o
mesmo que o sistema não existir.

Rodar:
    venv\\Scripts\\python.exe -m pytest tests/test_day6.py -v -s
"""

import sys
from pathlib import Path

import pytest
from rich.console import Console

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.game_state import (  # noqa: E402
    Carta,
    CartaEmJogo,
    GameState,
    Jogador,
    Zona,
)
from src.services.arena_paths import ArenaNaoEncontrado, caminho_do_log  # noqa: E402


def _arena_disponivel() -> bool:
    try:
        caminho_do_log()
        return True
    except (ArenaNaoEncontrado, OSError):
        return False


precisa_do_arena = pytest.mark.skipif(
    not _arena_disponivel(), reason="MTG Arena não encontrado"
)


def _estado_cheio() -> GameState:
    """Um board com cartas em todas as zonas relevantes."""
    estado = GameState(meu_seat=1, turno=6, etapa="Step_Draw", jogador_ativo=1,
                       numero_do_jogo=2)
    estado.jogadores[1] = Jogador(seat=1, team_id=1, vida=16)
    estado.jogadores[2] = Jogador(seat=2, team_id=2, vida=20)

    def carta(i, nome, zona, seat, **kw):
        return CartaEmJogo(
            instance_id=i,
            carta=Carta(grp_id=i, nome_en=nome, nome_pt=f"{nome} PT"),
            zona=zona, dono_seat=seat, controlador_seat=seat, **kw,
        )

    for c in [
        carta(1, "Mountain", Zona.CAMPO, 1, tipos=["CardType_Land"],
              subtipos=["SubType_Mountain"]),
        carta(2, "Nest Robber", Zona.CAMPO, 1, tipos=["CardType_Creature"],
              poder_atual="2", resistencia_atual="1", enjoada=True),
        carta(3, "Shock", Zona.MAO, 1),
        carta(4, "Island", Zona.CAMPO, 2, tipos=["CardType_Land"],
              subtipos=["SubType_Island"], virada=True),
        carta(5, "Cloudkin Seer", Zona.CAMPO, 2, tipos=["CardType_Creature"],
              poder_atual="2", resistencia_atual="1", atacando=True),
        carta(6, "Unsummon", Zona.CEMITERIO, 2),
    ]:
        estado.cartas[c.instance_id] = c
    return estado


def _desenhar(painel, estado: GameState) -> str:
    """Renderiza a tela num buffer e devolve o texto."""
    console = Console(width=160, height=40, record=True)
    console.print(painel.montar(estado))
    return console.export_text()


@precisa_do_arena
def test_painel_desenha_sem_quebrar() -> None:
    """A tela monta com um board cheio."""
    from src.ui.dashboard import Painel

    painel = Painel(formato="standard")
    texto = _desenhar(painel, _estado_cheio())

    assert "MAGIC AI ADVISOR" in texto
    assert "Turno 6" in texto
    assert "Jogo 2" in texto
    print("OK - painel desenhou com board cheio")


@precisa_do_arena
def test_painel_desenha_com_estado_vazio() -> None:
    """Board vazio (antes da partida começar) não pode quebrar a tela.

    Caso real: ao abrir o painel entre partidas, o estado vem sem jogadores
    e sem cartas. Se `minha_vida` ou `mana_disponivel` estourarem aqui, o
    sistema não abre.
    """
    from src.ui.dashboard import Painel

    painel = Painel(formato="standard")
    texto = _desenhar(painel, GameState())

    assert "MAGIC AI ADVISOR" in texto
    assert "vazio" in texto.lower()
    print("OK - painel desenhou com estado vazio")


@precisa_do_arena
def test_painel_mostra_nomes_em_portugues() -> None:
    """A interface é em português, mesmo a IA raciocinando em inglês."""
    from src.ui.dashboard import Painel

    painel = Painel(formato="standard")
    texto = _desenhar(painel, _estado_cheio())

    assert "Shock PT" in texto, "Não usou o nome em português na tela"
    print("OK - tela em português")


@precisa_do_arena
def test_painel_marca_enjoada_e_virada() -> None:
    """Os estados que mudam a decisão precisam aparecer na tela."""
    from src.ui.dashboard import Painel

    painel = Painel(formato="standard")
    texto = _desenhar(painel, _estado_cheio())

    assert "enjoada" in texto, "Não marcou criatura enjoada"
    assert "virada" in texto, "Não marcou permanente virada"
    assert "atacando" in texto, "Não marcou criatura atacando"
    print("OK - tela marca enjoada, virada e atacando")


@precisa_do_arena
def test_painel_nao_chama_ia_ao_abrir() -> None:
    """Abrir o painel não pode gastar dinheiro.

    Os serviços de IA só são criados quando você aperta A ou J. Assim o
    painel abre instantâneo e funciona sem internet.
    """
    from src.ui.dashboard import Painel

    painel = Painel(formato="standard")

    assert painel._identificador is None, "Criou o identificador ao abrir"
    assert painel._recomendador is None, "Criou o recomendador ao abrir"
    print("OK - painel abre sem tocar na IA")


@precisa_do_arena
def test_prefetch_dispara_e_entrega_pronto() -> None:
    """O pré-cálculo roda em segundo plano e o J pega o resultado pronto.

    É o que transforma 2,5s de espera em 0. Sem isso, você aperta J no meio
    do turno e olha pra tela travada.
    """
    import time as _time

    from src.ui.dashboard import Painel

    painel = Painel(formato="standard")
    estado = _estado_cheio()

    class RecomendadorFalso:
        def recomendar_rapido(self, est, analise=None, formato="standard"):
            _time.sleep(0.05)  # simula a latência da IA

            class R:
                acao = "Atacar com tudo"
                motivo = "Board livre"
                atacar = True
                alerta = ""
                segundos = 0.05

            return R()

    painel._recomendador = RecomendadorFalso()

    # A primeira chamada só marca o board como visto; o disparo só acontece
    # depois que ele fica estável (ver ESPERA_BOARD_ESTAVEL).
    painel._talvez_pre_calcular(estado)
    painel._board_estavel_desde = 0.0
    painel._talvez_pre_calcular(estado)

    assert painel._prefetch_thread is not None

    painel._prefetch_thread.join(timeout=3)
    assert painel._prefetch_resultado is not None, "Pré-cálculo não entregou"

    # Agora o J tem que ser instantâneo
    inicio = _time.monotonic()
    painel.pedir_jogada_rapida(estado)
    duracao = _time.monotonic() - inicio

    assert painel.rapida is not None
    assert painel.rapida.acao == "Atacar com tudo"
    assert duracao < 0.05, f"Não usou o pré-cálculo: {duracao:.3f}s"
    print(f"OK - pré-cálculo entregue em {duracao*1000:.1f}ms")


@precisa_do_arena
def test_prefetch_nao_recalcula_o_mesmo_board() -> None:
    """Board parado não pode ficar queimando tokens em segundo plano."""
    from src.ui.dashboard import Painel

    chamadas = {"total": 0}

    class RecomendadorContado:
        def recomendar_rapido(self, est, analise=None, formato="standard"):
            chamadas["total"] += 1
            return None

    painel = Painel(formato="standard")
    painel._recomendador = RecomendadorContado()
    estado = _estado_cheio()

    for _ in range(5):
        painel._board_estavel_desde = 0.0  # finge que já estabilizou
        painel._talvez_pre_calcular(estado)
        if painel._prefetch_thread:
            painel._prefetch_thread.join(timeout=2)

    assert chamadas["total"] == 1, (
        f"Recalculou {chamadas['total']}x o mesmo board — queima de tokens"
    )
    print("OK - board parado não dispara recálculo")


@precisa_do_arena
def test_prefetch_desligado_nao_dispara() -> None:
    """Dá pra desligar o pré-cálculo (tecla P) pra economizar tokens."""
    from src.ui.dashboard import Painel

    painel = Painel(formato="standard")
    painel.prefetch_ligado = False

    painel._talvez_pre_calcular(_estado_cheio())

    assert painel._prefetch_thread is None, "Disparou mesmo desligado"
    print("OK - pré-cálculo desligado não dispara")


@precisa_do_arena
def test_automatico_nao_calcula_no_turno_do_oponente() -> None:
    """No turno dele você raramente decide algo — não vale gastar chamada.

    Sem esse filtro o painel queimaria token a cada animação de carta durante
    o turno inteiro do oponente.
    """
    from src.ui.dashboard import Painel

    painel = Painel(formato="standard")
    estado = _estado_cheio()
    estado.jogador_ativo = 2  # turno do oponente (eu sou o assento 1)

    assert not painel._vale_a_pena_calcular(estado)
    print("OK - não calcula no turno do oponente")


@precisa_do_arena
def test_automatico_calcula_no_meu_turno() -> None:
    """No meu turno, com carta na mão, vale calcular."""
    from src.ui.dashboard import Painel

    painel = Painel(formato="standard")
    estado = _estado_cheio()
    estado.jogador_ativo = 1  # meu turno

    assert painel._vale_a_pena_calcular(estado)
    print("OK - calcula no meu turno")


@precisa_do_arena
def test_automatico_espera_board_estabilizar() -> None:
    """Board mudando não pode disparar cálculo a cada mudancinha.

    Durante uma jogada o estado muda várias vezes em sequência: a carta sai
    da mão, vai pra pilha, resolve, entra em campo. Calcular a cada passo
    daria conselho sobre situações que duraram 200 milissegundos — e cobraria
    por cada uma.
    """
    from src.ui.dashboard import Painel

    painel = Painel(formato="standard")
    estado = _estado_cheio()
    estado.jogador_ativo = 1

    # Primeira vez: só marca o board como "visto agora", não dispara
    painel._talvez_pre_calcular(estado)
    assert painel._prefetch_thread is None, "Disparou sem esperar estabilizar"

    # Logo em seguida, board igual mas ainda dentro da janela de espera
    painel._talvez_pre_calcular(estado)
    assert painel._prefetch_thread is None, "Disparou antes da espera terminar"

    print("OK - espera o board estabilizar antes de gastar chamada")


@precisa_do_arena
def test_automatico_publica_resultado_sozinho() -> None:
    """No automático, o conselho sobe pra tela sem ninguém apertar tecla.

    É o que permite jogar com um monitor só: o Arena fica em foco e o painel
    atualiza sozinho.
    """
    import time as _time

    from src.ui.dashboard import Painel

    painel = Painel(formato="standard", automatico=True)
    estado = _estado_cheio()
    estado.jogador_ativo = 1

    class RecomendadorFalso:
        def recomendar_rapido(self, est, analise=None, formato="standard"):
            class R:
                acao = "Atacar com Nest Robber"
                motivo = "Board livre"
                atacar = True
                alerta = ""
                segundos = 0.1

            return R()

    painel._recomendador = RecomendadorFalso()

    # Simula o board já estável
    painel._talvez_pre_calcular(estado)
    painel._board_estavel_desde = 0.0
    painel._talvez_pre_calcular(estado)

    assert painel._prefetch_thread is not None
    painel._prefetch_thread.join(timeout=3)
    _time.sleep(0.05)

    assert painel.rapida is not None, "Não publicou o conselho sozinho"
    assert painel.rapida.acao == "Atacar com Nest Robber"
    print("OK - conselho publicado automaticamente, sem tecla")


@precisa_do_arena
def test_manual_nao_publica_sozinho() -> None:
    """No manual, o pré-cálculo fica guardado até você apertar J."""
    from src.ui.dashboard import Painel

    painel = Painel(formato="standard", automatico=False)
    estado = _estado_cheio()
    estado.jogador_ativo = 1

    class RecomendadorFalso:
        def recomendar_rapido(self, est, analise=None, formato="standard"):
            class R:
                acao = "x"
                motivo = "y"
                atacar = None
                alerta = ""
                segundos = 0.1

            return R()

    painel._recomendador = RecomendadorFalso()
    painel._talvez_pre_calcular(estado)
    painel._board_estavel_desde = 0.0
    painel._talvez_pre_calcular(estado)

    if painel._prefetch_thread:
        painel._prefetch_thread.join(timeout=3)

    assert painel.rapida is None, "Publicou sozinho no modo manual"
    assert painel._prefetch_resultado is not None, "Não guardou o pré-cálculo"
    print("OK - manual guarda o resultado sem publicar")


def test_ler_tecla_nao_trava_sem_tecla() -> None:
    """Ler o teclado sem ninguém digitando devolve vazio na hora.

    Se travasse, o painel congelaria esperando uma tecla e pararia de
    acompanhar a partida.
    """
    from src.ui.dashboard import ler_tecla

    assert ler_tecla() == ""
    print("OK - leitura de tecla não bloqueia")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
