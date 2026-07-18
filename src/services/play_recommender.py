"""Recomenda a próxima jogada: o que baixar, se ataca, se segura mana.

É a funcionalidade que mais mexe no winrate, porque age no momento da
decisão — diferente do identificador de deck, que só informa.

## O que muda em relação ao identificador de deck

O identificador olha só pro lado do oponente e pode errar sem prejuízo: uma
hipótese errada custa uma leitura ruim. Aqui é diferente — a recomendação vira
ação, e ação errada perde partida. Por isso este módulo:

1. **Manda mais contexto**: mão, campo dos dois lados, mana por cor,
   quem pode atacar, quem pode bloquear, dano marcado
2. **Exige alternativas**: a IA tem que dizer o que considerou e descartou,
   pra você julgar em vez de obedecer
3. **Sempre inclui o risco**: toda recomendação vem com "o que pode dar errado"

## Sobre confiar na recomendação

O sistema é um copiloto, não um piloto automático. Ele vê o board mas não
sabe o que está na sua mão *futura*, não conhece seu estilo, e erra em
situações incomuns. A UI mostra o raciocínio junto com a resposta justamente
pra você discordar quando fizer sentido.
"""

import time

from pydantic import BaseModel, Field

from src.models.game_state import GameState
from src.services.claude_client import ClienteClaude, carregar_prompt
from src.services.deck_identifier import AnaliseDoOponente
from src.services.scryfall_service import BancoDeTextos


class Jogada(BaseModel):
    """Uma jogada possível, avaliada pela IA.

    Attributes:
        acao: O que fazer, em uma linha ("Baixar Ogre Battledriver").
        cartas: Cartas envolvidas, em inglês.
        prioridade: Ordem sugerida (1 = fazer primeiro).
        motivo: Por que essa jogada.
        risco: O que pode dar errado.
    """

    acao: str = ""
    cartas: list[str] = Field(default_factory=list)
    prioridade: int = 0
    motivo: str = ""
    risco: str = ""


class RecomendacaoDeJogada(BaseModel):
    """A recomendação completa para o turno atual.

    Attributes:
        resumo: A recomendação em uma frase.
        sequencia: Jogadas na ordem sugerida.
        atacar: True (atacar), False (não atacar) ou None (não é fase de ataque).
        com_quais_atacar: Criaturas que devem atacar.
        motivo_do_ataque: Raciocínio da decisão de combate.
        segurar_mana: Se vale deixar mana aberta.
        motivo_da_mana: Por que segurar (ou não).
        alternativas_descartadas: O que a IA considerou e rejeitou, e por quê.
        alerta: Aviso urgente, se houver.
        confianca: De 0 a 1.
    """

    resumo: str = ""
    sequencia: list[Jogada] = Field(default_factory=list)
    atacar: bool | None = None
    com_quais_atacar: list[str] = Field(default_factory=list)
    motivo_do_ataque: str = ""
    segurar_mana: bool = False
    motivo_da_mana: str = ""
    alternativas_descartadas: list[str] = Field(default_factory=list)
    alerta: str = ""
    confianca: float = 0.0


class RecomendacaoRapida(BaseModel):
    """Conselho enxuto, pra ler em segundos no meio do turno.

    Attributes:
        acao: O que fazer, em uma frase curta.
        motivo: Por quê, em uma frase curta.
        atacar: True, False, ou None se não é decisão de ataque agora.
        alerta: Aviso urgente, ou vazio.
        segundos: Quanto tempo a IA levou pra responder.
    """

    acao: str = ""
    motivo: str = ""
    atacar: bool | None = None
    alerta: str = ""
    segundos: float = 0.0


SISTEMA_RAPIDO = """Você é um copiloto de Magic: The Gathering dando conselho \
DURANTE a partida, com o relógio do turno correndo.

Seja telegráfico. O jogador tem poucos segundos para ler.

REGRAS QUE NÃO PODEM SER VIOLADAS:
- Use SEMPRE o poder/resistência marcado como ATUAL. Nunca some com a base
  impressa da ficha, nunca invente um terceiro número.
- Criatura enjoada NÃO ataca, mas bloqueia normalmente.
- Criatura virada não bloqueia.
- Voador bloqueia criatura terrestre normalmente. O contrário é que não vale.
- Não recomende o que não dá pra pagar com a mana disponível.
- Se não é fase de ataque ou não há decisão de combate, "atacar" é null.

Responda APENAS o JSON, sem texto ao redor."""


class RecomendadorDeJogada:
    """Sugere a melhor jogada para o estado atual da partida.

    Uso:
        recomendador = RecomendadorDeJogada()
        rec = recomendador.recomendar(estado, analise_do_oponente)
        print(rec.resumo)
    """

    def __init__(
        self,
        cliente: ClienteClaude | None = None,
        textos: BancoDeTextos | None = None,
    ) -> None:
        """Prepara o recomendador.

        Args:
            cliente: Cliente da IA. Se None, cria um com o modelo do .env.
            textos: Banco de textos oficiais das cartas. Se None, abre um.
                Passe `BancoDeTextos(offline=True)` pra não usar rede.
        """
        self.cliente: ClienteClaude = cliente or ClienteClaude()
        self.textos: BancoDeTextos = textos or BancoDeTextos()
        self._cache: dict[str, RecomendacaoDeJogada] = {}
        self._cache_rapido: dict[str, RecomendacaoRapida] = {}

    def recomendar(
        self,
        estado: GameState,
        oponente: AnaliseDoOponente | None = None,
        formato: str = "standard",
        usar_cache: bool = True,
    ) -> RecomendacaoDeJogada | None:
        """Recomenda a jogada para o momento atual.

        Args:
            estado: Estado da partida.
            oponente: Análise do deck do oponente, se já feita.
            formato: Formato do jogo.
            usar_cache: Reaproveita recomendação se o board não mudou.

        Returns:
            A recomendação, ou None se não há nada a decidir (mão vazia e
            nenhuma criatura apta a atacar).
        """
        # `ha_algo_a_decidir` inclui a decisão de BLOQUEIO, que acontece no
        # turno do oponente e com a mão possivelmente vazia. A versão antiga
        # desta guarda só olhava mão e atacantes, e por isso o sistema ficava
        # mudo justamente na hora de bloquear.
        if not estado.ha_algo_a_decidir():
            return None

        assinatura = self._assinatura(estado)
        if usar_cache and assinatura in self._cache:
            return self._cache[assinatura]

        dados = self.cliente.perguntar_json(
            sistema=carregar_prompt("play-recommender"),
            usuario=self._montar_pergunta(estado, oponente, formato),
        )

        recomendacao = self._interpretar(dados)
        self._cache[assinatura] = recomendacao
        return recomendacao

    def recomendar_rapido(
        self,
        estado: GameState,
        oponente: AnaliseDoOponente | None = None,
        formato: str = "standard",
        usar_cache: bool = True,
    ) -> RecomendacaoRapida | None:
        """Conselho enxuto, pra usar com o relógio do turno correndo.

        Mede-se em segundos, não em qualidade de redação. A versão completa
        (`recomendar`) leva ~22s porque escreve 1300 tokens de análise — ótimo
        pra revisar entre turnos, inútil no meio de um.

        A descoberta que motivou este método: a API entrega ~60 tokens por
        segundo em qualquer modelo e qualquer esforço. Ou seja, o tempo é
        ditado pelo TAMANHO DA RESPOSTA. Pedindo 90 tokens em vez de 1300, o
        conselho sai em ~2,5s.

        Args:
            estado: Estado da partida.
            oponente: Análise do oponente, se já feita.
            formato: Formato do jogo.
            usar_cache: Reaproveita se o board não mudou.

        Returns:
            O conselho, ou None se não há nada a decidir.
        """
        # `ha_algo_a_decidir` inclui a decisão de BLOQUEIO, que acontece no
        # turno do oponente e com a mão possivelmente vazia. A versão antiga
        # desta guarda só olhava mão e atacantes, e por isso o sistema ficava
        # mudo justamente na hora de bloquear.
        if not estado.ha_algo_a_decidir():
            return None

        assinatura = "rapido|" + self._assinatura(estado)
        if usar_cache and assinatura in self._cache_rapido:
            return self._cache_rapido[assinatura]

        contexto = self._montar_pergunta(estado, oponente, formato)
        # Reaproveita todo o contexto (board, mana, fichas das cartas) e troca
        # só o pedido final — o que a IA deve devolver.
        contexto = contexto.split("TAREFA")[0]

        pedido = """TAREFA
Diga a jogada em no máximo 12 palavras, e o motivo em no máximo 15.
Se houver perigo imediato, use "alerta" (senão deixe vazio).

JSON:
{"acao": "...", "motivo": "...", "atacar": true/false/null, "alerta": "..."}"""

        inicio = time.monotonic()
        dados = self.cliente.perguntar_json(
            sistema=SISTEMA_RAPIDO,
            usuario=contexto + pedido,
            max_tokens=1200,
            rapido=True,
        )
        duracao = time.monotonic() - inicio

        recomendacao = RecomendacaoRapida(
            acao=dados.get("acao", ""),
            motivo=dados.get("motivo", ""),
            atacar=dados.get("atacar"),
            alerta=dados.get("alerta", "") or "",
            segundos=duracao,
        )
        self._cache_rapido[assinatura] = recomendacao
        return recomendacao

    @staticmethod
    def _assinatura(estado: GameState) -> str:
        """Resume o board numa string, pra saber se algo mudou de verdade.

        Inclui turno, fase, vidas, mana e as cartas de cada zona com o estado
        de virada. Se nada disso mudou, a decisão é a mesma e não faz sentido
        pagar outra chamada de IA.

        Args:
            estado: Estado da partida.

        Returns:
            Assinatura do board.
        """
        def resumir(cartas: list) -> str:
            return ",".join(
                sorted(f"{c.carta.nome_en}{'*' if c.virada else ''}" for c in cartas)
            )

        return "|".join(
            [
                str(estado.turno),
                estado.etapa or estado.fase,
                str(estado.minha_vida),
                str(estado.vida_oponente),
                str(estado.mana_disponivel().get("total", 0)),
                resumir(estado.minha_mao),
                resumir(estado.meu_campo),
                resumir(estado.campo_oponente),
            ]
        )

    def _texto_das_cartas(self, estado: GameState) -> str:
        """Monta a ficha técnica das cartas em jogo, com o texto oficial.

        Esta seção existe por causa de um erro concreto: sem ela, a IA
        afirmou que "Nest Robber tem menace" (tem ímpeto) e ignorou que o
        bloqueador tinha voar. Recomendou um ataque ruim com 90% de
        confiança.

        Mandar o texto de regras junto troca "o que o modelo lembra da carta"
        por "o que a carta faz". É a mesma diferença entre citar uma bula de
        memória e ler a bula.

        Args:
            estado: Estado da partida.

        Returns:
            Bloco de texto com a ficha de cada carta relevante.
        """
        relevantes = (
            estado.minha_mao
            + estado.meu_campo
            + estado.campo_oponente
            + estado.cemiterio_oponente
        )
        # Terreno básico não precisa de ficha: todo mundo sabe o que faz, e
        # numa partida eles são a maioria das cartas em jogo.
        nomes = sorted(
            {
                c.carta.nome_en
                for c in relevantes
                if c.carta.nome_en
                and not (c.eh_terreno and "SuperType_Basic" in c.subtipos)
                and c.carta.nome_en not in ("Plains", "Island", "Swamp", "Mountain", "Forest")
            }
        )
        if not nomes:
            return ""

        fichas = self.textos.buscar_varias(nomes)
        if not fichas:
            return ""

        linhas = [
            "FICHA OFICIAL DAS CARTAS (texto de regras verificado)",
            "",
            "COMO USAR ESTA SEÇÃO:",
            "1. O TEXTO DE REGRAS aqui é a verdade. Use ele, não sua memória "
            "da carta. Se uma habilidade não estiver listada, a carta NÃO a tem.",
            "2. O poder/resistência aqui é o BASE IMPRESSO. Ele NÃO vale pra "
            "conta de combate.",
            "   Para combate, use SEMPRE o poder/resistência que aparece na "
            "descrição do board mais abaixo — aquele é o valor ATUAL, já com "
            "todos os buffs, auras e efeitos aplicados.",
            "   Exemplo do erro a evitar: se a ficha diz 4/3 e o board diz 5/3, "
            "a criatura É 5/3. Nunca some os dois, nunca invente um terceiro valor.",
            "",
        ]
        for nome in nomes:
            ficha = fichas.get(nome)
            if ficha is None:
                linhas.append(f"- {nome}: (texto não encontrado — seja cauteloso)")
                continue

            partes = [ficha.nome]
            if ficha.custo:
                partes.append(ficha.custo)
            if ficha.tipo:
                partes.append(f"— {ficha.tipo}")
            cabecalho = " ".join(partes)

            if ficha.poder:
                cabecalho += f" (base impressa: {ficha.poder}/{ficha.resistencia})"
            if ficha.keywords:
                cabecalho += f" [keywords: {', '.join(ficha.keywords)}]"

            corpo = f": {ficha.texto.replace(chr(10), ' / ')}" if ficha.texto else ""
            linhas.append(f"- {cabecalho}{corpo}")

        return "\n".join(linhas)

    def _montar_pergunta(
        self,
        estado: GameState,
        oponente: AnaliseDoOponente | None,
        formato: str,
    ) -> str:
        """Monta o texto enviado à IA.

        Args:
            estado: Estado da partida.
            oponente: Análise do oponente, se houver.
            formato: Formato do jogo.

        Returns:
            A pergunta pronta.
        """
        mana = estado.mana_disponivel()
        cores_com_mana = ", ".join(
            f"{cor}:{qtd}"
            for cor, qtd in mana.items()
            if cor not in ("total",) and qtd > 0
        )

        def detalhar(cartas: list) -> str:
            """Descreve cartas com o que importa pra decisão de combate."""
            if not cartas:
                return "(nada)"
            partes = []
            for c in cartas:
                texto = c.carta.nome_en
                if c.poder_atual:
                    # "ATUAL" explícito porque a ficha do Scryfall traz o valor
                    # base impresso, e a IA já confundiu os dois: chamou de 6/4
                    # uma criatura de base 4/3 que estava 5/3 no board.
                    texto += f" (ATUAL {c.poder_atual}/{c.resistencia_atual}"
                    if c.dano:
                        texto += f", {c.dano} de dano marcado"
                    texto += ")"
                marcas = []
                if c.virada:
                    marcas.append("virada")
                if c.enjoada:
                    marcas.append("enjoada, não pode atacar")
                if c.atacando:
                    marcas.append("atacando")
                if marcas:
                    texto += f" [{'; '.join(marcas)}]"
                partes.append(texto)
            return "; ".join(partes)

        contexto_oponente = "Deck do oponente ainda não identificado."
        if oponente and oponente.principal.nome:
            ameacas = ", ".join(
                f"{a.carta} ({a.probabilidade:.0%})" for a in oponente.ameacas[:4]
            )
            contexto_oponente = f"""Deck provável: {oponente.principal.nome} \
({oponente.principal.confianca:.0%} de confiança)
Arquétipo: {oponente.principal.arquetipo}
Ameaças esperadas: {ameacas or 'nenhuma mapeada'}"""

        podem_atacar = estado.criaturas_que_podem_atacar()
        podem_bloquear = estado.criaturas_que_podem_bloquear()

        return f"""SITUAÇÃO ATUAL

{self._texto_das_cartas(estado)}

Formato: {formato} | Jogo {estado.numero_do_jogo} | Turno {estado.turno}
Fase: {estado.etapa or estado.fase or 'desconhecida'}
Turno de quem: {'MEU' if estado.jogador_ativo == estado.meu_seat else 'DO OPONENTE'}

VIDAS
Eu: {estado.minha_vida}
Oponente: {estado.vida_oponente}

MINHA MANA DISPONÍVEL
Total: {mana.get('total', 0)} terreno(s) desvirado(s)
Por cor: {cores_com_mana or 'nenhuma'}

MINHA MÃO ({len(estado.minha_mao)} cartas)
{detalhar(estado.minha_mao)}

MEU CAMPO
{detalhar(estado.meu_campo)}

CRIATURAS MINHAS QUE PODEM ATACAR AGORA
{detalhar(podem_atacar) if podem_atacar else '(nenhuma)'}

CAMPO DO OPONENTE
{detalhar(estado.campo_oponente)}

CRIATURAS DELE QUE PODEM BLOQUEAR
{detalhar(podem_bloquear) if podem_bloquear else '(nenhuma — campo livre)'}

CEMITÉRIO DELE
{detalhar(estado.cemiterio_oponente)}

SOBRE O OPONENTE
{contexto_oponente}

TAREFA
Recomende a jogada. Seja concreto e cite as cartas pelo nome.

Regras da sua análise:
- Considere a mana REAL disponível: não recomende o que não dá pra pagar.
- Criatura enjoada não pode atacar. Criatura virada não bloqueia.
- Se for fase em que não se ataca, deixe "should_attack" como null.
- Diga o que você DESCARTOU e por quê — o jogador precisa julgar, não obedecer.
- Toda jogada tem risco. Se não enxergar nenhum, você não pensou o bastante.
- Se a informação for insuficiente pra decidir, diga isso em vez de inventar.

RESPONDA APENAS COM ESTE JSON, sem texto antes ou depois:
{{
  "summary": "a recomendação em uma frase",
  "sequence": [
    {{"action": "o que fazer", "cards": ["nome em inglês"], "priority": 1,
      "reason": "por quê", "risk": "o que pode dar errado"}}
  ],
  "should_attack": true/false/null,
  "attack_with": ["nomes das criaturas que devem atacar"],
  "attack_reasoning": "por que atacar ou não",
  "hold_mana": true/false,
  "hold_mana_reasoning": "por que segurar mana ou não",
  "rejected_alternatives": ["considerei X mas descartei porque Y"],
  "warning": "alerta urgente, ou string vazia",
  "confidence": 0.0 a 1.0
}}"""

    @staticmethod
    def _interpretar(dados: dict) -> RecomendacaoDeJogada:
        """Converte o JSON da IA no nosso modelo.

        Args:
            dados: JSON devolvido pela IA.

        Returns:
            A recomendação estruturada.
        """
        sequencia = [
            Jogada(
                acao=item.get("action", ""),
                cartas=item.get("cards", []) or [],
                prioridade=int(item.get("priority", 0) or 0),
                motivo=item.get("reason", ""),
                risco=item.get("risk", ""),
            )
            for item in dados.get("sequence", []) or []
        ]
        sequencia.sort(key=lambda j: j.prioridade or 99)

        return RecomendacaoDeJogada(
            resumo=dados.get("summary", ""),
            sequencia=sequencia,
            atacar=dados.get("should_attack"),
            com_quais_atacar=dados.get("attack_with", []) or [],
            motivo_do_ataque=dados.get("attack_reasoning", ""),
            segurar_mana=bool(dados.get("hold_mana", False)),
            motivo_da_mana=dados.get("hold_mana_reasoning", ""),
            alternativas_descartadas=dados.get("rejected_alternatives", []) or [],
            alerta=dados.get("warning", "") or "",
            confianca=float(dados.get("confidence", 0) or 0),
        )
