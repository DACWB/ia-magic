"""Preparação do terminal do Windows para acentos e emoji.

O problema: o console do Windows historicamente usa a codificação cp1252
(Latin-1 estendido), que NÃO tem emoji. Qualquer `print("🎴")` explode com
UnicodeEncodeError antes mesmo de aparecer na tela.

Como o dashboard do Dia 6 é feito de emoji e acentuação, isso não é detalhe
estético — é o que decide se o programa roda ou quebra. Resolvemos uma vez
aqui, e todo o resto do projeto assume que o terminal aguenta UTF-8.
"""

import sys


def preparar_terminal() -> None:
    """Força a saída do terminal para UTF-8, se necessário.

    Deve ser chamada UMA vez, no começo do programa, antes de qualquer
    impressão. Chamar de novo é inofensivo.

    Em terminais que já são UTF-8 (Linux, macOS, Windows Terminal moderno)
    a função não faz efeito nenhum — é segura em qualquer plataforma.
    """
    for fluxo in (sys.stdout, sys.stderr):
        # `reconfigure` existe em qualquer TextIOWrapper do Python 3.7+, mas
        # o fluxo pode ter sido substituído (pytest, redirecionamento, etc.),
        # então checamos antes de chamar.
        reconfigurar = getattr(fluxo, "reconfigure", None)
        if reconfigurar is None:
            continue
        try:
            reconfigurar(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # Fluxo já fechado ou não reconfigurável: seguimos sem travar.
            # `errors="replace"` acima garante que, no pior caso, um emoji
            # vira "?" em vez de derrubar o programa.
            pass
