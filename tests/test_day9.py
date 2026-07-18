"""Testes de combate: atacar, bloquear, e limpar as marcas.

Rodar:
    venv\\Scripts\\python.exe -m pytest tests/test_day9.py -v -s
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.game_state import (  # noqa: E402
    Carta,
    CartaEmJogo,
    GameState,
    Jogador,
    Zona,
)
from src.services.arena_log_service import LeitorDeLogArena  # noqa: E402


class _BancoFalso:
    """Devolve uma carta pra qualquer grpId."""

    def buscar(self, grp_id: int) -> Carta:
        return Carta(grp_id=grp_id, nome_en=f"Carta{grp_id}")


def _leitor() -> LeitorDeLogArena:
    """Leitor sem depender do Arena instalado."""
    return LeitorDeLogArena(
        caminho_log=Path(__file__),
        banco=_BancoFalso(),  # type: ignore[arg-type]
    )


def _mensagem(tipo: str, **conteudo) -> dict:
    """Embrulha um gameStateMessage no formato do log."""
    return {
        "greToClientEvent": {
            "greToClientMessages": [
                {"gameStateMessage": {"type": tipo, **conteudo}}
            ]
        }
    }


def _carta(i: int, nome: str, zona: Zona, seat: int, **kw) -> CartaEmJogo:
    return CartaEmJogo(
        instance_id=i,
        carta=Carta(grp_id=i, nome_en=nome, nome_pt=nome),
        zona=zona, dono_seat=seat, controlador_seat=seat, **kw,
    )


# ----------------------------------------------------------------------
# Limpeza das marcas de combate
# ----------------------------------------------------------------------


def test_marca_de_ataque_some_ao_sair_do_combate() -> None:
    """A marca de "atacando" precisa ser apagada por nós.

    Descoberto num replay do log real: o Arena só escreve `attackState`
    quando alguém ataca — não existe um "AttackState_None". Conferido no
    log: só aparecem `AttackState_Declared` e `AttackState_Attacking`.

    Sem limpeza manual, a criatura fica atacando PARA SEMPRE. No replay, um
    Charmed Stray apareceu como atacante em 255 leituras seguidas, muito
    depois do combate acabar. O sistema acharia que o jogador está sob
    ataque a partida inteira: leitura errada e queima de tokens.
    """
    leitor = _leitor()

    # Combate: criatura ataca
    leitor.processar(
        _mensagem(
            "GameStateType_Diff",
            turnInfo={"turnNumber": 5, "phase": "Phase_Combat",
                      "step": "Step_DeclareAttack"},
            zones=[{"zoneId": 1, "type": "ZoneType_Battlefield", "ownerSeatId": 2}],
            gameObjects=[{
                "instanceId": 10, "grpId": 99, "zoneId": 1,
                "ownerSeatId": 2, "controllerSeatId": 2,
                "cardTypes": ["CardType_Creature"],
                "attackState": "AttackState_Attacking",
            }],
        )
    )
    assert leitor.estado.cartas[10].atacando, "Não registrou o ataque"

    # Combate acabou: fase mudou
    leitor.processar(
        _mensagem(
            "GameStateType_Diff",
            turnInfo={"phase": "Phase_Main2", "step": "Step_PostCombatMain"},
        )
    )
    assert not leitor.estado.cartas[10].atacando, (
        "A marca de ataque ficou grudada depois do combate"
    )
    print("OK - marca de ataque limpa ao sair do combate")


def test_marca_de_ataque_some_ao_virar_o_turno() -> None:
    """Combate não atravessa turno."""
    leitor = _leitor()

    leitor.processar(
        _mensagem(
            "GameStateType_Diff",
            turnInfo={"turnNumber": 5, "phase": "Phase_Combat"},
            zones=[{"zoneId": 1, "type": "ZoneType_Battlefield", "ownerSeatId": 2}],
            gameObjects=[{
                "instanceId": 10, "grpId": 99, "zoneId": 1,
                "ownerSeatId": 2, "controllerSeatId": 2,
                "cardTypes": ["CardType_Creature"],
                "attackState": "AttackState_Attacking",
            }],
        )
    )
    assert leitor.estado.cartas[10].atacando

    leitor.processar(_mensagem("GameStateType_Diff", turnInfo={"turnNumber": 6}))

    assert not leitor.estado.cartas[10].atacando, "Ataque atravessou o turno"
    print("OK - marca de ataque limpa ao virar o turno")


# ----------------------------------------------------------------------
# Decisão de bloqueio
# ----------------------------------------------------------------------


def _estado_sob_ataque(com_bloqueador: bool = True, mao: int = 0) -> GameState:
    """Oponente atacando; eu com ou sem bloqueador."""
    estado = GameState(meu_seat=1, turno=6, fase="Phase_Combat",
                       etapa="Step_DeclareBlock")
    estado.jogador_ativo = 2  # turno DELE
    estado.jogadores[1] = Jogador(seat=1, team_id=1, vida=12)
    estado.jogadores[2] = Jogador(seat=2, team_id=2, vida=18)

    estado.cartas[1] = _carta(
        1, "Soulblade Djinn", Zona.CAMPO, 2,
        tipos=["CardType_Creature"], poder_atual="5", resistencia_atual="3",
        atacando=True,
    )
    if com_bloqueador:
        estado.cartas[2] = _carta(
            2, "Molten Ravager", Zona.CAMPO, 1,
            tipos=["CardType_Creature"], poder_atual="0", resistencia_atual="4",
        )
    for n in range(mao):
        estado.cartas[100 + n] = _carta(100 + n, f"Carta{n}", Zona.MAO, 1)
    return estado


def test_detecta_decisao_de_bloqueio() -> None:
    """Ataque + bloqueador disponível = decisão a tomar."""
    estado = _estado_sob_ataque()

    assert estado.atacantes_do_oponente(), "Não viu o atacante"
    assert estado.minhas_criaturas_desviradas(), "Não viu meu bloqueador"
    assert estado.preciso_decidir_bloqueio()
    print("OK - detectou decisão de bloqueio")


def test_sem_bloqueador_nao_ha_decisao() -> None:
    """Sem criatura pra bloquear, não há escolha — não gasta chamada."""
    estado = _estado_sob_ataque(com_bloqueador=False)

    assert not estado.preciso_decidir_bloqueio()
    print("OK - sem bloqueador, sem decisão")


def test_bloqueio_conta_mesmo_com_mao_vazia() -> None:
    """Mão vazia não significa "nada a decidir".

    A guarda antiga só olhava mão e atacantes meus. Com a mão vazia no turno
    do oponente, ela devolvia "nada a decidir" — e o sistema ficava mudo
    justamente na hora de bloquear, que é das decisões mais caras de errar
    em Magic.
    """
    estado = _estado_sob_ataque(mao=0)

    assert not estado.minha_mao, "O teste precisa de mão vazia"
    assert not estado.criaturas_que_podem_atacar(), "É turno dele"
    assert estado.ha_algo_a_decidir(), (
        "Disse que não há nada a decidir, mas há um bloqueio pendente"
    )
    print("OK - bloqueio conta como decisão mesmo com mão vazia")


def test_criatura_virada_nao_serve_de_bloqueador() -> None:
    """Criatura virada não bloqueia — não adianta contar como opção."""
    estado = _estado_sob_ataque()
    estado.cartas[2].virada = True

    assert not estado.minhas_criaturas_desviradas()
    assert not estado.preciso_decidir_bloqueio()
    print("OK - criatura virada não conta como bloqueador")


def test_criatura_enjoada_serve_de_bloqueador() -> None:
    """Enjoo impede atacar, não bloquear. Confundir muda a conta de combate."""
    estado = _estado_sob_ataque()
    estado.cartas[2].enjoada = True

    assert estado.minhas_criaturas_desviradas(), "Enjoada bloqueia sim"
    assert estado.preciso_decidir_bloqueio()
    print("OK - criatura enjoada pode bloquear")


# ----------------------------------------------------------------------
# Integração com o copiloto
# ----------------------------------------------------------------------


def test_copiloto_calcula_durante_ataque_do_oponente() -> None:
    """O copiloto precisa falar quando você está sendo atacado.

    O filtro de custo original só liberava chamada no SEU turno. Bloquear
    acontece no turno DELE — o sistema ficava mudo na hora errada.
    """
    from src.services.copiloto import Copiloto

    class CopilotoDeTeste(Copiloto):
        def __init__(self) -> None:  # sem log, sem banco
            self.estado = GameState()
            self.formato = "standard"
            self.automatico = True

    copiloto = CopilotoDeTeste()
    copiloto.estado = _estado_sob_ataque()

    assert not copiloto.e_meu_turno(), "O teste precisa ser no turno dele"
    assert copiloto.estou_sendo_atacado()
    assert copiloto.vale_a_pena_calcular(), (
        "Não vai dar conselho durante o ataque do oponente"
    )
    print("OK - copiloto fala durante o ataque do oponente")


def test_copiloto_calado_no_turno_dele_sem_ataque() -> None:
    """Turno dele sem ataque nenhum: fica quieto e não gasta."""
    from src.services.copiloto import Copiloto

    class CopilotoDeTeste(Copiloto):
        def __init__(self) -> None:
            self.estado = GameState()
            self.formato = "standard"
            self.automatico = True

    copiloto = CopilotoDeTeste()
    estado = _estado_sob_ataque()
    estado.cartas[1].atacando = False  # ninguém atacando

    copiloto.estado = estado

    assert not copiloto.vale_a_pena_calcular(), "Gastou chamada à toa"
    print("OK - turno dele sem ataque: não gasta")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
