"""Testes do analisador pós-jogo.

Rodar:
    venv\\Scripts\\python.exe -m pytest tests/test_day7.py -v -s
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
    ResultadoPartida,
    Zona,
)
from src.services.post_game_analyzer import (  # noqa: E402
    AnalisadorPosJogo,
    PartidaNaoTerminou,
)


def _carta(i: int, nome: str, zona: Zona, seat: int, **kw) -> CartaEmJogo:
    return CartaEmJogo(
        instance_id=i,
        carta=Carta(grp_id=i, nome_en=nome, nome_pt=nome),
        zona=zona,
        dono_seat=seat,
        controlador_seat=seat,
        **kw,
    )


def _partida_encerrada() -> GameState:
    """Partida perdida, com cartas dos dois lados."""
    estado = GameState(meu_seat=1, turno=11, numero_do_jogo=2)
    estado.jogadores[1] = Jogador(seat=1, team_id=1, vida=-7)
    estado.jogadores[2] = Jogador(seat=2, team_id=2, vida=4)
    estado.resultado = ResultadoPartida(
        match_id="teste", time_vencedor=2, eu_venci=False, motivo="ResultReason_Game"
    )
    for c in [
        _carta(1, "Nest Robber", Zona.CAMPO, 1, tipos=["CardType_Creature"],
               poder_atual="2", resistencia_atual="1"),
        _carta(2, "Siege Dragon", Zona.MAO, 1),
        _carta(3, "Soulblade Djinn", Zona.CAMPO, 2, tipos=["CardType_Creature"],
               poder_atual="5", resistencia_atual="3"),
        _carta(4, "Wanderwine Distracter", Zona.CAMPO, 2,
               tipos=["CardType_Creature"], poder_atual="4", resistencia_atual="3"),
    ]:
        estado.cartas[c.instance_id] = c
    return estado


def test_recusa_partida_em_andamento() -> None:
    """Não dá pra tirar lição de uma partida que ainda está rolando.

    Erro real: o analisador pegou o jogo em andamento (turno 7, 18x20) e
    escreveu "perdi porque terminei com zero criaturas" sobre uma partida no
    meio. Análise confiante da partida errada é pior que análise nenhuma —
    o jogador aprende algo que não aconteceu.
    """

    class ClienteQueExplode:
        def perguntar_json(self, **_k: object) -> dict:
            raise AssertionError("Chamou a IA sobre partida em andamento!")

    analisador = AnalisadorPosJogo(cliente=ClienteQueExplode())  # type: ignore[arg-type]
    em_andamento = GameState(meu_seat=1, turno=7)  # sem resultado

    with pytest.raises(PartidaNaoTerminou, match="em andamento"):
        analisador.analisar(em_andamento)

    print("OK - recusou analisar partida em andamento")


def test_aceita_partida_encerrada() -> None:
    """Partida com resultado registrado passa na guarda."""

    class ClienteFalso:
        def perguntar_json(self, **_k: object) -> dict:
            return {"verdict": "perdi porque X", "lethal_was_available": False}

    analisador = AnalisadorPosJogo(cliente=ClienteFalso())  # type: ignore[arg-type]
    analise = analisador.analisar(_partida_encerrada())

    assert analise.veredito == "perdi porque X"
    assert analise.eu_venci is False
    print("OK - analisou partida encerrada")


def test_prompt_separa_minhas_cartas_das_dele() -> None:
    """O sideboard só pode mexer no MEU deck.

    Erro real: a IA sugeriu "tirar Wanderwine Distracter" do deck do jogador.
    Essa carta era do OPONENTE — estava no board dele como bloqueador.
    """
    enviado = {"texto": ""}

    class ClienteEspiao:
        def perguntar_json(self, sistema: str, usuario: str, **_k: object) -> dict:
            enviado["texto"] = usuario
            return {"verdict": "x"}

    analisador = AnalisadorPosJogo(cliente=ClienteEspiao())  # type: ignore[arg-type]
    analisador.analisar(_partida_encerrada())

    texto = enviado["texto"]
    assert "DE QUEM É CADA CARTA" in texto, "Faltou a separação de propriedade"
    assert "NUNCA sugira tirar" in texto, "Faltou a proibição explícita"

    # A carta do oponente tem que aparecer na lista DELE, não na minha
    posicao_minhas = texto.index("Cartas do MEU deck")
    posicao_dele = texto.index("Cartas do DECK DELE")
    trecho_minhas = texto[posicao_minhas:posicao_dele]

    assert "Nest Robber" in trecho_minhas, "Minha carta não entrou na minha lista"
    assert "Wanderwine Distracter" not in trecho_minhas, (
        "Carta do oponente vazou pra lista das minhas cartas"
    )
    print("OK - prompt separa minhas cartas das do oponente")


def test_ultimo_jogo_encerrado_ignora_em_andamento() -> None:
    """O leitor sabe escolher a partida certa pra revisar."""
    from src.services.arena_log_service import LeitorDeLogArena

    class LeitorDeMentira(LeitorDeLogArena):
        def __init__(self) -> None:  # não chama o super: sem log, sem banco
            self.jogos_anteriores = []
            self.estado = GameState()

    leitor = LeitorDeMentira()

    encerrado = _partida_encerrada()
    em_andamento = GameState(meu_seat=1, turno=3, numero_do_jogo=3)

    leitor.jogos_anteriores = [encerrado]
    leitor.estado = em_andamento

    escolhido = leitor.ultimo_jogo_encerrado()

    assert escolhido is encerrado, "Escolheu a partida em andamento"
    print("OK - escolheu o último jogo ENCERRADO, não o atual")


def test_sem_jogo_encerrado_devolve_none() -> None:
    """Se nada terminou ainda, diz isso em vez de inventar."""
    from src.services.arena_log_service import LeitorDeLogArena

    class LeitorDeMentira(LeitorDeLogArena):
        def __init__(self) -> None:
            self.jogos_anteriores = []
            self.estado = GameState(turno=2)

    assert LeitorDeMentira().ultimo_jogo_encerrado() is None
    print("OK - sem partida encerrada, devolve None")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
