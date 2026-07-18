"""Testes do painel web e do motor compartilhado (Copiloto).

Rodar:
    venv\\Scripts\\python.exe -m pytest tests/test_day8.py -v -s
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


def _estado(meu_turno: bool = True) -> GameState:
    """Board simples: meu turno, carta na mão, terreno desvirado."""
    estado = GameState(meu_seat=1, turno=5, numero_do_jogo=2, etapa="Step_Main1")
    estado.jogador_ativo = 1 if meu_turno else 2
    estado.jogadores[1] = Jogador(seat=1, team_id=1, vida=17)
    estado.jogadores[2] = Jogador(seat=2, team_id=2, vida=13)

    def carta(i, nome, zona, seat, **kw):
        return CartaEmJogo(
            instance_id=i,
            carta=Carta(grp_id=i, nome_en=nome, nome_pt=f"{nome} PT"),
            zona=zona, dono_seat=seat, controlador_seat=seat, **kw,
        )

    for c in [
        carta(1, "Shock", Zona.MAO, 1),
        carta(2, "Mountain", Zona.CAMPO, 1, tipos=["CardType_Land"],
              subtipos=["SubType_Mountain"]),
        carta(3, "Cloudkin Seer", Zona.CAMPO, 2, tipos=["CardType_Creature"],
              poder_atual="2", resistencia_atual="1"),
    ]:
        estado.cartas[c.instance_id] = c
    return estado


# ----------------------------------------------------------------------
# Motor compartilhado
# ----------------------------------------------------------------------


@precisa_do_arena
def test_copiloto_so_calcula_no_meu_turno() -> None:
    """No turno do oponente você raramente decide — não vale gastar."""
    from src.services.copiloto import Copiloto

    copiloto = Copiloto()

    copiloto.estado = _estado(meu_turno=True)
    assert copiloto.vale_a_pena_calcular()

    copiloto.estado = _estado(meu_turno=False)
    assert not copiloto.vale_a_pena_calcular()

    print("OK - copiloto respeita de quem é o turno")


@precisa_do_arena
def test_copiloto_nao_cria_ia_ao_abrir() -> None:
    """Abrir o copiloto não pode gastar nada nem exigir internet."""
    from src.services.copiloto import Copiloto

    copiloto = Copiloto()

    assert copiloto._identificador is None
    assert copiloto._recomendador is None
    assert copiloto.gasto() == {
        "chamadas": 0, "tokens_entrada": 0, "tokens_saida": 0
    }
    print("OK - copiloto abre sem tocar na IA")


# ----------------------------------------------------------------------
# Serialização pro navegador
# ----------------------------------------------------------------------


@precisa_do_arena
def test_pacote_web_tem_o_que_a_tela_precisa() -> None:
    """O JSON enviado ao navegador precisa conter tudo que a página desenha."""
    import json

    from src.services.copiloto import Copiloto
    from src.web.server import _estado_para_json

    copiloto = Copiloto()
    copiloto.estado = _estado()

    pacote = _estado_para_json(copiloto.estado, copiloto)

    for chave in (
        "jogo", "turno", "fase", "meu_turno", "minha_vida", "vida_oponente",
        "mana", "minha_mao", "meu_campo", "campo_oponente", "conselho",
        "oponente", "gasto", "automatico", "calculando", "erro",
    ):
        assert chave in pacote, f"Falta '{chave}' no pacote"

    # Tem que virar JSON de verdade, com acento e tudo
    texto = json.dumps(pacote, ensure_ascii=False)
    assert "Shock PT" in texto, "Não usou o nome em português"

    print(f"OK - pacote completo ({len(texto)} bytes)")


@precisa_do_arena
def test_pacote_nunca_vaza_a_chave_da_api() -> None:
    """A chave da Anthropic NUNCA pode sair no JSON pro navegador.

    O servidor escuta em 0.0.0.0 pra ser acessível do celular, ou seja, fica
    visível pra qualquer aparelho na rede. Vazar a chave aí seria grave.
    """
    import json

    from src.services.copiloto import Copiloto
    from src.utils.config import config
    from src.web.server import _estado_para_json

    copiloto = Copiloto()
    copiloto.estado = _estado()
    texto = json.dumps(_estado_para_json(copiloto.estado, copiloto))

    assert "sk-ant" not in texto, "VAZOU a chave da API no pacote web!"
    if config.anthropic_api_key:
        assert config.anthropic_api_key not in texto, "VAZOU a chave!"

    print("OK - chave da API não vaza pro navegador")


@precisa_do_arena
def test_descobre_ip_da_rede_local() -> None:
    """Precisa achar o IP certo pra montar o link do celular."""
    from src.web.server import descobrir_ip_local

    ip = descobrir_ip_local()
    partes = ip.split(".")

    assert len(partes) == 4, f"IP inválido: {ip}"
    assert all(p.isdigit() for p in partes), f"IP inválido: {ip}"
    print(f"OK - IP local: {ip}")


@precisa_do_arena
def test_pagina_html_existe_e_carrega() -> None:
    """A página precisa existir e ter os elementos que o script manipula."""
    from src.web.server import PASTA_ESTATICA

    arquivo = PASTA_ESTATICA / "index.html"
    assert arquivo.exists(), f"Página não encontrada em {arquivo}"

    html = arquivo.read_text(encoding="utf-8")

    # Todo id usado pelo JavaScript precisa existir no HTML, senão a tela
    # quebra em silêncio no meio de uma partida.
    for elemento in (
        "conselho-acao", "conselho-motivo", "conselho-alerta", "conselho-tempo",
        "conselho-combate", "conselho-vazio", "conselho-conteudo",
        "lista-mao", "lista-campo", "lista-dele", "lista-cemiterio",
        "c-jogo", "c-turno", "c-vidas", "c-mana", "c-fase",
        "rodape", "desconectado", "oponente-conteudo", "completa-conteudo",
        "b-conselho", "b-oponente", "b-completa", "b-auto",
    ):
        assert f'id="{elemento}"' in html, f"Falta o elemento #{elemento}"

    assert "viewport" in html, "Sem meta viewport — quebraria no celular"
    assert "WebSocket" in html
    print(f"OK - página completa ({len(html)} caracteres)")


@precisa_do_arena
def test_app_web_tem_as_rotas() -> None:
    """As rotas da página e do WebSocket existem."""
    from src.web.server import app

    caminhos = {rota.path for rota in app.routes}
    assert "/" in caminhos, "Falta a rota da página"
    assert "/ws" in caminhos, "Falta a rota do WebSocket"
    print(f"OK - rotas: {sorted(c for c in caminhos if not c.startswith('/openapi'))}")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
