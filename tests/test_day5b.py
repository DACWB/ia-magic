"""Testes do recomendador de jogada.

Rodar:
    venv\\Scripts\\python.exe -m pytest tests/test_day5b.py -v -s
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
from src.services.play_recommender import RecomendadorDeJogada  # noqa: E402
from src.utils.config import config  # noqa: E402

precisa_de_api = pytest.mark.skipif(
    not config.chave_api_configurada(),
    reason="Sem chave de API no .env",
)


def _carta(
    instancia: int,
    nome: str,
    zona: Zona,
    seat: int,
    tipos: list[str] | None = None,
    subtipos: list[str] | None = None,
    virada: bool = False,
    enjoada: bool = False,
    poder: str = "",
    resistencia: str = "",
) -> CartaEmJogo:
    """Atalho pra montar cartas nos testes."""
    return CartaEmJogo(
        instance_id=instancia,
        carta=Carta(grp_id=instancia, nome_en=nome, nome_pt=nome),
        zona=zona,
        dono_seat=seat,
        controlador_seat=seat,
        tipos=tipos or [],
        subtipos=subtipos or [],
        virada=virada,
        enjoada=enjoada,
        poder_atual=poder,
        resistencia_atual=resistencia,
    )


def _estado_de_combate() -> GameState:
    """Board realista: eu de vermelho, oponente de azul com um bloqueador.

    Situação: turno 5, tenho 3 Montanhas (uma virada), um Nest Robber pronto
    pra atacar e um Goblin recém-jogado (enjoado). O oponente tem um
    Cloudkin Seer desvirado que pode bloquear.
    """
    estado = GameState(meu_seat=1, turno=5, fase="Phase_Main1",
                       etapa="Step_PreCombatMain", jogador_ativo=1)
    estado.jogadores[1] = Jogador(seat=1, team_id=1, vida=16)
    estado.jogadores[2] = Jogador(seat=2, team_id=2, vida=12)

    cartas = [
        # Meus terrenos: 2 desvirados, 1 virada
        _carta(1, "Mountain", Zona.CAMPO, 1, ["CardType_Land"], ["SubType_Mountain"]),
        _carta(2, "Mountain", Zona.CAMPO, 1, ["CardType_Land"], ["SubType_Mountain"]),
        _carta(3, "Mountain", Zona.CAMPO, 1, ["CardType_Land"], ["SubType_Mountain"],
               virada=True),
        # Minhas criaturas
        _carta(4, "Nest Robber", Zona.CAMPO, 1, ["CardType_Creature"], [],
               poder="2", resistencia="1"),
        _carta(5, "Goblin", Zona.CAMPO, 1, ["CardType_Creature"], [],
               enjoada=True, poder="1", resistencia="1"),
        # Minha mão
        _carta(6, "Shock", Zona.MAO, 1, ["CardType_Instant"]),
        _carta(7, "Ogre Battledriver", Zona.MAO, 1, ["CardType_Creature"], [],
               poder="3", resistencia="3"),
        # Oponente
        _carta(8, "Island", Zona.CAMPO, 2, ["CardType_Land"], ["SubType_Island"]),
        _carta(9, "Island", Zona.CAMPO, 2, ["CardType_Land"], ["SubType_Island"]),
        _carta(10, "Cloudkin Seer", Zona.CAMPO, 2, ["CardType_Creature"], [],
               poder="2", resistencia="1"),
    ]
    for carta in cartas:
        estado.cartas[carta.instance_id] = carta
    return estado


# ----------------------------------------------------------------------
# Cálculo de mana e combate (sem custo de API)
# ----------------------------------------------------------------------


def test_conta_mana_por_cor() -> None:
    """Terrenos desvirados viram mana; virados não contam."""
    estado = _estado_de_combate()
    mana = estado.mana_disponivel()

    assert mana["total"] == 2, f"Devia ter 2 mana (1 Montanha está virada): {mana}"
    assert mana["R"] == 2, "Montanha produz vermelho"
    assert mana["U"] == 0, "Não tenho fonte de azul"
    print(f"OK - mana: total={mana['total']}, R={mana['R']}")


def test_mana_do_oponente_e_separada() -> None:
    """Contar mana de um jogador não pode misturar com a do outro."""
    estado = _estado_de_combate()
    minha = estado.mana_disponivel()
    dele = estado.mana_disponivel(seat=2)

    assert minha["R"] == 2 and minha["U"] == 0
    assert dele["U"] == 2 and dele["R"] == 0
    print(f"OK - minha={minha['R']}R, dele={dele['U']}U")


def test_criatura_enjoada_nao_ataca() -> None:
    """Enjoo de invocação impede ataque — regra básica de Magic."""
    estado = _estado_de_combate()
    podem = [c.carta.nome_en for c in estado.criaturas_que_podem_atacar()]

    assert "Nest Robber" in podem, "Nest Robber devia poder atacar"
    assert "Goblin" not in podem, "Goblin enjoado NÃO pode atacar"
    print(f"OK - podem atacar: {podem}")


def test_criatura_enjoada_pode_bloquear() -> None:
    """Enjoo impede atacar, mas NÃO impede bloquear.

    Confundir as duas coisas é erro clássico de quem está aprendendo Magic —
    e seria erro grave no sistema, porque mudaria a conta de combate.
    """
    estado = GameState(meu_seat=1)
    estado.cartas[1] = _carta(
        1, "Blocker", Zona.CAMPO, 2, ["CardType_Creature"], [], enjoada=True
    )

    podem_bloquear = [c.carta.nome_en for c in estado.criaturas_que_podem_bloquear()]

    assert "Blocker" in podem_bloquear, "Criatura enjoada bloqueia sim"
    print("OK - criatura enjoada bloqueia (só não ataca)")


def test_criatura_virada_nao_bloqueia() -> None:
    """Criatura virada não pode bloquear."""
    estado = GameState(meu_seat=1)
    estado.cartas[1] = _carta(
        1, "Tapped", Zona.CAMPO, 2, ["CardType_Creature"], [], virada=True
    )

    assert estado.criaturas_que_podem_bloquear() == []
    print("OK - criatura virada não bloqueia")


def test_terreno_sem_subtipo_conta_como_incolor() -> None:
    """Terreno sem subtipo básico entra como incolor, mas conta no total.

    Escolha conservadora: melhor subestimar a cor disponível do que sugerir
    uma jogada que o jogador não consegue pagar.
    """
    estado = GameState(meu_seat=1)
    estado.cartas[1] = _carta(1, "Terra Estranha", Zona.CAMPO, 1, ["CardType_Land"], [])

    mana = estado.mana_disponivel()
    assert mana["total"] == 1
    assert mana["incolor"] == 1
    assert sum(mana[c] for c in ("W", "U", "B", "R", "G")) == 0
    print("OK - terreno desconhecido conta como incolor")


# ----------------------------------------------------------------------
# Comportamento do recomendador (sem custo de API)
# ----------------------------------------------------------------------


def test_sem_nada_a_decidir_nao_gasta_api() -> None:
    """Mão vazia e nenhuma criatura apta = nada a recomendar."""

    class ClienteQueExplode:
        def perguntar_json(self, **_k: object) -> dict:
            raise AssertionError("Chamou a IA sem nada pra decidir!")

    recomendador = RecomendadorDeJogada(cliente=ClienteQueExplode())  # type: ignore[arg-type]
    estado = GameState(meu_seat=1, turno=1)

    assert recomendador.recomendar(estado) is None
    print("OK - sem jogadas possíveis, não chama a IA")


def test_cache_por_board_e_nao_por_turno() -> None:
    """Mudou o board = nova recomendação. Mesmo board = cache.

    O turno sozinho não serve de chave: dentro de um turno você baixa
    terreno, joga criatura e ataca — três decisões diferentes.
    """
    chamadas = {"total": 0}

    class ClienteContado:
        def perguntar_json(self, **_k: object) -> dict:
            chamadas["total"] += 1
            return {"summary": "Ataque com tudo", "confidence": 0.7}

    recomendador = RecomendadorDeJogada(cliente=ClienteContado())  # type: ignore[arg-type]
    estado = _estado_de_combate()

    recomendador.recomendar(estado)
    recomendador.recomendar(estado)
    assert chamadas["total"] == 1, "Mesmo board devia usar cache"

    # Agora o board muda: uma criatura entra em campo
    estado.cartas[99] = _carta(99, "Volcanic Dragon", Zona.CAMPO, 1,
                               ["CardType_Creature"], [], poder="4", resistencia="4")
    recomendador.recomendar(estado)
    assert chamadas["total"] == 2, "Board diferente devia gerar nova análise"

    print("OK - cache é por board, não por turno")


def test_prompt_avisa_sobre_criatura_enjoada() -> None:
    """A IA precisa saber quem não pode atacar, senão recomenda o impossível."""
    enviado = {"texto": ""}

    class ClienteEspiao:
        def perguntar_json(self, sistema: str, usuario: str, **_k: object) -> dict:
            enviado["texto"] = usuario
            return {"summary": "x"}

    recomendador = RecomendadorDeJogada(cliente=ClienteEspiao())  # type: ignore[arg-type]
    recomendador.recomendar(_estado_de_combate())

    assert "enjoada" in enviado["texto"], "Prompt não avisou do enjoo de invocação"
    assert "2 terreno" in enviado["texto"], "Prompt não informou a mana disponível"
    print("OK - prompt informa enjoo e mana disponível")


# ----------------------------------------------------------------------
# Teste com API real
# ----------------------------------------------------------------------


def test_ficha_das_cartas_entra_no_prompt() -> None:
    """O texto oficial das cartas tem que chegar à IA.

    Sem isso ela raciocina de memória — foi assim que afirmou que "Nest
    Robber tem menace" (tem ímpeto) e ignorou o voar do Cloudkin Seer.
    """
    enviado = {"texto": ""}

    class ClienteEspiao:
        def perguntar_json(self, sistema: str, usuario: str, **_k: object) -> dict:
            enviado["texto"] = usuario
            return {"summary": "x"}

    recomendador = RecomendadorDeJogada(cliente=ClienteEspiao())  # type: ignore[arg-type]
    recomendador.recomendar(_estado_de_combate())

    texto = enviado["texto"]
    assert "FICHA OFICIAL" in texto, "A ficha das cartas não entrou no prompt"
    assert "Haste" in texto, "Não mandou as keywords reais do Nest Robber"
    assert "Flying" in texto, "Não mandou o voar do Cloudkin Seer"
    assert "NÃO a tem" in texto, "Faltou a instrução de não inventar habilidade"

    # Terreno básico não precisa de ficha — seria ruído
    assert "- Mountain" not in texto, "Gastou espaço com ficha de terreno básico"

    print("OK - ficha oficial no prompt, com Haste e Flying corretos")


def test_prompt_separa_poder_base_de_poder_atual() -> None:
    """A ficha traz o poder BASE; o board traz o ATUAL. Não podem se misturar.

    Erro real de 18/07/2026, numa partida do jogador: o Soulblade Djinn estava
    5/3 no board (base impressa 4/3, com um buff). A IA anunciou "6/4" —
    inventou um terceiro valor somando as duas fontes.

    Conta de combate errada é o pior tipo de erro aqui: leva a bloquear
    quando não devia, ou a não atacar quando o ataque era letal.
    """
    enviado = {"texto": ""}

    class ClienteEspiao:
        def perguntar_json(self, sistema: str, usuario: str, **_k: object) -> dict:
            enviado["texto"] = usuario
            return {"summary": "x"}

    estado = _estado_de_combate()
    # Soulblade Djinn: base 4/3 no Scryfall, mas 5/3 em campo (buffado)
    estado.cartas[50] = _carta(
        50, "Soulblade Djinn", Zona.CAMPO, 2, ["CardType_Creature"], [],
        poder="5", resistencia="3",
    )

    recomendador = RecomendadorDeJogada(cliente=ClienteEspiao())  # type: ignore[arg-type]
    recomendador.recomendar(estado)

    texto = enviado["texto"]

    assert "ATUAL 5/3" in texto, "O board precisa marcar o valor como ATUAL"
    assert "base impressa" in texto, "A ficha precisa marcar o valor como BASE"
    assert "Nunca some os dois" in texto, "Faltou a instrução de não somar"

    print("OK - prompt separa poder base (ficha) de poder atual (board)")


def test_texto_de_carta_vem_do_cache_na_segunda_vez() -> None:
    """Buscar a mesma carta duas vezes não pode ir à rede duas vezes."""
    from src.services.scryfall_service import BancoDeTextos

    with BancoDeTextos() as banco:
        primeira = banco.buscar("Nest Robber")
        buscas_apos_primeira = banco.buscas_na_rede
        segunda = banco.buscar("Nest Robber")

        if primeira is None:
            pytest.skip("Sem rede e sem cache pra 'Nest Robber'")

        assert banco.buscas_na_rede == buscas_apos_primeira, "Foi à rede de novo"
        assert segunda is not None
        assert primeira.nome == segunda.nome

        # A prova de que o texto está certo
        assert "Haste" in primeira.keywords, (
            f"Nest Robber devia ter Haste. Keywords: {primeira.keywords}"
        )
        assert "Menace" not in primeira.keywords, "Nest Robber NÃO tem menace"

        print(f"OK - {primeira.resumo()} | keywords={primeira.keywords}")
        print(f"     {banco.total_em_cache()} cartas em cache local")


def test_offline_nao_vai_a_rede() -> None:
    """Modo offline responde só o que já está em cache, sem travar."""
    from src.services.scryfall_service import BancoDeTextos

    with BancoDeTextos(offline=True) as banco:
        banco.buscar("Carta Que Nao Existe Em Lugar Nenhum 12345")
        assert banco.buscas_na_rede == 0, "Foi à rede em modo offline"
    print("OK - modo offline não toca na rede")


@precisa_de_api
def test_recomendacao_real_respeita_as_regras() -> None:
    """A IA recomenda algo jogável e respeita as regras do jogo.

    O board de teste tem uma armadilha: o Goblin está enjoado. Se a IA
    recomendar atacar com ele, ela não leu o estado direito.
    """
    recomendador = RecomendadorDeJogada()
    rec = recomendador.recomendar(_estado_de_combate(), formato="draft")

    assert rec is not None

    print(f"\n   Resumo:     {rec.resumo}")
    print(f"   Confiança:  {rec.confianca:.0%}")
    for jogada in rec.sequencia[:4]:
        print(f"   {jogada.prioridade}. {jogada.acao}")
        print(f"      motivo: {jogada.motivo[:120]}")
        if jogada.risco:
            print(f"      risco:  {jogada.risco[:120]}")
    print(f"   Atacar?     {rec.atacar} com {rec.com_quais_atacar}")
    print(f"      {rec.motivo_do_ataque[:160]}")
    print(f"   Segurar mana? {rec.segurar_mana} — {rec.motivo_da_mana[:120]}")
    if rec.alternativas_descartadas:
        print(f"   Descartou:  {rec.alternativas_descartadas[0][:150]}")

    # A regra que não pode ser violada: Goblin enjoado não ataca
    assert "Goblin" not in rec.com_quais_atacar, (
        "A IA recomendou atacar com criatura enjoada — leu o estado errado"
    )

    # Recomendou pelo menos alguma coisa
    assert rec.resumo, "Recomendação sem resumo"

    # A REGRESSÃO QUE ESTE TESTE EXISTE PRA PEGAR:
    # antes da ficha oficial das cartas, a IA afirmou que "Nest Robber tem
    # menace". Ele tem ímpeto. Se a palavra menace reaparecer no raciocínio,
    # a ancoragem no texto real parou de funcionar.
    tudo_que_ela_disse = " ".join(
        [
            rec.resumo,
            rec.motivo_do_ataque,
            rec.motivo_da_mana,
            *(j.motivo for j in rec.sequencia),
            *(j.risco for j in rec.sequencia),
            *rec.alternativas_descartadas,
        ]
    ).lower()

    assert "menace" not in tudo_que_ela_disse, (
        "A IA voltou a inventar 'menace' no Nest Robber — a ficha oficial "
        "das cartas não está ancorando o raciocínio"
    )

    print(f"\n   {recomendador.cliente.resumo_de_gasto()}")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
