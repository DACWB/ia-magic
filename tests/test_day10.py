"""Testes do identificador de cartas por nome escrito.

Rodar:
    venv\\Scripts\\python.exe -m pytest tests/test_day10.py -v -s
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.arena_paths import ArenaNaoEncontrado, caminho_banco_de_cartas  # noqa: E402
from src.services.identificador_de_cartas import (  # noqa: E402
    IdentificadorDeCartas,
    normalizar,
)


def _arena_disponivel() -> bool:
    try:
        caminho_banco_de_cartas()
        return True
    except (ArenaNaoEncontrado, OSError):
        return False


precisa_do_arena = pytest.mark.skipif(
    not _arena_disponivel(), reason="Banco de cartas do Arena não encontrado"
)


def test_normalizacao_tira_acento_e_pontuacao() -> None:
    """Nome sem acento tem que virar a mesma chave do nome com acento."""
    # A vírgula vira espaço; sem colapsar espaços, as duas chaves diferem e
    # o casamento exato falha em toda carta lendária.
    assert normalizar("Capitão América, Ícone da Liberdade") == normalizar(
        "Capitao America Icone da Liberdade"
    )
    assert normalizar("S.H.I.E.L.D.  Kit") == normalizar("SHIELD Kit").replace(
        "shield", "s h i e l d"
    )
    assert "  " not in normalizar("Nome,  com   espaços"), "Sobrou espaço duplo"
    print("OK - normalização remove acento, pontuação e espaço duplo")


@precisa_do_arena
def test_le_formato_exportado_do_arena() -> None:
    """O export do Arena vem com quantidade, set e número — tudo tem que ser lido."""
    lista = """Deck
4 Triunfo Político (MSH) 12
2 Agente Phil Coulson (MSH) 5
1 Montanha (MSH) 270"""

    with IdentificadorDeCartas() as ident:
        r = ident.ler_lista(lista)

    assert not r.nao_encontradas, f"Não achou: {[l.nome_lido for l in r.nao_encontradas]}"
    assert r.total_de_cartas == 7, f"Contou {r.total_de_cartas} cartas, esperava 7"

    nomes = {l.carta.nome_pt for l in r.encontradas + r.duvidosas if l.carta}
    assert any("Triunfo" in n for n in nomes)
    print(f"OK - export lido: {r.resumo()}")


@precisa_do_arena
def test_aguenta_nome_sem_acento() -> None:
    """Digitado sem acento continua achando a carta certa."""
    with IdentificadorDeCartas() as ident:
        r = ident.ler_lista("2 Capitao America, Icone da Liberdade")

    assert not r.nao_encontradas, "Não achou o nome sem acento"
    linha = (r.encontradas + r.duvidosas)[0]
    assert "Capit" in linha.carta.nome_pt
    print(f"OK - sem acento -> {linha.carta.nome_pt} ({linha.semelhanca:.0%})")


@precisa_do_arena
def test_aguenta_nome_cortado() -> None:
    """OCR corta o fim do nome. O casamento por prefixo salva."""
    with IdentificadorDeCartas() as ident:
        r = ident.ler_lista("1 Agente 13, Sharon")

    encontradas = r.encontradas + r.duvidosas
    assert encontradas, "Não achou o nome cortado"
    assert "Sharon" in encontradas[0].carta.nome_pt
    print(f"OK - cortado -> {encontradas[0].carta.nome_pt}")


@precisa_do_arena
def test_aguenta_letra_trocada() -> None:
    """Erro de digitação de uma letra ainda casa."""
    with IdentificadorDeCartas() as ident:
        r = ident.ler_lista("3 Triunfo Politco")  # falta o 'i'

    encontradas = r.encontradas + r.duvidosas
    assert encontradas, "Não achou com letra faltando"
    print(f"OK - letra trocada -> {encontradas[0].carta.nome_pt} "
          f"({encontradas[0].semelhanca:.0%})")


@precisa_do_arena
def test_nome_inventado_nao_casa() -> None:
    """Melhor dizer "não achei" do que devolver a carta errada.

    Se o identificador aceitasse qualquer coisa, uma linha ilegível viraria
    silenciosamente uma carta aleatória no deck — e ninguém notaria.
    """
    with IdentificadorDeCartas() as ident:
        r = ident.ler_lista("4 Xyzabc Qwerty Naoexiste 99")

    assert r.nao_encontradas, "Aceitou um nome que não existe"
    assert not r.encontradas
    print("OK - nome inventado devolve 'não encontrado'")


@precisa_do_arena
def test_ignora_cabecalhos_do_export() -> None:
    """O export tem "Deck" e "Reserva" como cabeçalho — não são cartas."""
    lista = """Deck
4 Triunfo Político

Reserva
2 Agente Phil Coulson"""

    with IdentificadorDeCartas() as ident:
        r = ident.ler_lista(lista)

    todos = r.encontradas + r.duvidosas + r.nao_encontradas
    assert len(todos) == 2, f"Leu {len(todos)} linhas, esperava 2 cartas"
    print("OK - cabeçalhos ignorados")


@precisa_do_arena
def test_linha_sem_quantidade_assume_uma() -> None:
    """Lista só com nomes: cada linha vale 1 cópia."""
    with IdentificadorDeCartas() as ident:
        r = ident.ler_lista("Triunfo Político\nAgente Phil Coulson")

    assert r.total_de_cartas == 2
    print("OK - sem quantidade assume 1")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
