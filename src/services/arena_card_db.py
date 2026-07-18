"""Leitura do banco de cartas que o MTG Arena instala junto com o jogo.

O Arena traz um SQLite de ~237 MB com 26 mil cartas e os nomes traduzidos em
9 idiomas. Ele é a ponte entre o número que aparece no log (`grpId`) e o nome
humano da carta.

Estrutura relevante do banco:

    Cards                -> GrpId, TitleId, TypeTextId, Power, Toughness, ...
    Localizations_enUS   -> LocId, Formatted, Loc   (Loc = o texto)
    Localizations_ptBR   -> LocId, Formatted, Loc

O `TitleId` da carta é a chave que liga nas tabelas de tradução. Ou seja:

    grpId 75521  ->  TitleId 42955  ->  "Ogre Battledriver" / "Ogro Guia de Batalha"

IMPORTANTE: abrimos sempre em modo somente-leitura (`mode=ro`). Este arquivo
pertence ao jogo — escrever nele poderia corromper a instalação do Arena.
"""

import sqlite3
from pathlib import Path

from src.models.game_state import Carta
from src.services.arena_paths import caminho_banco_de_cartas

# Uma consulta só, resolvendo nome em dois idiomas e o tipo, de uma vez.
# LEFT JOIN em tudo: carta sem tradução ainda deve aparecer (com nome vazio),
# em vez de sumir silenciosamente do resultado.
_CONSULTA_CARTA = """
    SELECT
        c.GrpId,
        en.Loc      AS nome_en,
        pt.Loc      AS nome_pt,
        tipo.Loc    AS tipo,
        c.Power,
        c.Toughness,
        c.Rarity,
        c.ExpansionCode
    FROM Cards c
    LEFT JOIN Localizations_enUS en   ON en.LocId   = c.TitleId
    LEFT JOIN Localizations_ptBR pt   ON pt.LocId   = c.TitleId
    LEFT JOIN Localizations_ptBR tipo ON tipo.LocId = c.TypeTextId
    WHERE c.GrpId = ?
"""


class BancoDeCartasArena:
    """Traduz `grpId` em cartas, lendo o banco do próprio jogo.

    Mantém um cache em memória: numa partida a mesma carta aparece dezenas de
    vezes (na sua partida, "Montanha" apareceu 102 vezes). Consultar o SQLite
    102 vezes pra mesma resposta é desperdício — a primeira consulta paga, as
    outras 101 são de graça.

    Uso:
        banco = BancoDeCartasArena()
        carta = banco.buscar(75521)
        print(carta.nome_pt)  # "Ogro Guia de Batalha"
    """

    def __init__(self, caminho: Path | None = None) -> None:
        """Abre o banco de cartas do Arena em modo somente-leitura.

        Args:
            caminho: Caminho do arquivo .mtga. Se None, descobre sozinho.
        """
        self.caminho: Path = caminho or caminho_banco_de_cartas()
        # `uri=True` permite o parâmetro `mode=ro` (read-only).
        # `check_same_thread=False` porque o leitor de log roda em async e
        # pode consultar de contextos diferentes.
        self._conexao = sqlite3.connect(
            f"file:{self.caminho}?mode=ro",
            uri=True,
            check_same_thread=False,
        )
        self._cache: dict[int, Carta | None] = {}

    def buscar(self, grp_id: int) -> Carta | None:
        """Devolve a carta correspondente a um `grpId`.

        Args:
            grp_id: ID numérico da carta no Arena.

        Returns:
            A carta, ou None se o ID não existir no banco (acontece com
            objetos internos do jogo, como emblemas e efeitos).
        """
        if grp_id in self._cache:
            return self._cache[grp_id]

        linha = self._conexao.execute(_CONSULTA_CARTA, (grp_id,)).fetchone()

        if linha is None or not linha[1]:
            # Sem nome em inglês = não é uma carta de verdade
            self._cache[grp_id] = None
            return None

        _, nome_en, nome_pt, tipo, poder, resistencia, raridade, colecao = linha
        carta = Carta(
            grp_id=grp_id,
            nome_en=nome_en or "",
            nome_pt=nome_pt or "",
            tipo=tipo or "",
            poder=str(poder) if poder not in (None, "") else "",
            resistencia=str(resistencia) if resistencia not in (None, "") else "",
            raridade=int(raridade or 0),
            colecao=colecao or "",
        )
        self._cache[grp_id] = carta
        return carta

    def total_de_cartas(self) -> int:
        """Conta quantas cartas o banco do Arena tem.

        Serve de teste de sanidade: se vier 0, o arquivo abriu mas está errado.

        Returns:
            Número de linhas na tabela Cards.
        """
        return self._conexao.execute("SELECT COUNT(*) FROM Cards").fetchone()[0]

    def fechar(self) -> None:
        """Fecha a conexão com o banco."""
        self._conexao.close()

    def __enter__(self) -> "BancoDeCartasArena":
        return self

    def __exit__(self, *_erro: object) -> None:
        self.fechar()
