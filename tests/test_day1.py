"""Testes do Dia 1: o ambiente está de pé?

Três perguntas, três testes:
  1. As bibliotecas instalaram?
  2. A configuração (.env) carregou e tem chave de API válida?
  3. A API da Anthropic responde de verdade?

Rodar de duas formas:
    venv\\Scripts\\python.exe -m pytest tests/test_day1.py -v   (modo pytest)
    venv\\Scripts\\python.exe tests/test_day1.py                (modo script)

O teste 3 é o único que gasta dinheiro — e gasta desprezível (~10 tokens).
Ele é pulado automaticamente se a chave da API ainda não estiver no .env,
pra você conseguir validar os passos 1 e 2 antes de ter a chave em mãos.
"""

import sys
from pathlib import Path

import pytest

# Garante que `import src...` funcione mesmo rodando o arquivo direto
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.config import config  # noqa: E402


def test_dependencias_instaladas() -> None:
    """Confere que todas as bibliotecas do requirements.txt importam.

    Se alguma falhar aqui, o problema é instalação — não código nosso.
    """
    import anthropic  # noqa: F401
    import cv2  # noqa: F401  (opencv-python)
    import httpx  # noqa: F401
    import obswebsocket  # noqa: F401
    import pandas  # noqa: F401
    import pydantic  # noqa: F401
    import rich  # noqa: F401
    import sqlalchemy  # noqa: F401

    print("OK - todas as bibliotecas importaram")


def test_configuracao_carregada() -> None:
    """Confere que o .env foi lido e os valores chegaram na config.

    Não testa a chave da API aqui — isso é o próximo teste. Aqui só validamos
    que o mecanismo de configuração funciona.
    """
    assert config.obs_port == 4455, "Porta do OBS deveria ser 4455"
    assert config.capture_width > 0, "Largura de captura inválida"
    assert config.claude_model_primary, "Modelo principal não configurado"

    print(f"OK - config carregada (modelo: {config.claude_model_primary})")


def test_chave_api_presente() -> None:
    """Confere que a ANTHROPIC_API_KEY foi preenchida no .env.

    Falha de propósito enquanto a chave for o placeholder do .env.example.
    """
    assert config.chave_api_configurada(), (
        "Chave da Anthropic ausente ou ainda no valor de exemplo. "
        "Edite o arquivo .env e coloque sua chave real em ANTHROPIC_API_KEY."
    )

    print("OK - chave da API presente")


@pytest.mark.skipif(
    not config.chave_api_configurada(),
    reason="Sem chave de API no .env — pulando chamada real",
)
def test_claude_api_responde() -> None:
    """Faz uma chamada mínima e real à API pra provar que tudo conecta.

    Usa max_tokens baixo de propósito: o objetivo é validar a conexão e a
    autenticação, não gerar texto.
    """
    from anthropic import Anthropic

    cliente = Anthropic(api_key=config.anthropic_api_key)

    resposta = cliente.messages.create(
        model=config.claude_model_primary,
        max_tokens=20,
        messages=[{"role": "user", "content": "Responda apenas: pong"}],
    )

    assert resposta.content, "A API respondeu, mas sem conteúdo"
    texto = resposta.content[0].text

    print(f"OK - Claude respondeu: {texto.strip()!r}")
    print(f"     tokens: {resposta.usage.input_tokens} entrada / "
          f"{resposta.usage.output_tokens} saida")


if __name__ == "__main__":
    # Modo script: roda os testes na ordem e para no primeiro erro,
    # com mensagens amigáveis em vez de traceback do pytest.
    testes = [
        ("Dependencias instaladas", test_dependencias_instaladas),
        ("Configuracao carregada", test_configuracao_carregada),
        ("Chave da API presente", test_chave_api_presente),
        ("Claude API responde", test_claude_api_responde),
    ]

    for nome, funcao in testes:
        print(f"\n>> {nome}")
        try:
            funcao()
        except AssertionError as erro:
            print(f"   FALHOU: {erro}")
            sys.exit(1)
        except Exception as erro:  # erro inesperado (rede, auth, etc.)
            print(f"   ERRO INESPERADO: {type(erro).__name__}: {erro}")
            sys.exit(1)

    print("\n=== DIA 1 COMPLETO ===")
