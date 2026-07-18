"""Texto oficial das cartas, via Scryfall, com cache local em SQLite.

## Por que este módulo existe (a fatura que chegou)

Sem ele, a IA raciocina pela MEMÓRIA que tem das cartas. Num teste real ela
recomendou atacar afirmando que "Nest Robber tem menace, então passa ileso".
Nest Robber tem **ímpeto**, não menace — e o bloqueador do oponente era um
Cloudkin Seer com **voar**, que a IA nem mencionou. A recomendação estava
errada, com 90% de confiança declarada.

Alucinação confiante é o pior tipo de erro num sistema de apoio à decisão:
ela não parece erro. A defesa é sempre a mesma — ancorar o raciocínio em
dados verificáveis, não na lembrança do modelo.

## Por que Scryfall e não o banco do Arena

O banco do Arena tem o texto, e seria local e instantâneo. Mas o campo
`AbilityIds` usa um formato não documentado (`"9:101"`) que, decodificado
ingenuamente, atribuiu "Evolve" ao Nest Robber e "Bushido" ao Cloudkin Seer.
Texto errado com cara de fonte oficial é pior que texto nenhum.

O Scryfall é a fonte que o próprio ecossistema de Magic usa, tem API pública
e devolve `keywords` já em lista limpa — exatamente o campo que teria evitado
o erro do menace.

## Cache

Cada carta é buscada UMA vez e guardada no SQLite do projeto. A partir da
segunda vez é instantâneo e offline. O Scryfall pede ~100ms entre requisições,
que respeitamos.
"""

import sqlite3
import time
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

from src.utils.config import config

URL_SCRYFALL = "https://api.scryfall.com/cards/named"

# O Scryfall pede 50-100ms entre requisições. Usamos 120ms por educação:
# é uma API pública e gratuita mantida pela comunidade.
PAUSA_ENTRE_REQUISICOES = 0.12


class TextoDeCarta(BaseModel):
    """O que a IA precisa saber sobre uma carta pra raciocinar direito.

    Attributes:
        nome: Nome oficial em inglês.
        custo: Custo de mana ("{1}{R}").
        cmc: Custo convertido.
        tipo: Linha de tipo ("Creature — Dinosaur").
        texto: Texto de regras completo.
        poder: Poder impresso.
        resistencia: Resistência impressa.
        keywords: Habilidades-chave em lista limpa (["Haste"], ["Flying"]).
            É o campo que impede o erro de atribuir habilidade inexistente.
        cores: Cores da carta.
    """

    nome: str
    custo: str = ""
    cmc: float = 0.0
    tipo: str = ""
    texto: str = ""
    poder: str = ""
    resistencia: str = ""
    keywords: list[str] = Field(default_factory=list)
    cores: list[str] = Field(default_factory=list)

    def resumo(self) -> str:
        """Descreve a carta em uma linha, pronta pra entrar num prompt.

        Returns:
            Descrição compacta com o que importa pra decisão.
        """
        partes = [self.nome]
        if self.custo:
            partes.append(self.custo)
        if self.poder:
            partes.append(f"{self.poder}/{self.resistencia}")
        if self.tipo:
            partes.append(f"— {self.tipo}")
        cabecalho = " ".join(partes)

        if self.texto:
            corpo = self.texto.replace("\n", " / ")
            return f"{cabecalho}: {corpo}"
        return cabecalho


class BancoDeTextos:
    """Busca e guarda o texto oficial das cartas.

    Uso:
        with BancoDeTextos() as banco:
            carta = banco.buscar("Nest Robber")
            print(carta.keywords)   # ['Haste']
    """

    def __init__(self, caminho: Path | None = None, offline: bool = False) -> None:
        """Abre (ou cria) o cache local.

        Args:
            caminho: Arquivo SQLite. Se None, usa o do .env.
            offline: Se True, nunca vai à rede — só responde o que já está
                em cache. Útil pra testes e pra jogar sem internet.
        """
        self.caminho: Path = caminho or config.database_path
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.offline: bool = offline

        self._conexao = sqlite3.connect(self.caminho, check_same_thread=False)
        self._criar_tabela()
        self._memoria: dict[str, TextoDeCarta | None] = {}
        self._ultima_requisicao: float = 0.0

        self.buscas_na_rede: int = 0
        self.acertos_de_cache: int = 0

    def _criar_tabela(self) -> None:
        """Cria a tabela de cache, se ainda não existir."""
        self._conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS textos_de_cartas (
                nome        TEXT PRIMARY KEY,
                custo       TEXT,
                cmc         REAL,
                tipo        TEXT,
                texto       TEXT,
                poder       TEXT,
                resistencia TEXT,
                keywords    TEXT,
                cores       TEXT
            )
            """
        )
        self._conexao.commit()

    def buscar(self, nome_em_ingles: str) -> TextoDeCarta | None:
        """Devolve o texto oficial de uma carta.

        Ordem de busca: memória → SQLite → Scryfall.

        Args:
            nome_em_ingles: Nome oficial da carta em inglês.

        Returns:
            O texto da carta, ou None se não existir (ou se estiver offline
            e a carta não estiver em cache).
        """
        chave = nome_em_ingles.strip()
        if not chave:
            return None

        if chave in self._memoria:
            return self._memoria[chave]

        do_banco = self._ler_do_banco(chave)
        if do_banco is not None:
            self.acertos_de_cache += 1
            self._memoria[chave] = do_banco
            return do_banco

        if self.offline:
            self._memoria[chave] = None
            return None

        da_rede = self._buscar_na_rede(chave)
        if da_rede is not None:
            self._gravar_no_banco(da_rede)
        self._memoria[chave] = da_rede
        return da_rede

    def buscar_varias(self, nomes: list[str]) -> dict[str, TextoDeCarta]:
        """Busca várias cartas de uma vez.

        Args:
            nomes: Nomes em inglês.

        Returns:
            Dicionário nome → texto, pulando as que não foram encontradas.
        """
        resultado = {}
        for nome in dict.fromkeys(nomes):  # remove duplicatas mantendo a ordem
            carta = self.buscar(nome)
            if carta is not None:
                resultado[nome] = carta
        return resultado

    def _ler_do_banco(self, nome: str) -> TextoDeCarta | None:
        """Lê uma carta do cache SQLite.

        Args:
            nome: Nome da carta.

        Returns:
            A carta, ou None se não estiver em cache.
        """
        linha = self._conexao.execute(
            "SELECT nome, custo, cmc, tipo, texto, poder, resistencia, "
            "keywords, cores FROM textos_de_cartas WHERE nome = ?",
            (nome,),
        ).fetchone()
        if linha is None:
            return None

        return TextoDeCarta(
            nome=linha[0],
            custo=linha[1] or "",
            cmc=linha[2] or 0.0,
            tipo=linha[3] or "",
            texto=linha[4] or "",
            poder=linha[5] or "",
            resistencia=linha[6] or "",
            keywords=[k for k in (linha[7] or "").split("|") if k],
            cores=[c for c in (linha[8] or "").split("|") if c],
        )

    def _gravar_no_banco(self, carta: TextoDeCarta) -> None:
        """Guarda uma carta no cache SQLite.

        Args:
            carta: A carta a guardar.
        """
        self._conexao.execute(
            "INSERT OR REPLACE INTO textos_de_cartas "
            "(nome, custo, cmc, tipo, texto, poder, resistencia, keywords, cores) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                carta.nome,
                carta.custo,
                carta.cmc,
                carta.tipo,
                carta.texto,
                carta.poder,
                carta.resistencia,
                "|".join(carta.keywords),
                "|".join(carta.cores),
            ),
        )
        self._conexao.commit()

    def _buscar_na_rede(self, nome: str) -> TextoDeCarta | None:
        """Consulta o Scryfall.

        Args:
            nome: Nome exato da carta em inglês.

        Returns:
            A carta, ou None se não achou ou a rede falhou. Falha de rede
            NUNCA derruba o sistema: sem texto, a IA ainda funciona — só
            com menos precisão.
        """
        # Respeita a pausa pedida pelo Scryfall
        desde_a_ultima = time.monotonic() - self._ultima_requisicao
        if desde_a_ultima < PAUSA_ENTRE_REQUISICOES:
            time.sleep(PAUSA_ENTRE_REQUISICOES - desde_a_ultima)

        try:
            resposta = httpx.get(
                URL_SCRYFALL,
                params={"exact": nome},
                timeout=10,
                headers={"User-Agent": "magic-ai-advisor/0.1"},
            )
            self._ultima_requisicao = time.monotonic()
            self.buscas_na_rede += 1

            if resposta.status_code != 200:
                return None  # carta não existe, ou nome com grafia diferente

            dados = resposta.json()
        except (httpx.HTTPError, ValueError):
            return None

        return TextoDeCarta(
            nome=dados.get("name", nome),
            custo=dados.get("mana_cost", "") or "",
            cmc=float(dados.get("cmc", 0) or 0),
            tipo=dados.get("type_line", "") or "",
            texto=dados.get("oracle_text", "") or "",
            poder=str(dados.get("power", "") or ""),
            resistencia=str(dados.get("toughness", "") or ""),
            keywords=dados.get("keywords", []) or [],
            cores=dados.get("colors", []) or [],
        )

    def total_em_cache(self) -> int:
        """Quantas cartas já estão guardadas localmente.

        Returns:
            Número de cartas em cache.
        """
        return self._conexao.execute(
            "SELECT COUNT(*) FROM textos_de_cartas"
        ).fetchone()[0]

    def fechar(self) -> None:
        """Fecha a conexão."""
        self._conexao.close()

    def __enter__(self) -> "BancoDeTextos":
        return self

    def __exit__(self, *_erro: object) -> None:
        self.fechar()
