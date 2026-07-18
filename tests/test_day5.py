"""Testes do Dia 5: a camada de IA.

Os testes que gastam API são pulados sem a chave configurada.

Rodar:
    venv\\Scripts\\python.exe -m pytest tests/test_day5.py -v -s
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.models.game_state import Carta, CartaEmJogo, GameState, Jogador, Zona  # noqa: E402
from src.services.claude_client import (  # noqa: E402
    ClienteClaude,
    RespostaInvalida,
    carregar_prompt,
)
from src.services.deck_identifier import IdentificadorDeDeck  # noqa: E402
from src.utils.config import config  # noqa: E402
from src.utils.json_solto import extrair_objetos_json, maior_objeto_json  # noqa: E402

precisa_de_api = pytest.mark.skipif(
    not config.chave_api_configurada(),
    reason="Sem chave de API no .env",
)


def _estado_de_exemplo() -> GameState:
    """Monta um estado com um oponente mono-azul de voadores.

    Baseado numa partida real do jogador contra o deck azul do Desafio de
    Cores. Serve de caso conhecido: se a IA não identificar "azul tempo /
    voadores" aqui, tem algo errado.
    """
    estado = GameState(meu_seat=1, turno=6, fase="Phase_Main1")
    estado.jogadores[1] = Jogador(seat=1, team_id=1, vida=14)
    estado.jogadores[2] = Jogador(seat=2, team_id=2, vida=20)

    cartas_do_oponente = [
        (301, "Island", Zona.CAMPO),
        (302, "Island", Zona.CAMPO),
        (303, "Island", Zona.CAMPO),
        (304, "Cloudkin Seer", Zona.CAMPO),
        (305, "Warden of Evos Isle", Zona.CAMPO),
        (306, "Riddlemaster Sphinx", Zona.CAMPO),
        (307, "Unsummon", Zona.CEMITERIO),
    ]
    for instancia, nome, zona in cartas_do_oponente:
        estado.cartas[instancia] = CartaEmJogo(
            instance_id=instancia,
            carta=Carta(grp_id=instancia, nome_en=nome, nome_pt=nome),
            zona=zona,
            dono_seat=2,
            controlador_seat=2,
        )

    # Uma carta minha, pra provar que ela NÃO entra na análise do oponente
    estado.cartas[401] = CartaEmJogo(
        instance_id=401,
        carta=Carta(grp_id=401, nome_en="Mountain", nome_pt="Montanha"),
        zona=Zona.CAMPO,
        dono_seat=1,
        controlador_seat=1,
    )
    return estado


# ----------------------------------------------------------------------
# Testes sem custo de API
# ----------------------------------------------------------------------


def test_extrai_json_de_resposta_conversada() -> None:
    """A IA às vezes escreve antes do JSON. Temos que aguentar isso."""
    resposta = 'Claro! Aqui está a análise:\n```json\n{"nome": "Mono Blue"}\n```\nEspero ajudar!'
    dados = maior_objeto_json(resposta)

    assert dados is not None
    assert dados["nome"] == "Mono Blue"
    print("OK - JSON extraído de resposta conversada")


def test_pega_o_maior_json_e_nao_o_primeiro() -> None:
    """Se houver um exemplo pequeno antes, queremos a resposta de verdade."""
    resposta = '{"exemplo": 1} e a resposta real: {"nome": "Azorius", "cores": ["W","U"], "confianca": 0.8}'
    dados = maior_objeto_json(resposta)

    assert dados is not None
    assert dados.get("nome") == "Azorius", "Pegou o exemplo em vez da resposta"
    print("OK - pegou o maior objeto, não o primeiro")


def test_carrega_prompt_do_markdown() -> None:
    """Os prompts vivem em markdown pra serem editáveis sem código."""
    prompt = carregar_prompt("deck-identifier")

    assert len(prompt) > 100, "Prompt curto demais — leitura falhou?"
    assert "JSON" in prompt.upper()
    print(f"OK - prompt carregado ({len(prompt)} caracteres)")


def test_prompt_inexistente_da_erro_claro() -> None:
    """Errar o nome do prompt não pode virar um erro críptico."""
    with pytest.raises(FileNotFoundError, match="não encontrado"):
        carregar_prompt("prompt-que-nao-existe")
    print("OK - erro claro pra prompt inexistente")


def test_sem_cartas_nao_gasta_api() -> None:
    """Se o oponente não mostrou nada, não faz sentido perguntar à IA.

    Parece detalhe, mas é dinheiro: sem essa guarda, o sistema dispararia uma
    chamada a cada atualização de tela durante o mulligan, quando ainda não
    há absolutamente nada pra analisar.
    """

    class ClienteQueExplode:
        """Se a IA for chamada, o teste falha."""

        def perguntar_json(self, **_kwargs: object) -> dict:
            raise AssertionError("Chamou a IA sem cartas reveladas!")

    identificador = IdentificadorDeDeck(cliente=ClienteQueExplode())  # type: ignore[arg-type]
    estado = GameState(meu_seat=1, turno=1)

    analise = identificador.identificar(estado)

    assert analise.principal.nome == ""
    assert analise.cartas_analisadas == []
    print("OK - sem cartas reveladas, não chama a IA")


def test_cache_evita_chamada_repetida() -> None:
    """Mesmas cartas visíveis = mesma análise, sem pagar de novo.

    Durante um turno o estado muda muitas vezes (mana virando, criatura
    atacando) sem o oponente revelar nada novo. Sem cache, cada mudancinha
    custaria uma chamada de IA.
    """
    chamadas = {"total": 0}

    class ClienteContado:
        def perguntar_json(self, **_kwargs: object) -> dict:
            chamadas["total"] += 1
            return {"identified_deck": {"name": "Mono Blue Tempo",
                                        "confidence": 0.8}}

    identificador = IdentificadorDeDeck(cliente=ClienteContado())  # type: ignore[arg-type]
    estado = _estado_de_exemplo()

    primeira = identificador.identificar(estado)
    segunda = identificador.identificar(estado)

    assert chamadas["total"] == 1, f"Chamou a IA {chamadas['total']}x"
    assert primeira.principal.nome == segunda.principal.nome
    print("OK - cache evitou chamada repetida")


def test_mao_do_oponente_nunca_entra_na_analise() -> None:
    """Informação oculta continua oculta.

    Em partidas contra a máquina o log revela a mão dos dois lados. O sistema
    é assistente de raciocínio, não raio-x: analisa só o que qualquer jogador
    atento veria numa mesa física.
    """
    enviado = {"texto": ""}

    class ClienteEspiao:
        def perguntar_json(self, sistema: str, usuario: str, **_k: object) -> dict:
            enviado["texto"] = usuario
            return {"identified_deck": {"name": "X", "confidence": 0.5}}

    estado = _estado_de_exemplo()
    # Carta secreta na mão do oponente
    estado.cartas[999] = CartaEmJogo(
        instance_id=999,
        carta=Carta(grp_id=999, nome_en="Counterspell", nome_pt="Contramágica"),
        zona=Zona.MAO,
        dono_seat=2,
        controlador_seat=2,
    )

    identificador = IdentificadorDeDeck(cliente=ClienteEspiao())  # type: ignore[arg-type]
    identificador.identificar(estado)

    assert "Counterspell" not in enviado["texto"], (
        "A mão do oponente vazou pro prompt da IA!"
    )
    print("OK - mão do oponente não vazou pro prompt")


def test_prompt_usa_nomes_em_ingles() -> None:
    """Pra IA vai inglês, mesmo o jogador vendo tudo em português."""
    enviado = {"texto": ""}

    class ClienteEspiao:
        def perguntar_json(self, sistema: str, usuario: str, **_k: object) -> dict:
            enviado["texto"] = usuario
            return {"identified_deck": {"name": "X", "confidence": 0.5}}

    identificador = IdentificadorDeDeck(cliente=ClienteEspiao())  # type: ignore[arg-type]
    identificador.identificar(_estado_de_exemplo())

    assert "Riddlemaster Sphinx" in enviado["texto"]
    assert "Esfinge" not in enviado["texto"], "Mandou português pra IA"
    print("OK - prompt em inglês, interface em português")


# ----------------------------------------------------------------------
# Testes que gastam API (poucos tokens, mas gastam)
# ----------------------------------------------------------------------


@precisa_de_api
def test_cliente_devolve_json_de_verdade() -> None:
    """Chamada real: a IA obedece o pedido de JSON?"""
    cliente = ClienteClaude()
    dados = cliente.perguntar_json(
        sistema="Você responde apenas com JSON válido, sem texto ao redor.",
        usuario='Devolva exatamente: {"status": "ok", "numero": 42}',
        max_tokens=2000,
    )

    assert dados.get("status") == "ok"
    assert dados.get("numero") == 42
    print(f"OK - {cliente.resumo_de_gasto()}")


@precisa_de_api
def test_identifica_deck_azul_conhecido() -> None:
    """O teste de verdade: a IA reconhece um deck que sabemos qual é.

    O oponente mostrou 3 Ilhas, Cloudkin Seer, Warden of Evos Isle,
    Riddlemaster Sphinx e Unsummon. Qualquer jogador de Magic diria
    "azul, voadores, tempo". A IA tem que chegar lá também.
    """
    identificador = IdentificadorDeDeck()
    analise = identificador.identificar(_estado_de_exemplo(), formato="draft")

    print(f"\n   Deck:       {analise.principal.nome}")
    print(f"   Confiança:  {analise.principal.confianca:.0%}")
    print(f"   Arquétipo:  {analise.principal.arquetipo}")
    print(f"   Cores:      {analise.principal.cores}")
    print(f"   Raciocínio: {analise.principal.raciocinio[:180]}")
    if analise.ameacas:
        print(f"   Ameaças:    {[a.carta for a in analise.ameacas[:3]]}")
    if analise.como_enfrentar:
        print(f"   Conselho:   {analise.como_enfrentar[0][:150]}")

    # Identificou a cor certa?
    assert "U" in analise.principal.cores, (
        f"Não identificou azul. Cores: {analise.principal.cores}"
    )

    # A carta do MEU lado não pode ter influenciado
    assert "Mountain" not in analise.cartas_analisadas

    # Confiança tem que ser um número plausível
    assert 0 <= analise.principal.confianca <= 1

    print(f"\n   {identificador.cliente.resumo_de_gasto()}")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
