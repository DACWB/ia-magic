"""Descobre onde o MTG Arena guarda o log e o banco de cartas.

Por que isso merece um módulo? Porque o Arena pode estar instalado em vários
lugares (Steam, Epic, instalador da Wizards, disco D:...) e o caminho muda de
PC pra PC. Se a gente cravar `D:\\Steam\\...` no código, funciona na máquina do
o jogador e quebra na de qualquer aluno que tentar rodar.

O truque mais bonito daqui: o **próprio log** informa onde o jogo está
instalado. A primeira linha que a Unity escreve é sempre:

    Mono path[0] = 'D:/Steam/steamapps/common/MTGA/MTGA_Data/Managed'

Ou seja: achando o log (que fica sempre no mesmo lugar), achamos a instalação
de brinde — sem chutar caminhos nem varrer o disco inteiro.
"""

import os
import re
from pathlib import Path

# O log fica SEMPRE aqui, em qualquer instalação do Windows.
# (LocalLow é a pasta que a Unity usa; não confundir com Local ou Roaming.)
PASTA_LOG_PADRAO = (
    Path(os.environ.get("USERPROFILE", Path.home()))
    / "AppData"
    / "LocalLow"
    / "Wizards Of The Coast"
    / "MTGA"
)

# Caminhos de instalação mais comuns, usados só se o log não revelar o certo
CAMINHOS_INSTALACAO_COMUNS = [
    Path(r"C:\Program Files\Wizards of the Coast\MTGA"),
    Path(r"C:\Program Files (x86)\Wizards of the Coast\MTGA"),
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\MTGA"),
    Path(r"D:\Steam\steamapps\common\MTGA"),
]


class ArenaNaoEncontrado(RuntimeError):
    """O MTG Arena não foi localizado no computador."""


def caminho_do_log() -> Path:
    """Devolve o caminho do Player.log (log da sessão atual).

    Returns:
        Caminho do arquivo Player.log.

    Raises:
        ArenaNaoEncontrado: Se o arquivo não existir.
    """
    log = PASTA_LOG_PADRAO / "Player.log"
    if not log.exists():
        raise ArenaNaoEncontrado(
            f"Player.log não encontrado em {log}.\n"
            "Abra o MTG Arena pelo menos uma vez e confirme que a opção "
            "'Registros detalhados (suporte de plugin)' está ligada em "
            "Ajustes → Conta."
        )
    return log


def caminho_do_log_anterior() -> Path | None:
    """Devolve o Player-prev.log (log da sessão anterior), se existir.

    Útil pra analisar partidas de ontem sem depender do jogo estar aberto.

    Returns:
        Caminho do Player-prev.log, ou None se não existir.
    """
    anterior = PASTA_LOG_PADRAO / "Player-prev.log"
    return anterior if anterior.exists() else None


def pasta_de_instalacao() -> Path:
    """Descobre a pasta onde o MTG Arena está instalado.

    Estratégia, em ordem:
      1. Lê a linha `Mono path[0]` do próprio log (mais confiável)
      2. Testa os caminhos de instalação mais comuns

    Returns:
        Pasta raiz da instalação (a que contém MTGA_Data).

    Raises:
        ArenaNaoEncontrado: Se nenhuma estratégia funcionar.
    """
    # Estratégia 1: perguntar pro log
    try:
        log = caminho_do_log()
    except ArenaNaoEncontrado:
        log = None

    if log is not None:
        # Só as primeiras linhas bastam — `Mono path` é sempre a linha 1
        with log.open("r", encoding="utf-8", errors="replace") as arquivo:
            cabecalho = "".join(next(arquivo, "") for _ in range(5))

        achado = re.search(r"Mono path\[0\]\s*=\s*'([^']+)'", cabecalho)
        if achado:
            # O caminho aponta pra .../MTGA_Data/Managed — subimos dois níveis
            managed = Path(achado.group(1))
            raiz = managed.parent.parent
            if (raiz / "MTGA_Data").exists():
                return raiz

    # Estratégia 2: os suspeitos de sempre
    for candidato in CAMINHOS_INSTALACAO_COMUNS:
        if (candidato / "MTGA_Data").exists():
            return candidato

    raise ArenaNaoEncontrado(
        "Não localizei a instalação do MTG Arena.\n"
        "Defina ARENA_INSTALL_PATH no .env apontando pra pasta que contém "
        "MTGA_Data (ex.: D:\\Steam\\steamapps\\common\\MTGA)."
    )


def caminho_banco_de_cartas(instalacao: Path | None = None) -> Path:
    """Localiza o SQLite com as ~26 mil cartas que o Arena instala junto.

    O arquivo tem um hash no nome, que muda a cada atualização do jogo
    (ex.: `Raw_CardDatabase_4ef2ba4d....mtga`), por isso procuramos por padrão
    em vez de nome fixo. Se houver mais de um (sobra de update antigo),
    pegamos o maior — o atual é sempre o mais completo.

    Args:
        instalacao: Pasta de instalação. Se None, descobre sozinha.

    Returns:
        Caminho do arquivo .mtga (que por dentro é um SQLite comum).

    Raises:
        ArenaNaoEncontrado: Se o banco não estiver na instalação.
    """
    raiz = instalacao or pasta_de_instalacao()
    pasta_raw = raiz / "MTGA_Data" / "Downloads" / "Raw"

    candidatos = sorted(
        pasta_raw.glob("Raw_CardDatabase_*.mtga"),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not candidatos:
        raise ArenaNaoEncontrado(
            f"Banco de cartas não encontrado em {pasta_raw}.\n"
            "Abra o Arena e deixe ele terminar de baixar as atualizações."
        )
    return candidatos[0]
