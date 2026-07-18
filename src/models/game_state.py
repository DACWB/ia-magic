"""Modelos que representam o estado de uma partida de Magic.

Estes são os "substantivos" do sistema. Toda camada acima (IA, dashboard)
conversa nesta linguagem, e nenhuma delas precisa saber que os dados vieram
de um log da Unity cheio de JSON.

Analogia clínica: é a diferença entre o dado bruto do aparelho e o registro
estruturado no prontuário. A IA lê o prontuário, não o cabo do aparelho.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Zona(str, Enum):
    """Onde uma carta está no jogo.

    O Arena usa nomes como `ZoneType_Hand`. Traduzimos para um vocabulário
    nosso, curto e em português, para o resto do sistema não depender do
    formato interno do jogo.
    """

    MAO = "mao"
    CAMPO = "campo"
    CEMITERIO = "cemiterio"
    EXILIO = "exilio"
    BIBLIOTECA = "biblioteca"
    PILHA = "pilha"
    COMANDO = "comando"
    LIMBO = "limbo"
    DESCONHECIDA = "desconhecida"


# Tradução dos nomes internos do Arena para o nosso vocabulário
ZONAS_DO_ARENA: dict[str, Zona] = {
    "ZoneType_Hand": Zona.MAO,
    "ZoneType_Battlefield": Zona.CAMPO,
    "ZoneType_Graveyard": Zona.CEMITERIO,
    "ZoneType_Exile": Zona.EXILIO,
    "ZoneType_Library": Zona.BIBLIOTECA,
    "ZoneType_Stack": Zona.PILHA,
    "ZoneType_Command": Zona.COMANDO,
    "ZoneType_Limbo": Zona.LIMBO,
    "ZoneType_Revealed": Zona.LIMBO,
    "ZoneType_Sideboard": Zona.LIMBO,
    "ZoneType_Pending": Zona.LIMBO,
}


class Carta(BaseModel):
    """Identidade de uma carta, vinda do banco do próprio Arena.

    Attributes:
        grp_id: ID numérico da carta no Arena. É o mesmo em qualquer idioma —
            por isso jogar em português não custa nada ao sistema.
        nome_en: Nome em inglês. É este que mandamos pra IA, porque toda a
            literatura estratégica de Magic é em inglês.
        nome_pt: Nome em português. É este que mostramos pro jogador.
        tipo: Linha de tipo ("Criatura — Ogro Guerreiro").
        poder: Poder impresso, como texto (pode ser "*").
        resistencia: Resistência impressa, como texto.
        raridade: Código numérico de raridade do Arena.
        colecao: Código da coleção (ex.: "FDN", "DMU").
    """

    grp_id: int
    nome_en: str
    nome_pt: str = ""
    tipo: str = ""
    poder: str = ""
    resistencia: str = ""
    raridade: int = 0
    colecao: str = ""

    def nome(self, idioma: str = "ptBR") -> str:
        """Devolve o nome no idioma pedido, caindo pro inglês se faltar.

        Args:
            idioma: "ptBR" ou "enUS".

        Returns:
            O nome da carta.
        """
        if idioma == "ptBR" and self.nome_pt:
            return self.nome_pt
        return self.nome_en


class CartaEmJogo(BaseModel):
    """Uma carta específica em uma partida específica.

    A diferença entre `Carta` e `CartaEmJogo`: você pode ter quatro cópias de
    Choque no deck. Todas compartilham o mesmo `grp_id` (mesma carta), mas cada
    uma tem seu próprio `instance_id` (aquele objeto ali, naquela zona).

    É a distinção entre "o medicamento Losartana" e "o comprimido que este
    paciente tomou às 8h".

    Attributes:
        instance_id: ID único deste objeto nesta partida.
        carta: Identidade da carta.
        zona: Onde está agora.
        dono_seat: Assento de quem é dono da carta.
        controlador_seat: Assento de quem controla agora (pode diferir do dono
            se houve roubo de criatura, por exemplo).
        virada: Se está virada (tapped).
        poder_atual: Poder considerando buffs em jogo.
        resistencia_atual: Resistência considerando buffs em jogo.
    """

    instance_id: int
    carta: Carta
    zona: Zona = Zona.DESCONHECIDA
    dono_seat: int | None = None
    controlador_seat: int | None = None
    virada: bool = False
    poder_atual: str = ""
    resistencia_atual: str = ""


class Jogador(BaseModel):
    """Um dos dois jogadores da partida.

    Attributes:
        seat: Número do assento (1 ou 2).
        team_id: Time do jogador — é o que o resultado final referencia.
        vida: Total de vida atual.
        vida_inicial: Vida com que começou (normalmente 20).
        tamanho_maximo_mao: Limite de cartas na mão.
    """

    seat: int
    team_id: int = 0
    vida: int = 20
    vida_inicial: int = 20
    tamanho_maximo_mao: int = 7


class ResultadoPartida(BaseModel):
    """Como a partida terminou.

    Attributes:
        match_id: Identificador da partida.
        time_vencedor: `team_id` de quem venceu.
        eu_venci: True se o jogador local venceu.
        motivo: Motivo do encerramento, como o Arena reporta.
    """

    match_id: str = ""
    time_vencedor: int | None = None
    eu_venci: bool | None = None
    motivo: str = ""


class GameState(BaseModel):
    """Fotografia completa da partida em um instante.

    Este é o objeto que a Camada 4 (IA) recebe pra decidir a jogada, e que a
    Camada 5 (dashboard) recebe pra desenhar a tela.

    Attributes:
        numero_do_jogo: 1 para o primeiro jogo da partida, 2 para o segundo,
            etc. Num BO3 cada jogo é um GameState separado — e os assentos
            podem trocar entre eles.
        meu_seat: Assento do jogador local NESTE jogo.
        turno: Número do turno.
        fase: Fase atual, como o Arena reporta.
        etapa: Etapa dentro da fase.
        jogador_ativo: Assento de quem está com o turno.
        jogadores: Jogadores indexados por assento.
        cartas: Todas as cartas conhecidas, indexadas por instance_id.
        resultado: Preenchido quando a partida termina.
    """

    numero_do_jogo: int = 1
    meu_seat: int | None = None
    turno: int = 0
    fase: str = ""
    etapa: str = ""
    jogador_ativo: int | None = None
    jogadores: dict[int, Jogador] = Field(default_factory=dict)
    cartas: dict[int, CartaEmJogo] = Field(default_factory=dict)
    resultado: ResultadoPartida | None = None

    # --- Atalhos de leitura (o que a IA e a UI realmente perguntam) ---

    @property
    def seat_oponente(self) -> int | None:
        """Assento do oponente, deduzido a partir do meu."""
        if self.meu_seat is None:
            return None
        return next(
            (s for s in self.jogadores if s != self.meu_seat),
            2 if self.meu_seat == 1 else 1,
        )

    @property
    def minha_vida(self) -> int:
        """Vida do jogador local."""
        jogador = self.jogadores.get(self.meu_seat or -1)
        return jogador.vida if jogador else 0

    @property
    def vida_oponente(self) -> int:
        """Vida do oponente."""
        jogador = self.jogadores.get(self.seat_oponente or -1)
        return jogador.vida if jogador else 0

    def cartas_em(self, zona: Zona, seat: int | None) -> list[CartaEmJogo]:
        """Lista as cartas de um jogador em uma zona.

        Args:
            zona: Zona procurada.
            seat: Assento do jogador dono/controlador.

        Returns:
            Cartas encontradas, ordenadas por nome pra saída estável.
        """
        if seat is None:
            return []
        # No campo o que importa é quem CONTROLA; nas outras zonas, quem é DONO
        campo_relevante = "controlador_seat" if zona is Zona.CAMPO else "dono_seat"
        encontradas = [
            c
            for c in self.cartas.values()
            if c.zona is zona and getattr(c, campo_relevante) == seat
        ]
        return sorted(encontradas, key=lambda c: c.carta.nome_en)

    @property
    def minha_mao(self) -> list[CartaEmJogo]:
        """Cartas na minha mão."""
        return self.cartas_em(Zona.MAO, self.meu_seat)

    @property
    def meu_campo(self) -> list[CartaEmJogo]:
        """Minhas permanentes em jogo."""
        return self.cartas_em(Zona.CAMPO, self.meu_seat)

    @property
    def campo_oponente(self) -> list[CartaEmJogo]:
        """Permanentes do oponente em jogo."""
        return self.cartas_em(Zona.CAMPO, self.seat_oponente)

    @property
    def cemiterio_oponente(self) -> list[CartaEmJogo]:
        """Cemitério do oponente — a melhor pista do deck dele."""
        return self.cartas_em(Zona.CEMITERIO, self.seat_oponente)

    def cartas_reveladas_do_oponente(self) -> list[CartaEmJogo]:
        """Tudo que o oponente já mostrou: campo, cemitério, exílio e pilha.

        É exatamente isso que a Camada 4 usa pra identificar o deck dele.
        Não inclui a mão do oponente — informação oculta continua oculta,
        do mesmo jeito que estaria numa mesa física.

        Returns:
            Cartas visíveis do oponente.
        """
        seat = self.seat_oponente
        zonas_publicas = (Zona.CAMPO, Zona.CEMITERIO, Zona.EXILIO, Zona.PILHA)
        return [c for z in zonas_publicas for c in self.cartas_em(z, seat)]
