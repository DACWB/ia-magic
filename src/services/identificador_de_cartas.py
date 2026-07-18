"""Transforma uma lista de nomes escritos à mão em cartas de verdade.

## Por que isso existe

A coleção do jogador não está em lugar nenhum que dê pra ler automaticamente
— nem no log, nem em arquivo local. Então em algum momento ela chega como
TEXTO: exportada do Arena, digitada, ou lida de uma tela.

Texto vindo de humano ou de OCR tem erro: acento faltando, letra trocada,
nome cortado. Se o sistema aceitar "Capitao America" e não achar nada, a
carta simplesmente some do deck e ninguém percebe.

Este módulo resolve casando cada nome contra as ~26 mil cartas do banco do
próprio Arena, que tem os nomes oficiais em português E em inglês. É a mesma
ideia do Dia 3: em vez de confiar no texto, ancorar num dado verificável.

## Formatos que ele entende

    4 Triunfo Político (MSH) 12      <- exportado do Arena
    4x Triunfo Politico              <- digitado, sem acento
    Triunfo Politico                 <- só o nome (assume 1 cópia)
    2 Capitao America, Icone da...   <- OCR cortando o nome
"""

import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from src.models.game_state import Carta
from src.services.arena_paths import caminho_banco_de_cartas

# Confiança mínima pra aceitar um casamento aproximado. Abaixo disso é melhor
# devolver "não encontrei" do que fingir que achou a carta errada.
LIMITE_DE_SEMELHANCA = 0.82


def normalizar(texto: str) -> str:
    """Deixa o texto comparável: sem acento, sem pontuação, minúsculo.

    "Capitão América, Ícone da Liberdade" vira "capitao america icone da
    liberdade". Assim quem digitou sem acento ainda casa.

    Args:
        texto: Nome como veio.

    Returns:
        Versão normalizada.
    """
    sem_acento = "".join(
        c
        for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    sem_pontuacao = re.sub(r"[^a-z0-9 ]", " ", sem_acento.lower())

    # Colapsar espaços é essencial, não cosmético: a vírgula vira espaço, e
    # "Capitão América, Ícone" produziria DOIS espaços onde quem digitou sem
    # vírgula produz um só. As duas chaves ficariam diferentes e o casamento
    # exato falharia — justo nas cartas lendárias, que no Marvel são quase
    # todos os heróis ("Nome, Título").
    return re.sub(r"\s+", " ", sem_pontuacao).strip()


@dataclass
class LinhaDaLista:
    """Uma linha da lista que o jogador forneceu.

    Attributes:
        texto_original: A linha como veio.
        quantidade: Quantas cópias.
        nome_lido: O nome extraído da linha.
        carta: A carta encontrada no banco, se houve.
        semelhanca: Quão parecido o nome lido está do oficial (0 a 1).
        exato: Se casou perfeitamente, sem aproximação.
    """

    texto_original: str
    quantidade: int = 1
    nome_lido: str = ""
    carta: Carta | None = None
    semelhanca: float = 0.0
    exato: bool = False


@dataclass
class ResultadoDaLeitura:
    """O que saiu da leitura da lista inteira.

    Attributes:
        encontradas: Linhas que viraram carta.
        duvidosas: Casaram, mas por aproximação — vale conferir.
        nao_encontradas: Não casaram com nada.
    """

    encontradas: list[LinhaDaLista] = field(default_factory=list)
    duvidosas: list[LinhaDaLista] = field(default_factory=list)
    nao_encontradas: list[LinhaDaLista] = field(default_factory=list)

    @property
    def total_de_cartas(self) -> int:
        """Soma das cópias identificadas."""
        return sum(l.quantidade for l in self.encontradas + self.duvidosas)

    def resumo(self) -> str:
        """Descreve o resultado em uma linha."""
        return (
            f"{len(self.encontradas)} exatas, "
            f"{len(self.duvidosas)} aproximadas, "
            f"{len(self.nao_encontradas)} não encontradas "
            f"({self.total_de_cartas} cartas no total)"
        )


class IdentificadorDeCartas:
    """Casa nomes escritos com as cartas oficiais do banco do Arena.

    Uso:
        with IdentificadorDeCartas() as ident:
            resultado = ident.ler_lista(texto_colado)
            print(resultado.resumo())
    """

    def __init__(self) -> None:
        """Carrega o índice de nomes do banco do Arena."""
        self._conexao = sqlite3.connect(
            f"file:{caminho_banco_de_cartas()}?mode=ro", uri=True
        )
        # nome normalizado -> (grp_id, nome_en, nome_pt)
        self._indice: dict[str, tuple[int, str, str]] = {}
        self._carregar_indice()

    def _carregar_indice(self) -> None:
        """Monta o índice de busca com os nomes em inglês e português."""
        consulta = """
            SELECT c.GrpId, en.Loc, pt.Loc
            FROM Cards c
            LEFT JOIN Localizations_enUS en ON en.LocId = c.TitleId
            LEFT JOIN Localizations_ptBR pt ON pt.LocId = c.TitleId
            WHERE c.IsPrimaryCard = 1 AND en.Loc IS NOT NULL
        """
        for grp_id, nome_en, nome_pt in self._conexao.execute(consulta):
            registro = (grp_id, nome_en or "", nome_pt or "")
            # Indexa pelos dois idiomas: a lista pode vir em qualquer um
            for nome in (nome_en, nome_pt):
                if nome:
                    self._indice.setdefault(normalizar(nome), registro)

    def _buscar(self, nome: str) -> tuple[Carta | None, float]:
        """Acha a carta mais parecida com o nome dado.

        Args:
            nome: Nome lido da lista.

        Returns:
            A carta e o grau de semelhança (1.0 = exato).
        """
        chave = normalizar(nome)
        if not chave:
            return None, 0.0

        # 1. Casamento exato
        if chave in self._indice:
            grp, en, pt = self._indice[chave]
            return Carta(grp_id=grp, nome_en=en, nome_pt=pt), 1.0

        # 2. Nome cortado: o OCR costuma perder o fim do texto.
        #    "Capitao America Icone da" deve achar "Capitão América, Ícone
        #    da Liberdade".
        candidatos = [k for k in self._indice if k.startswith(chave)]
        if len(candidatos) == 1:
            grp, en, pt = self._indice[candidatos[0]]
            return Carta(grp_id=grp, nome_en=en, nome_pt=pt), 0.95

        # 3. Aproximação por semelhança. Só compara com nomes de tamanho
        #    parecido — sem isso, varrer 26 mil nomes fica lento e ainda
        #    casa bobagem.
        melhor_chave, melhor_nota = "", 0.0
        faixa = range(max(1, len(chave) - 6), len(chave) + 7)
        for candidato in self._indice:
            if len(candidato) not in faixa:
                continue
            nota = SequenceMatcher(None, chave, candidato).ratio()
            if nota > melhor_nota:
                melhor_chave, melhor_nota = candidato, nota

        if melhor_nota >= LIMITE_DE_SEMELHANCA:
            grp, en, pt = self._indice[melhor_chave]
            return Carta(grp_id=grp, nome_en=en, nome_pt=pt), melhor_nota

        return None, melhor_nota

    @staticmethod
    def _separar_quantidade(linha: str) -> tuple[int, str]:
        """Separa "4x Nome da Carta (MSH) 12" em quantidade e nome.

        Args:
            linha: Uma linha da lista.

        Returns:
            Quantidade e nome limpo.
        """
        texto = linha.strip()

        # Tira o sufixo de set do formato exportado: "(MSH) 12"
        texto = re.sub(r"\s*\([A-Z0-9]{2,5}\)\s*\d*\s*$", "", texto)

        achado = re.match(r"^(\d+)\s*[xX]?\s+(.+)$", texto)
        if achado:
            return int(achado.group(1)), achado.group(2).strip()
        return 1, texto

    def ler_lista(self, texto: str) -> ResultadoDaLeitura:
        """Lê uma lista inteira e devolve as cartas identificadas.

        Args:
            texto: A lista colada, uma carta por linha.

        Returns:
            O resultado, separado por confiança.
        """
        resultado = ResultadoDaLeitura()

        for bruta in texto.splitlines():
            limpa = bruta.strip()
            # Pula linhas vazias e cabeçalhos do export ("Deck", "Reserva")
            if not limpa or limpa.lower() in ("deck", "sideboard", "reserva",
                                              "companion", "commander"):
                continue

            quantidade, nome = self._separar_quantidade(limpa)
            carta, nota = self._buscar(nome)

            linha = LinhaDaLista(
                texto_original=limpa,
                quantidade=quantidade,
                nome_lido=nome,
                carta=carta,
                semelhanca=nota,
                exato=nota >= 1.0,
            )

            if carta is None:
                resultado.nao_encontradas.append(linha)
            elif linha.exato:
                resultado.encontradas.append(linha)
            else:
                resultado.duvidosas.append(linha)

        return resultado

    def fechar(self) -> None:
        """Fecha a conexão com o banco."""
        self._conexao.close()

    def __enter__(self) -> "IdentificadorDeCartas":
        return self

    def __exit__(self, *_erro: object) -> None:
        self.fechar()
