"""Identifica o deck do oponente a partir do que ele já mostrou.

É a primeira peça da Camada 4 (inteligência) e a base das outras: pra
recomendar jogada, escolher sideboard ou decidir se ataca, o sistema precisa
antes saber CONTRA O QUE está jogando.

## Por que isso funciona sem OCR e quase sem token

O `GameState` já sabe exatamente quais cartas o oponente revelou — nome
oficial, tipo, poder, custo. A IA não precisa adivinhar nada de imagem: ela
recebe uma lista limpa e faz o que sabe fazer melhor, que é raciocinar sobre
padrões conhecidos do metagame.

## O que a IA recebe e o que ela NÃO recebe

Recebe: cartas do campo, cemitério, exílio e pilha do oponente — tudo que
está publicamente visível numa mesa física.

**Não recebe: a mão do oponente.** Mesmo que o log traga essa informação em
partidas contra a máquina, `cartas_reveladas_do_oponente()` não a inclui. O
sistema é um assistente de raciocínio, não um raio-x: ele analisa o que
qualquer jogador atento veria. Essa fronteira é deliberada.
"""

import json
from typing import Any

from pydantic import BaseModel, Field

from src.models.game_state import GameState
from src.services.claude_client import ClienteClaude, carregar_prompt
from src.utils.config import DIRETORIO_RAIZ, config


class HipoteseDeDeck(BaseModel):
    """Um palpite sobre qual é o deck do oponente.

    Attributes:
        nome: Nome do arquétipo (ex.: "Mono Blue Tempo").
        confianca: De 0 a 1.
        arquetipo: Família do deck (aggro, control, midrange, combo, ramp, tempo).
        cores: Cores identificadas (W, U, B, R, G).
        raciocinio: Por que a IA chegou nessa conclusão.
    """

    nome: str = ""
    confianca: float = 0.0
    arquetipo: str = ""
    cores: list[str] = Field(default_factory=list)
    raciocinio: str = ""


class AmeacaPrevista(BaseModel):
    """Uma carta que o oponente provavelmente vai jogar e que dói.

    Attributes:
        carta: Nome da carta em inglês.
        probabilidade: Chance de aparecer, de 0 a 1.
        turno_esperado: Em que turno costuma vir.
        impacto: "critica", "alta", "media" ou "baixa".
        motivo: Por que é uma ameaça.
    """

    carta: str = ""
    probabilidade: float = 0.0
    turno_esperado: int = 0
    impacto: str = ""
    motivo: str = ""


class AnaliseDoOponente(BaseModel):
    """Resultado completo da identificação.

    Attributes:
        principal: A hipótese mais provável.
        alternativas: Outras hipóteses consideradas.
        ameacas: Cartas perigosas esperadas.
        como_enfrentar: Conselhos práticos de como jogar contra.
        cartas_analisadas: Quais cartas do oponente foram usadas na análise.
        turno: Turno em que a análise foi feita.
    """

    principal: HipoteseDeDeck = Field(default_factory=HipoteseDeDeck)
    alternativas: list[HipoteseDeDeck] = Field(default_factory=list)
    ameacas: list[AmeacaPrevista] = Field(default_factory=list)
    como_enfrentar: list[str] = Field(default_factory=list)
    cartas_analisadas: list[str] = Field(default_factory=list)
    turno: int = 0


class IdentificadorDeDeck:
    """Descobre qual deck o oponente está jogando.

    Uso:
        identificador = IdentificadorDeDeck()
        analise = identificador.identificar(estado, formato="standard")
        print(f"{analise.principal.nome} ({analise.principal.confianca:.0%})")
    """

    def __init__(self, cliente: ClienteClaude | None = None) -> None:
        """Prepara o identificador.

        Args:
            cliente: Cliente da IA. Se None, cria um com o modelo do .env.
        """
        self.cliente: ClienteClaude = cliente or ClienteClaude()
        self._arquetipos: dict[str, Any] = self._carregar("arquetipos.json")
        self._formatos: dict[str, Any] = self._carregar("formatos.json")

        # Guarda a última análise por assinatura de cartas. Numa partida, o
        # estado muda várias vezes por turno (mana virando, criatura
        # atacando) sem que o oponente revele carta nova. Sem esse cache, o
        # sistema pagaria uma chamada de IA a cada piscada de tela.
        self._cache: dict[str, AnaliseDoOponente] = {}

    @staticmethod
    def _carregar(nome_do_arquivo: str) -> dict[str, Any]:
        """Lê um JSON de apoio da pasta `data/`.

        Args:
            nome_do_arquivo: Nome do arquivo em data/.

        Returns:
            Conteúdo do arquivo, ou dicionário vazio se não existir.
        """
        caminho = DIRETORIO_RAIZ / "data" / nome_do_arquivo
        if not caminho.exists():
            return {}
        return json.loads(caminho.read_text(encoding="utf-8"))

    def identificar(
        self,
        estado: GameState,
        formato: str = "standard",
        usar_cache: bool = True,
    ) -> AnaliseDoOponente:
        """Analisa o que o oponente revelou e identifica o deck.

        Args:
            estado: Estado atual da partida.
            formato: Formato do jogo ("standard", "draft", "brawl"...).
            usar_cache: Se True, reaproveita análise quando nada novo apareceu.

        Returns:
            A análise. Se o oponente ainda não mostrou nada, devolve uma
            análise vazia em vez de gastar uma chamada de IA à toa.
        """
        reveladas = estado.cartas_reveladas_do_oponente()

        # Nomes em INGLÊS de propósito: toda a literatura estratégica de
        # Magic é em inglês, e a IA raciocina melhor com os nomes oficiais.
        # O jogador continua vendo tudo em português na tela.
        nomes = sorted({carta.carta.nome_en for carta in reveladas})

        if not nomes:
            return AnaliseDoOponente(turno=estado.turno)

        assinatura = f"{formato}|{'|'.join(nomes)}"
        if usar_cache and assinatura in self._cache:
            return self._cache[assinatura]

        dados = self.cliente.perguntar_json(
            sistema=carregar_prompt("deck-identifier"),
            usuario=self._montar_pergunta(estado, nomes, formato),
        )

        analise = self._interpretar(dados, nomes, estado.turno)
        self._cache[assinatura] = analise
        return analise

    def _montar_pergunta(
        self, estado: GameState, nomes: list[str], formato: str
    ) -> str:
        """Monta o texto enviado à IA.

        Args:
            estado: Estado da partida.
            nomes: Nomes em inglês das cartas reveladas.
            formato: Formato do jogo.

        Returns:
            A pergunta pronta.
        """
        info_formato = self._formatos.get("formats", {}).get(formato, {})
        familias = list(self._arquetipos.get("archetypes", {}).keys())

        # Detalhar POR ZONA importa: criatura no campo é ameaça presente;
        # carta no cemitério revela o deck mas já foi. A IA precisa dessa
        # diferença pra separar "o que ele tem" de "o que ele joga".
        def listar(cartas: list) -> str:
            if not cartas:
                return "(nada)"
            return ", ".join(sorted({c.carta.nome_en for c in cartas}))

        return f"""CONTEXTO DA PARTIDA

Formato: {formato} ({info_formato.get('description', 'desconhecido')})
Tamanho de deck no formato: {info_formato.get('deck_size', '?')} cartas
Jogo número: {estado.numero_do_jogo}
Turno atual: {estado.turno}
Fase: {estado.etapa or estado.fase or 'desconhecida'}

VIDAS
Eu: {estado.minha_vida}
Oponente: {estado.vida_oponente}

O QUE O OPONENTE REVELOU (nomes oficiais em inglês)
No campo de batalha: {listar(estado.campo_oponente)}
No cemitério: {listar(estado.cemiterio_oponente)}
Todas as cartas vistas: {', '.join(nomes)}

MEU LADO
Meu campo: {listar(estado.meu_campo)}
Cartas na minha mão: {len(estado.minha_mao)}

FAMÍLIAS DE ARQUÉTIPO CONHECIDAS
{', '.join(familias)}

TAREFA
Identifique o deck do oponente. Considere o formato: em Draft e Sealed não
existem arquétipos de metagame consolidados como em Standard — descreva a
estratégia (ex.: "azul-branco voadores tempo") em vez de forçar o nome de um
deck competitivo.

Seja honesto sobre a incerteza: com 2 ou 3 cartas vistas, confiança alta é
chute disfarçado.

RESPONDA APENAS COM ESTE JSON, sem texto antes ou depois:
{{
  "identified_deck": {{
    "name": "nome do deck ou da estratégia",
    "confidence": 0.0 a 1.0,
    "archetype": "uma das famílias listadas acima",
    "colors": ["U", "W"],
    "reasoning": "por que, citando as cartas que provam"
  }},
  "alternative_hypotheses": [
    {{"name": "...", "confidence": 0.0, "archetype": "...", "reasoning": "..."}}
  ],
  "expected_threats": [
    {{"card": "nome em inglês", "probability": 0.0, "expected_turn": 0,
      "impact": "critica|alta|media|baixa", "reason": "..."}}
  ],
  "how_to_counter": ["conselho prático 1", "conselho prático 2"]
}}"""

    @staticmethod
    def _interpretar(
        dados: dict, nomes: list[str], turno: int
    ) -> AnaliseDoOponente:
        """Converte o JSON da IA nos nossos modelos.

        Tolerante de propósito: se a IA esquecer um campo, o resultado sai
        incompleto mas não derruba o sistema no meio da partida.

        Args:
            dados: JSON devolvido pela IA.
            nomes: Cartas que foram analisadas.
            turno: Turno da análise.

        Returns:
            A análise estruturada.
        """
        bruto = dados.get("identified_deck", {})
        principal = HipoteseDeDeck(
            nome=bruto.get("name", "desconhecido"),
            confianca=float(bruto.get("confidence", 0) or 0),
            arquetipo=bruto.get("archetype", ""),
            cores=bruto.get("colors", []) or [],
            raciocinio=bruto.get("reasoning", ""),
        )

        alternativas = [
            HipoteseDeDeck(
                nome=item.get("name", ""),
                confianca=float(item.get("confidence", 0) or 0),
                arquetipo=item.get("archetype", ""),
                cores=item.get("colors", []) or [],
                raciocinio=item.get("reasoning", "") or item.get("why_lower", ""),
            )
            for item in dados.get("alternative_hypotheses", []) or []
        ]

        ameacas = [
            AmeacaPrevista(
                carta=item.get("card", ""),
                probabilidade=float(item.get("probability", 0) or 0),
                turno_esperado=int(item.get("expected_turn", 0) or 0),
                impacto=item.get("impact", ""),
                motivo=item.get("reason", ""),
            )
            for item in dados.get("expected_threats", []) or []
        ]

        return AnaliseDoOponente(
            principal=principal,
            alternativas=alternativas,
            ameacas=ameacas,
            como_enfrentar=dados.get("how_to_counter", []) or [],
            cartas_analisadas=nomes,
            turno=turno,
        )
