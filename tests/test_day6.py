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
