"""Analisa a partida que acabou: o que deu errado e o que fazer diferente.

## Por que isso vale mais que a recomendação em tempo real

Durante o jogo você tem 30 segundos e adrenalina. Depois, dá pra olhar o
board inteiro com calma e perguntar "onde é que eu perdi isso?". É a mesma
lógica da discussão de caso depois do plantão: o aprendizado mora na revisão,
não na urgência.

E é aqui que o sistema fecha o ciclo do projeto — a Fase 4 do README:
"deck que ganha ganha vetor positivo, deck que perde é ajustado".

## O que entra na análise

Estado final dos dois lados, resultado, e a trajetória de vida ao longo da
partida. Com isso a IA consegue responder as perguntas que importam:

- Havia um ataque letal que passou batido?
- A curva de mana travou em algum turno?
- Que carta do oponente decidiu o jogo?
- O que trocar no sideboard pro próximo jogo?
"""

from pydantic import BaseModel, Field

from src.models.game_state import GameState
from src.services.claude_client import ClienteClaude
from src.services.scryfall_service import BancoDeTextos


class LicaoDaPartida(BaseModel):
    """Uma conclusão prática tirada da partida.

    Attributes:
        titulo: A lição em uma linha.
        turno: Em que turno isso aconteceu (0 se for geral).
        detalhe: Explicação com os números da partida.
        gravidade: "decisiva", "importante" ou "menor".
    """

    titulo: str = ""
    turno: int = 0
    detalhe: str = ""
    gravidade: str = ""


class TrocaDeSideboard(BaseModel):
    """Sugestão de troca pro próximo jogo da série.

    Attributes:
        tirar: Carta a remover.
        colocar: Carta a adicionar (ou descrição do que procurar).
        motivo: Por que a troca ajuda neste confronto.
    """

    tirar: str = ""
    colocar: str = ""
    motivo: str = ""


class AnalisePosJogo(BaseModel):
    """O resultado completo da revisão da partida.

    Attributes:
        veredito: Resumo em uma frase de por que ganhou ou perdeu.
        eu_venci: Se o jogador venceu.
        momento_decisivo: O turno que decidiu a partida, e por quê.
        havia_letal_perdido: Se existiu um ataque letal não executado.
        licoes: O que aprender.
        sideboard: Trocas sugeridas pro próximo jogo.
        contra_este_deck: Plano de jogo pro próximo confronto igual.
    """

    veredito: str = ""
    eu_venci: bool | None = None
    momento_decisivo: str = ""
    havia_letal_perdido: bool = False
    licoes: list[LicaoDaPartida] = Field(default_factory=list)
    sideboard: list[TrocaDeSideboard] = Field(default_factory=list)
    contra_este_deck: list[str] = Field(default_factory=list)


SISTEMA = """Você é um treinador de Magic: The Gathering analisando a partida \
de um aluno que acabou de terminar.

Seu trabalho não é consolar nem culpar. É achar a decisão específica que mudou \
o resultado, com os números da partida na mão.

REGRAS:
1. Use SEMPRE o poder/resistência marcado como ATUAL. Nunca some com o valor
   base impresso da ficha, nunca invente um terceiro número.
2. Faça a conta de combate explicitamente quando avaliar um ataque: quantos
   atacantes, quantos bloqueadores, quanto dano passa.
3. Lembre que criatura voadora BLOQUEIA criatura terrestre normalmente. O
   contrário é que não vale: criatura sem alcance nem voo não bloqueia voador.
4. Se não houver erro claro do jogador, diga isso. Perder pra um deck melhor
   não é erro — e inventar um erro que não houve ensina a coisa errada.
5. Seja concreto: "no turno 12 você tinha 6 atacantes contra 2 bloqueadores"
   vale mais que "faltou agressividade".

Responda APENAS com JSON válido."""


class PartidaNaoTerminou(RuntimeError):
    """Tentou revisar uma partida que ainda está em andamento."""


class AnalisadorPosJogo:
    """Revisa uma partida encerrada.

    Uso:
        analisador = AnalisadorPosJogo()
        analise = analisador.analisar(estado_final)
        print(analise.veredito)
    """

    def __init__(
        self,
        cliente: ClienteClaude | None = None,
        textos: BancoDeTextos | None = None,
    ) -> None:
        """Prepara o analisador.

        Args:
            cliente: Cliente da IA. Se None, cria um.
            textos: Banco de textos das cartas. Se None, abre um.
        """
        self.cliente: ClienteClaude = cliente or ClienteClaude()
        self.textos: BancoDeTextos = textos or BancoDeTextos()

    def analisar(
        self,
        estado: GameState,
        formato: str = "standard",
        vidas_ao_longo: list[int] | None = None,
        exigir_encerrada: bool = True,
    ) -> AnalisePosJogo:
        """Revisa a partida encerrada.

        Args:
            estado: Estado final da partida.
            formato: Formato do jogo.
            vidas_ao_longo: Trajetória de vida, se disponível.
            exigir_encerrada: Se True (padrão), recusa analisar partida em
                andamento.

        Returns:
            A análise.

        Raises:
            PartidaNaoTerminou: Se a partida ainda está rolando.
        """
        # Guarda que nasceu de um erro real: o analisador pegou o jogo em
        # andamento (turno 7, 18x20) achando que era o que tinha acabado, e
        # escreveu "perdi porque terminei com zero criaturas" sobre uma
        # partida que ainda estava no meio.
        #
        # Análise confiante da partida errada é pior que análise nenhuma:
        # o jogador tira lição de algo que não aconteceu.
        if exigir_encerrada and estado.resultado is None:
            raise PartidaNaoTerminou(
                f"O jogo {estado.numero_do_jogo} está no turno {estado.turno} "
                "e não tem resultado registrado — ainda está em andamento.\n"
                "Use LeitorDeLogArena.ultimo_jogo_encerrado() pra pegar a "
                "partida certa, ou passe exigir_encerrada=False se souber o "
                "que está fazendo."
            )

        dados = self.cliente.perguntar_json(
            sistema=SISTEMA,
            usuario=self._montar_pergunta(estado, formato, vidas_ao_longo),
            max_tokens=4000,
        )
        return self._interpretar(dados, estado)

    def _montar_pergunta(
        self,
        estado: GameState,
        formato: str,
        vidas_ao_longo: list[int] | None,
    ) -> str:
        """Monta o texto enviado à IA.

        Args:
            estado: Estado final.
            formato: Formato do jogo.
            vidas_ao_longo: Trajetória de vida.

        Returns:
            A pergunta pronta.
        """
        def detalhar(cartas: list) -> str:
            if not cartas:
                return "(nada)"
            saida = []
            for c in cartas:
                texto = c.carta.nome_en
                if c.poder_atual:
                    texto += f" (ATUAL {c.poder_atual}/{c.resistencia_atual})"
                if c.virada:
                    texto += " [virada]"
                saida.append(texto)
            return "; ".join(saida)

        # Ficha das cartas não-básicas, pro raciocínio ficar ancorado
        relevantes = estado.meu_campo + estado.campo_oponente + estado.cemiterio_oponente
        basicos = {"Plains", "Island", "Swamp", "Mountain", "Forest"}
        nomes = sorted(
            {c.carta.nome_en for c in relevantes if c.carta.nome_en not in basicos}
        )
        fichas = self.textos.buscar_varias(nomes)
        bloco_fichas = "\n".join(
            f"- {f.nome} {f.custo} (base impressa: {f.poder}/{f.resistencia})"
            f" [keywords: {', '.join(f.keywords) or 'nenhuma'}]: "
            f"{f.texto.replace(chr(10), ' / ')}"
            for f in fichas.values()
        ) or "(sem fichas)"

        resultado = estado.resultado
        if resultado and resultado.eu_venci is not None:
            veredito = "VITÓRIA" if resultado.eu_venci else "DERROTA"
        else:
            veredito = "resultado desconhecido"

        trajetoria = ""
        if vidas_ao_longo:
            trajetoria = f"\nTRAJETÓRIA DE VIDA (amostras): {vidas_ao_longo[:40]}"

        # Lista explícita do que é MEU — a IA já sugeriu tirar do sideboard
        # do jogador uma carta que era do oponente (Wanderwine Distracter).
        # Dar a lista pronta é mais confiável do que esperar que ela deduza
        # certo a partir dos títulos das seções.
        minhas = sorted(
            {
                c.carta.nome_en
                for c in estado.meu_campo + estado.minha_mao
                if c.carta.nome_en
            }
        )
        dele = sorted(
            {
                c.carta.nome_en
                for c in estado.campo_oponente + estado.cemiterio_oponente
                if c.carta.nome_en
            }
        )

        return f"""PARTIDA ENCERRADA

Formato: {formato} | Jogo {estado.numero_do_jogo}
Duração: {estado.turno} turnos
Resultado: {veredito}
Vida final: eu {estado.minha_vida}, oponente {estado.vida_oponente}{trajetoria}

FICHA DAS CARTAS (texto verificado; o P/T aqui é BASE IMPRESSO — para conta
de combate use o valor marcado como ATUAL na descrição do board)
{bloco_fichas}

MEU BOARD FINAL
{detalhar(estado.meu_campo)}

BOARD FINAL DO OPONENTE
{detalhar(estado.campo_oponente)}

CEMITÉRIO DO OPONENTE (o que ele gastou na partida)
{detalhar(estado.cemiterio_oponente)}

MINHA MÃO NO FINAL
{detalhar(estado.minha_mao)}

⚠️ DE QUEM É CADA CARTA (confira antes de sugerir sideboard)
Cartas do MEU deck (só estas podem entrar ou sair do meu sideboard):
{', '.join(minhas) or '(nenhuma)'}

Cartas do DECK DELE (NUNCA sugira tirar ou colocar estas no meu deck —
não são minhas):
{', '.join(dele) or '(nenhuma)'}

TAREFA
Revise a partida. Comece FAZENDO A CONTA DE COMBATE do board final: quantas
criaturas eu tinha aptas a atacar, quantos bloqueadores ele tinha, e quanto
dano passaria num ataque total. Compare com a vida dele.

Depois responda: houve um ataque letal disponível que não foi executado?

No sideboard, o campo "out" só pode conter carta da lista MEU DECK acima.
Se a sugestão for uma carta que eu ainda não mostrei nesta partida, descreva
o tipo de carta ("criatura vermelha de 2 de mana") em vez de inventar um nome.

RESPONDA APENAS COM ESTE JSON:
{{
  "verdict": "por que ganhei ou perdi, em uma frase",
  "decisive_moment": "o turno e a decisão que definiram a partida",
  "lethal_was_available": true/false,
  "lethal_explanation": "a conta de combate, com números",
  "lessons": [
    {{"title": "a lição", "turn": 0, "detail": "com os números",
      "severity": "decisiva|importante|menor"}}
  ],
  "sideboard": [
    {{"out": "carta a tirar", "in": "carta a colocar", "reason": "por quê"}}
  ],
  "next_time_vs_this_deck": ["plano de jogo pro próximo confronto"]
}}"""

    @staticmethod
    def _interpretar(dados: dict, estado: GameState) -> AnalisePosJogo:
        """Converte o JSON da IA no nosso modelo.

        Args:
            dados: JSON da IA.
            estado: Estado final, pra puxar o resultado real.

        Returns:
            A análise estruturada.
        """
        licoes = [
            LicaoDaPartida(
                titulo=item.get("title", ""),
                turno=int(item.get("turn", 0) or 0),
                detalhe=item.get("detail", ""),
                gravidade=item.get("severity", ""),
            )
            for item in dados.get("lessons", []) or []
        ]

        trocas = [
            TrocaDeSideboard(
                tirar=item.get("out", ""),
                colocar=item.get("in", ""),
                motivo=item.get("reason", ""),
            )
            for item in dados.get("sideboard", []) or []
        ]

        momento = dados.get("decisive_moment", "")
        explicacao = dados.get("lethal_explanation", "")
        if explicacao:
            momento = f"{momento}\n\n{explicacao}" if momento else explicacao

        return AnalisePosJogo(
            veredito=dados.get("verdict", ""),
            eu_venci=estado.resultado.eu_venci if estado.resultado else None,
            momento_decisivo=momento,
            havia_letal_perdido=bool(dados.get("lethal_was_available", False)),
            licoes=licoes,
            sideboard=trocas,
            contra_este_deck=dados.get("next_time_vs_this_deck", []) or [],
        )
