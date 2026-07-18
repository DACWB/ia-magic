"""Testes do Dia 3: o leitor de log do Arena funciona?

Estes testes rodam contra o Player.log REAL da sua máquina. Se você ainda não
jogou nenhuma partida com "Registros detalhados" ligado, eles são pulados em
vez de falhar — porque a ausência de partida não é um bug do código.

Rodar:
    venv\\Scripts\\python.exe -m pytest tests/test_day3.py -v -s
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.game_state import Carta, Zona  # noqa: E402
from src.services.arena_card_db import BancoDeCartasArena  # noqa: E402
from src.services.arena_log_service import (  # noqa: E402
    LeitorDeLogArena,
    extrair_objetos_json,
)
from src.services.arena_paths import (  # noqa: E402
    ArenaNaoEncontrado,
    caminho_banco_de_cartas,
    caminho_do_log,
    pasta_de_instalacao,
)


def _arena_disponivel() -> bool:
    """Diz se dá pra rodar os testes que dependem do Arena instalado."""
    try:
        caminho_do_log()
        caminho_banco_de_cartas()
        return True
    except (ArenaNaoEncontrado, OSError):
        return False


precisa_do_arena = pytest.mark.skipif(
    not _arena_disponivel(),
    reason="MTG Arena não encontrado nesta máquina",
)


# ----------------------------------------------------------------------
# Testes que NÃO dependem do Arena (rodam em qualquer máquina)
# ----------------------------------------------------------------------


def test_extrair_json_simples() -> None:
    """O extrator acha um JSON no meio de texto solto do log."""
    texto = 'lixo da unity {"a": 1, "b": {"c": 2}} mais lixo'
    objetos = list(extrair_objetos_json(texto))

    assert len(objetos) == 1
    assert objetos[0]["b"]["c"] == 2
    print("OK - JSON extraído do meio do texto")


def test_extrair_json_com_chaves_dentro_de_string() -> None:
    """Chaves dentro de string NÃO podem bagunçar a contagem.

    Este é o caso que quebra parsers ingênuos: custo de mana em Magic é
    escrito com chaves ('{2}{R}{R}'), e isso aparece o tempo todo no log.
    """
    texto = '{"custo": "{2}{R}{R}", "nome": "Choque"}'
    objetos = list(extrair_objetos_json(texto))

    assert len(objetos) == 1, "As chaves do custo de mana quebraram o parser"
    assert objetos[0]["custo"] == "{2}{R}{R}"
    assert objetos[0]["nome"] == "Choque"
    print("OK - custo de mana {2}{R}{R} não quebrou o parser")


def test_extrair_json_com_aspas_escapadas() -> None:
    """Aspas escapadas dentro de string não podem bagunçar a contagem."""
    texto = r'{"texto": "ele disse \"opa\" e saiu", "n": 1}'
    objetos = list(extrair_objetos_json(texto))

    assert len(objetos) == 1
    assert objetos[0]["n"] == 1
    print("OK - aspas escapadas tratadas")


def test_extrair_ignora_json_truncado() -> None:
    """Bloco cortado no meio (log sendo escrito) não derruba o parser."""
    texto = '{"ok": 1} {"cortado": [1, 2'
    objetos = list(extrair_objetos_json(texto))

    assert len(objetos) == 1
    assert objetos[0]["ok"] == 1
    print("OK - JSON truncado ignorado sem crash")


def test_jogos_sao_separados() -> None:
    """Dois jogos na mesma sessão NÃO podem virar um estado só.

    Este teste nasceu de um bug real. Numa sessão com dois jogos, os assentos
    trocaram de lado: o deck vermelho estava no assento 1 no primeiro jogo e
    no assento 2 no segundo. O parser fundia os dois, e as cartas do próprio
    jogador apareciam listadas como sendo do oponente.

    O sinal que separa os jogos é a mensagem `GameStateType_Full`.
    """

    class BancoFalso:
        """Banco de mentira: devolve uma carta pra qualquer grpId."""

        def buscar(self, grp_id: int) -> Carta:
            return Carta(grp_id=grp_id, nome_en=f"Carta{grp_id}")

    leitor = LeitorDeLogArena(
        caminho_log=Path(__file__),  # não será lido; usamos processar() direto
        banco=BancoFalso(),  # type: ignore[arg-type]
    )

    def mensagem(tipo: str, grp: int, seat: int) -> dict:
        return {
            "greToClientEvent": {
                "greToClientMessages": [
                    {
                        "gameStateMessage": {
                            "type": tipo,
                            "zones": [
                                {"zoneId": 1, "type": "ZoneType_Battlefield",
                                 "ownerSeatId": seat}
                            ],
                            "gameObjects": [
                                {"instanceId": 10, "grpId": grp, "zoneId": 1,
                                 "ownerSeatId": seat, "controllerSeatId": seat}
                            ],
                        }
                    }
                ]
            }
        }

    # Jogo 1: carta 111 do assento 1
    leitor.processar(mensagem("GameStateType_Full", 111, 1))
    assert leitor.estado.numero_do_jogo == 1
    assert len(leitor.estado.cartas) == 1

    # Jogo 2 começa: outra carta, e o assento trocou
    leitor.processar(mensagem("GameStateType_Full", 222, 2))

    assert leitor.estado.numero_do_jogo == 2, "Não contou o jogo novo"
    assert len(leitor.jogos_anteriores) == 1, "Não arquivou o jogo anterior"

    grps_atuais = {c.carta.grp_id for c in leitor.estado.cartas.values()}
    assert grps_atuais == {222}, (
        f"Carta do jogo anterior vazou pro jogo atual: {grps_atuais}"
    )

    grps_antigos = {c.carta.grp_id for c in leitor.jogos_anteriores[0].cartas.values()}
    assert grps_antigos == {111}, "Jogo arquivado ficou com dados errados"

    print("OK - jogos separados corretamente (o bug dos assentos trocados)")


def test_diff_nao_apaga_o_turno() -> None:
    """Mensagem incremental sem `turnNumber` não pode zerar o turno.

    Caso real do log: veio `{"activePlayer": 2, "decisionPlayer": 2}`, sem o
    número do turno. Um parser que sobrescreve em vez de acumular perde o
    turno nessa hora.
    """

    class BancoFalso:
        def buscar(self, grp_id: int) -> Carta | None:
            return None

    leitor = LeitorDeLogArena(
        caminho_log=Path(__file__),
        banco=BancoFalso(),  # type: ignore[arg-type]
    )

    def com_turno(turno_info: dict) -> dict:
        return {"greToClientEvent": {"greToClientMessages": [
            {"gameStateMessage": {"type": "GameStateType_Diff",
                                  "turnInfo": turno_info}}]}}

    leitor.processar(com_turno({"turnNumber": 7, "phase": "Phase_Main1"}))
    assert leitor.estado.turno == 7

    # Agora um diff que fala só de quem tem prioridade
    leitor.processar(com_turno({"activePlayer": 2, "decisionPlayer": 2}))

    assert leitor.estado.turno == 7, "O turno foi perdido no diff"
    assert leitor.estado.fase == "Phase_Main1", "A fase foi perdida no diff"
    assert leitor.estado.jogador_ativo == 2
    print("OK - diff incremental preserva turno e fase")


# ----------------------------------------------------------------------
# Testes que dependem do Arena instalado
# ----------------------------------------------------------------------


@precisa_do_arena
def test_localiza_arena() -> None:
    """Encontra log, instalação e banco de cartas."""
    log = caminho_do_log()
    instalacao = pasta_de_instalacao()
    banco = caminho_banco_de_cartas()

    assert log.exists()
    assert (instalacao / "MTGA_Data").exists()
    assert banco.stat().st_size > 10_000_000, "Banco de cartas pequeno demais"

    print(f"OK - log:        {log}")
    print(f"     instalação: {instalacao}")
    print(f"     banco:      {banco.name}")


@precisa_do_arena
def test_banco_de_cartas_traduz() -> None:
    """O banco do Arena resolve grpId em nome nos dois idiomas."""
    with BancoDeCartasArena() as banco:
        assert banco.total_de_cartas() > 20_000, "Poucas cartas no banco"

        # 75521 = Ogre Battledriver, carta do deck de goblins da partida real
        carta = banco.buscar(75521)
        assert carta is not None, "grpId 75521 não encontrado"
        assert carta.nome_en == "Ogre Battledriver"
        assert carta.nome_pt, "Faltou o nome em português"

        print(f"OK - {carta.grp_id}: {carta.nome_en} / {carta.nome_pt}")

        # grpId inexistente deve devolver None, não explodir
        assert banco.buscar(1) is None
        print("OK - grpId inválido devolve None")


@precisa_do_arena
def test_cache_do_banco_funciona() -> None:
    """Buscar a mesma carta duas vezes usa o cache."""
    with BancoDeCartasArena() as banco:
        primeira = banco.buscar(75521)
        segunda = banco.buscar(75521)

        assert primeira is segunda, "Cache não devolveu o mesmo objeto"
        print("OK - cache devolve a mesma instância")


@precisa_do_arena
def test_le_partida_do_log() -> None:
    """Lê o log inteiro e monta um GameState coerente.

    Este é O teste do dia: prova que dá pra reconstruir a partida sem OCR.
    """
    leitor = LeitorDeLogArena()
    estado = leitor.ler_arquivo_inteiro()

    if not estado.cartas:
        pytest.skip(
            "Nenhuma partida no log atual. Jogue uma partida com "
            "'Registros detalhados' ligado e rode de novo."
        )

    # Identificou de que lado da mesa eu estou?
    assert estado.meu_seat in (1, 2), f"Assento inválido: {estado.meu_seat}"
    assert estado.seat_oponente != estado.meu_seat

    # Achou cartas de verdade?
    assert len(estado.cartas) > 5, "Cartas de menos — parser não acumulou"

    # Vidas plausíveis.
    #
    # Atenção ao limite inferior: vida NEGATIVA é legítima em Magic. Você
    # perde ao chegar a 0, mas uma mágica de dano direto passa disso — na
    # partida de teste o jogador estava com 3 e tomou um Inescapable Blaze
    # (6 de dano), terminando em -3.
    #
    # A primeira versão deste teste exigia `0 <= vida` e falhou contra o log
    # real. O erro estava no teste, não no parser: eu tinha codificado uma
    # premissa errada sobre as regras do jogo.
    assert -60 <= estado.minha_vida <= 100
    assert -60 <= estado.vida_oponente <= 100

    # Zonas foram resolvidas? Se TODAS ficaram desconhecidas, o mapa de
    # zoneId não foi acumulado — bug clássico deste parser.
    zonas_conhecidas = {
        c.zona for c in estado.cartas.values() if c.zona is not Zona.DESCONHECIDA
    }
    assert zonas_conhecidas, "Nenhuma zona resolvida — acumulação falhou"

    print(f"OK - assento {estado.meu_seat} (oponente: {estado.seat_oponente})")
    print(f"     turno {estado.turno}, vida {estado.minha_vida} x {estado.vida_oponente}")
    print(f"     {len(estado.cartas)} cartas, zonas: {sorted(z.value for z in zonas_conhecidas)}")


@precisa_do_arena
def test_identifica_cartas_do_oponente() -> None:
    """As cartas reveladas do oponente são a base pra identificar o deck."""
    leitor = LeitorDeLogArena()
    estado = leitor.ler_arquivo_inteiro()

    if not estado.cartas:
        pytest.skip("Nenhuma partida no log atual.")

    reveladas = estado.cartas_reveladas_do_oponente()

    # A mão do oponente NUNCA pode vazar pra essa lista — informação oculta
    # continua oculta, igual numa mesa física.
    assert all(c.zona is not Zona.MAO for c in reveladas), (
        "A mão do oponente vazou nas cartas reveladas!"
    )

    nomes = sorted({c.carta.nome_en for c in reveladas})
    print(f"OK - {len(nomes)} cartas reveladas do oponente: {nomes[:10]}")


@precisa_do_arena
def test_leitura_incremental_nao_duplica() -> None:
    """Chamar ler_novidades() sem log novo não muda nada.

    Se duplicasse, a cada segundo o dashboard mostraria cartas repetidas.
    """
    leitor = LeitorDeLogArena()
    estado = leitor.ler_arquivo_inteiro()
    if not estado.cartas:
        pytest.skip("Nenhuma partida no log atual.")

    antes = len(estado.cartas)
    leitor.ler_novidades()
    leitor.ler_novidades()
    depois = len(leitor.estado.cartas)

    assert antes == depois, f"Duplicou cartas: {antes} -> {depois}"
    print(f"OK - leitura incremental estável ({antes} cartas)")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
