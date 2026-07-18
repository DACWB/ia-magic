"""Leitura do Player.log do MTG Arena — substitui OBS + OCR.

Este módulo é a Camada 1 (captura) e a Camada 2 (interpretação) do sistema,
fundidas num arquivo só. E não gasta um único token de API.

## Por que ler o log em vez de olhar a tela

O Arena escreve no `Player.log` todo o estado da partida em JSON, com os IDs
numéricos exatos de cada carta. Fazer OCR da tela pra descobrir o que o log
já entrega mastigado seria como transcrever à mão o laudo impresso quando o
laboratório expõe o resultado via API.

## O detalhe que mais confunde: as mensagens são INCREMENTAIS

O Arena manda `GameStateType_Diff` — cada mensagem contém só *o que mudou*.
Um exemplo real de `turnInfo` que veio no log da partida de teste:

    {"activePlayer": 2, "decisionPlayer": 2}

Repare: **não tem o número do turno.** Ele veio numa mensagem anterior e não
mudou. Se você ler cada mensagem isoladamente, o turno some.

Por isso este parser ACUMULA: mantém o estado e vai aplicando as mudanças por
cima, como um extrato bancário — cada linha é uma movimentação, e o saldo é a
soma de tudo até agora.
"""

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.models.game_state import (
    ZONAS_DO_ARENA,
    CartaEmJogo,
    GameState,
    Jogador,
    ResultadoPartida,
    Zona,
)
from src.services.arena_card_db import BancoDeCartasArena
from src.services.arena_paths import caminho_do_log


def extrair_objetos_json(texto: str) -> Iterator[dict[str, Any]]:
    """Extrai todo objeto JSON de nível superior de dentro do log.

    O Player.log não é um JSON — é um log de texto com blocos JSON espalhados
    no meio de mensagens da Unity. Não dá pra fazer `json.loads` no arquivo.

    A solução é varrer o texto contando chaves `{` e `}` até fechar o bloco.
    O cuidado essencial: ignorar chaves que estejam DENTRO de uma string.
    Um texto de carta como `"Escolha {R} ou {G}"` derrubaria a contagem
    ingênua — e no Magic isso aparece o tempo todo, nos custos de mana.

    Args:
        texto: Conteúdo bruto do log.

    Yields:
        Cada objeto JSON válido encontrado, já convertido em dicionário.
    """
    posicao = 0
    tamanho = len(texto)

    while posicao < tamanho:
        if texto[posicao] != "{":
            posicao += 1
            continue

        profundidade = 0
        dentro_de_string = False
        escapado = False
        fim_encontrado = False

        for indice in range(posicao, tamanho):
            caractere = texto[indice]

            # Uma barra invertida faz o próximo caractere perder o sentido
            # especial — inclusive uma aspa. Sem isso, `"texto \" aqui"`
            # bagunçaria a contagem de aspas.
            if escapado:
                escapado = False
                continue
            if caractere == "\\":
                escapado = True
                continue
            if caractere == '"':
                dentro_de_string = not dentro_de_string
                continue
            if dentro_de_string:
                continue

            if caractere == "{":
                profundidade += 1
            elif caractere == "}":
                profundidade -= 1
                if profundidade == 0:
                    trecho = texto[posicao : indice + 1]
                    try:
                        yield json.loads(trecho)
                    except json.JSONDecodeError:
                        pass  # bloco truncado (log sendo escrito) — segue o baile
                    posicao = indice + 1
                    fim_encontrado = True
                    break

        if not fim_encontrado:
            # Bloco aberto que nunca fecha: fim do arquivo no meio da escrita
            break


def _buscar_recursivo(objeto: Any, chave: str, _profundidade: int = 0) -> Any:
    """Procura uma chave em qualquer nível de um dicionário aninhado.

    O Arena aninha as mensagens em profundidades diferentes conforme a versão
    do jogo. Buscar recursivamente deixa o parser resistente a essas mudanças
    — é a diferença entre quebrar a cada patch e continuar funcionando.

    Args:
        objeto: Dicionário, lista ou valor simples.
        chave: Nome da chave procurada.
        _profundidade: Controle interno de recursão.

    Returns:
        O primeiro valor encontrado, ou None.
    """
    if _profundidade > 12:  # trava de segurança contra estruturas circulares
        return None

    if isinstance(objeto, dict):
        if chave in objeto:
            return objeto[chave]
        for valor in objeto.values():
            achado = _buscar_recursivo(valor, chave, _profundidade + 1)
            if achado is not None:
                return achado
    elif isinstance(objeto, list):
        for item in objeto:
            achado = _buscar_recursivo(item, chave, _profundidade + 1)
            if achado is not None:
                return achado
    return None


def _coletar_recursivo(
    objeto: Any, chave: str, encontrados: list[Any] | None = None, _prof: int = 0
) -> list[Any]:
    """Como `_buscar_recursivo`, mas coleta TODAS as ocorrências.

    Args:
        objeto: Estrutura a percorrer.
        chave: Nome da chave procurada.
        encontrados: Acumulador interno.
        _prof: Controle interno de recursão.

    Returns:
        Lista com todos os valores encontrados.
    """
    if encontrados is None:
        encontrados = []
    if _prof > 12:
        return encontrados

    if isinstance(objeto, dict):
        for nome, valor in objeto.items():
            if nome == chave:
                encontrados.append(valor)
            _coletar_recursivo(valor, chave, encontrados, _prof + 1)
    elif isinstance(objeto, list):
        for item in objeto:
            _coletar_recursivo(item, chave, encontrados, _prof + 1)
    return encontrados


class LeitorDeLogArena:
    """Transforma o Player.log em um `GameState` sempre atualizado.

    Uso típico:
        leitor = LeitorDeLogArena()
        estado = leitor.ler_arquivo_inteiro()
        print(f"{estado.minha_vida} x {estado.vida_oponente}")

    Attributes:
        estado: O GameState acumulado até agora.
    """

    def __init__(
        self,
        caminho_log: Path | None = None,
        banco: BancoDeCartasArena | None = None,
    ) -> None:
        """Prepara o leitor.

        Args:
            caminho_log: Caminho do Player.log. Se None, descobre sozinho.
            banco: Banco de cartas do Arena. Se None, abre sozinho.
        """
        self.caminho_log: Path = caminho_log or caminho_do_log()
        self.banco: BancoDeCartasArena = banco or BancoDeCartasArena()
        self.estado: GameState = GameState()

        # Jogos JÁ ENCERRADOS desta sessão, em ordem.
        # Não é luxo: num BO3, decidir o sideboard exige lembrar o que o
        # oponente mostrou no jogo 1. É a Fase 3 do projeto.
        self.jogos_anteriores: list[GameState] = []

        # zoneId -> Zona. Precisa ser acumulado: o gameObject diz em que
        # zoneId está, mas só uma mensagem anterior disse o que aquele
        # zoneId significa.
        self._zonas: dict[int, Zona] = {}
        self._donos_de_zona: dict[int, int] = {}

        # Quantas ações o cliente enviou em nome de cada assento, no jogo
        # atual. É assim que descobrimos de que lado da mesa o jogador está.
        self._acoes_por_assento: Counter[int] = Counter()

        # Posição de leitura, pro modo de acompanhamento em tempo real
        self._posicao_lida: int = 0

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    def ler_arquivo_inteiro(self) -> GameState:
        """Lê o log do começo e devolve o estado final acumulado.

        Use pra analisar uma partida que já terminou.

        Returns:
            O GameState resultante.
        """
        texto = self.caminho_log.read_text(encoding="utf-8", errors="replace")
        self._posicao_lida = len(texto)
        for objeto in extrair_objetos_json(texto):
            self.processar(objeto)
        return self.estado

    def ler_novidades(self) -> GameState:
        """Lê só o que foi escrito no log desde a última leitura.

        É o modo "tempo real": chame de tempos em tempos (a cada 1s, por
        exemplo) e o estado vai se atualizando conforme você joga.

        O log só cresce durante a sessão, então basta continuar de onde
        paramos. Se o arquivo encolher, o Arena foi reiniciado e recomeçamos.

        Returns:
            O GameState atualizado.
        """
        tamanho_atual = self.caminho_log.stat().st_size

        if tamanho_atual < self._posicao_lida:
            # Log rotacionado (Arena reiniciou): zera tudo e lê de novo
            self._posicao_lida = 0
            self.estado = GameState()
            self.jogos_anteriores.clear()
            self._zonas.clear()
            self._donos_de_zona.clear()
            self._acoes_por_assento.clear()

        if tamanho_atual == self._posicao_lida:
            return self.estado  # nada novo

        with self.caminho_log.open("r", encoding="utf-8", errors="replace") as arquivo:
            arquivo.seek(self._posicao_lida)
            novo_texto = arquivo.read()

        self._posicao_lida = tamanho_atual
        for objeto in extrair_objetos_json(novo_texto):
            self.processar(objeto)
        return self.estado

    # ------------------------------------------------------------------
    # Processamento
    # ------------------------------------------------------------------

    def processar(self, objeto: dict[str, Any]) -> None:
        """Aplica um objeto JSON do log sobre o estado acumulado.

        Args:
            objeto: Um bloco JSON extraído do log.
        """
        self._registrar_assento(objeto)

        # Cada objeto pode trazer várias mensagens de estado
        for mensagem in _coletar_recursivo(objeto, "gameStateMessage"):
            if isinstance(mensagem, dict):
                self._aplicar_estado(mensagem)

        # Resultado final da partida
        resultado = _buscar_recursivo(objeto, "finalMatchResult")
        if isinstance(resultado, dict):
            self._aplicar_resultado(resultado)

    def _aplicar_estado(self, mensagem: dict[str, Any]) -> None:
        """Aplica um `gameStateMessage` sobre o estado.

        Args:
            mensagem: O conteúdo de `gameStateMessage`.
        """
        # `GameStateType_Full` = retrato COMPLETO do jogo, enviado quando um
        # jogo novo começa. Tudo que estava acumulado é do jogo anterior e
        # precisa sair da frente.
        #
        # Ignorar isso causou um bug real: numa sessão com dois jogos, os
        # assentos trocaram de lado (quem era o deck vermelho no assento 1
        # virou assento 2 no jogo seguinte) e o parser fundiu os dois — as
        # cartas do próprio jogador apareceram como sendo do oponente.
        if mensagem.get("type") == "GameStateType_Full":
            self._iniciar_novo_jogo()

        self._aplicar_zonas(mensagem.get("zones", []))
        self._aplicar_jogadores(mensagem.get("players", []))
        self._aplicar_turno(mensagem.get("turnInfo", {}))
        self._aplicar_objetos(mensagem.get("gameObjects", []))

    def _registrar_assento(self, objeto: dict[str, Any]) -> None:
        """Descobre de que lado da mesa o jogador local está.

        A intuição errada (que eu tive primeiro) é usar `systemSeatIds` do
        `greToClientEvent`. Mas esse campo é a lista de DESTINATÁRIOS da
        mensagem, não a identidade do jogador — no log de teste ele aparecia
        como `[1]`, `[2]` e `[1, 2]` alternadamente.

        O sinal certo é: **de que assento partiram as ações enviadas pelo
        cliente** (`clientToMatchServiceMessage`). Quem clica é você.

        A ressalva: em modos contra a máquina (Desafio de Cores, tutorial), o
        cliente joga os DOIS lados, e aí aparecem ações dos dois assentos.
        Por isso decidimos por maioria — no log de teste, 381 ações do
        assento 1 contra 158 do assento 2, e o assento 1 era de fato o do
        jogador. Numa partida online normal só existe um assento, e a
        maioria é unânime.

        Args:
            objeto: Bloco JSON do log.
        """
        if "clientToMatchServiceMessageType" not in objeto:
            return

        for assento in _coletar_recursivo(objeto, "systemSeatId"):
            if isinstance(assento, int):
                self._acoes_por_assento[assento] += 1

        if self._acoes_por_assento:
            self.estado.meu_seat = self._acoes_por_assento.most_common(1)[0][0]

    def _iniciar_novo_jogo(self) -> None:
        """Arquiva o jogo atual e começa um estado limpo.

        O que se preserva e o que se descarta:

        - **Descarta** cartas e mapa de zonas: são daquele jogo. Os
          `instanceId` e `zoneId` são renumerados a cada jogo novo.
        - **Preserva** o assento do jogador local como palpite inicial, mas
          o próprio `GameStateType_Full` costuma trazer `systemSeatIds` de
          novo — e nesse caso o valor correto sobrescreve o palpite.
        """
        if self.estado.cartas:  # não arquiva estado vazio
            self.jogos_anteriores.append(self.estado)

        self.estado = GameState(
            numero_do_jogo=len(self.jogos_anteriores) + 1,
            meu_seat=self.estado.meu_seat,
        )
        self._zonas.clear()
        self._donos_de_zona.clear()
        # Zera a contagem: no jogo seguinte o jogador pode estar no OUTRO
        # assento. Foi exatamente o que aconteceu no log de teste — o deck
        # vermelho saiu do assento 1 e foi pro 2.
        self._acoes_por_assento.clear()

    def _aplicar_zonas(self, zonas: list[dict[str, Any]]) -> None:
        """Registra o que cada `zoneId` significa.

        Args:
            zonas: Lista de zonas da mensagem.
        """
        for zona in zonas:
            zona_id = zona.get("zoneId")
            if zona_id is None:
                continue
            tipo = zona.get("type", "")
            if tipo:
                self._zonas[zona_id] = ZONAS_DO_ARENA.get(tipo, Zona.DESCONHECIDA)
            dono = zona.get("ownerSeatId")
            if dono is not None:
                self._donos_de_zona[zona_id] = dono

    def _aplicar_jogadores(self, jogadores: list[dict[str, Any]]) -> None:
        """Atualiza vida e dados dos jogadores.

        Só sobrescreve campos que vieram na mensagem — o resto se mantém,
        porque as mensagens são incrementais.

        Args:
            jogadores: Lista de jogadores da mensagem.
        """
        for dados in jogadores:
            seat = dados.get("systemSeatNumber") or dados.get("controllerSeatId")
            if seat is None:
                continue

            jogador = self.estado.jogadores.get(seat) or Jogador(seat=seat)
            if "lifeTotal" in dados:
                jogador.vida = dados["lifeTotal"]
            if "startingLifeTotal" in dados:
                jogador.vida_inicial = dados["startingLifeTotal"]
            if "teamId" in dados:
                jogador.team_id = dados["teamId"]
            if "maxHandSize" in dados:
                jogador.tamanho_maximo_mao = dados["maxHandSize"]
            self.estado.jogadores[seat] = jogador

    def _aplicar_turno(self, turno: dict[str, Any]) -> None:
        """Atualiza turno, fase e etapa.

        Aqui está o exemplo mais claro de por que acumular: uma mensagem real
        do log trouxe só `{"activePlayer": 2, "decisionPlayer": 2}`. Se a
        gente sobrescrevesse o turno com o que veio (nada), ele voltaria a 0.

        Args:
            turno: O conteúdo de `turnInfo`.
        """
        if "turnNumber" in turno:
            self.estado.turno = turno["turnNumber"]
        if "phase" in turno:
            self.estado.fase = turno["phase"]
        if "step" in turno:
            self.estado.etapa = turno["step"]
        if "activePlayer" in turno:
            self.estado.jogador_ativo = turno["activePlayer"]

    def _aplicar_objetos(self, objetos: list[dict[str, Any]]) -> None:
        """Atualiza as cartas: onde estão, quem controla, poder atual.

        Args:
            objetos: Lista de `gameObjects` da mensagem.
        """
        for dados in objetos:
            instance_id = dados.get("instanceId")
            grp_id = dados.get("grpId")
            if instance_id is None or grp_id is None:
                continue

            carta = self.banco.buscar(grp_id)
            if carta is None:
                continue  # emblema, efeito, objeto interno do jogo

            zona_id = dados.get("zoneId")
            zona = self._zonas.get(zona_id, Zona.DESCONHECIDA) if zona_id else Zona.DESCONHECIDA

            # O poder/resistência ATUAL vem como {"value": 3} e já considera
            # os buffs em jogo (um Goblin 1/1 com Bombardeio vira 2/1 aqui).
            poder = dados.get("power", {})
            resistencia = dados.get("toughness", {})

            existente = self.estado.cartas.get(instance_id)
            if existente is None:
                existente = CartaEmJogo(instance_id=instance_id, carta=carta)

            existente.carta = carta
            existente.zona = zona
            if "ownerSeatId" in dados:
                existente.dono_seat = dados["ownerSeatId"]
            if "controllerSeatId" in dados:
                existente.controlador_seat = dados["controllerSeatId"]
            if isinstance(poder, dict) and "value" in poder:
                existente.poder_atual = str(poder["value"])
            if isinstance(resistencia, dict) and "value" in resistencia:
                existente.resistencia_atual = str(resistencia["value"])
            existente.virada = bool(dados.get("isTapped", existente.virada))

            self.estado.cartas[instance_id] = existente

    def _aplicar_resultado(self, resultado: dict[str, Any]) -> None:
        """Registra quem venceu a partida.

        O log diz `winningTeamId`, não `winningSeat`. Pra saber se fui eu,
        preciso cruzar com o `teamId` do meu assento — foi assim que o sistema
        detectou sozinho a derrota na partida de teste.

        Args:
            resultado: O conteúdo de `finalMatchResult`.
        """
        lista = resultado.get("resultList", [])
        # O escopo "Match" é o resultado da partida toda (não do game isolado)
        do_match = next(
            (r for r in lista if r.get("scope") == "MatchScope_Match"),
            lista[-1] if lista else None,
        )
        if not do_match:
            return

        time_vencedor = do_match.get("winningTeamId")
        meu_jogador = self.estado.jogadores.get(self.estado.meu_seat or -1)
        eu_venci = (
            (meu_jogador.team_id == time_vencedor)
            if (meu_jogador and time_vencedor is not None)
            else None
        )

        self.estado.resultado = ResultadoPartida(
            match_id=resultado.get("matchId", ""),
            time_vencedor=time_vencedor,
            eu_venci=eu_venci,
            motivo=do_match.get("reason", ""),
        )
