"""Camada única de conversa com o Claude.

Todo pedido de IA do sistema passa por aqui: identificar deck, recomendar
jogada, escolher pick de Draft, montar sideboard. Centralizar tem três
motivos práticos:

1. **Parâmetros por modelo.** Opus 4.8 recusa `temperature`; Haiku aceita.
   Espalhar essa regra por seis serviços é garantia de erro 400 em produção.
2. **Contagem de gasto.** Você precisa saber quanto custou a noite de jogo.
   Se cada serviço chamar a API direto, não há onde somar.
3. **Leitura da resposta.** A IA às vezes escreve "Aqui está a análise:"
   antes do JSON. O tratamento disso fica num lugar só.
"""

import re
from pathlib import Path

from anthropic import Anthropic, APIError

from src.utils.config import DIRETORIO_RAIZ, config
from src.utils.json_solto import maior_objeto_json

PASTA_DE_PROMPTS: Path = DIRETORIO_RAIZ / "prompts"


class RespostaInvalida(RuntimeError):
    """A IA respondeu, mas não no formato que pedimos."""


def carregar_prompt(nome: str) -> str:
    """Lê o system prompt de um arquivo em `prompts/`.

    Os prompts moram em markdown, não em Python, de propósito: assim o jogador
    ajusta o comportamento da IA sem mexer em código — e os alunos conseguem
    ler o "raciocínio" do sistema sem saber programar.

    O arquivo tem estrutura documental (títulos, exemplos, notas). O que
    interessa é o primeiro bloco de código depois do título `## System
    Prompt`.

    Args:
        nome: Nome do arquivo sem extensão (ex.: "deck-identifier").

    Returns:
        O texto do system prompt.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        ValueError: Se não houver bloco de System Prompt no arquivo.
    """
    arquivo = PASTA_DE_PROMPTS / f"{nome}.md"
    if not arquivo.exists():
        raise FileNotFoundError(
            f"Prompt '{nome}' não encontrado em {PASTA_DE_PROMPTS}"
        )

    texto = arquivo.read_text(encoding="utf-8")

    # Pega o primeiro bloco ``` depois do cabeçalho "## System Prompt"
    achado = re.search(
        r"##\s*System Prompt\s*\n+```[a-z]*\n(.*?)```",
        texto,
        re.DOTALL | re.IGNORECASE,
    )
    if not achado:
        raise ValueError(
            f"O arquivo {arquivo.name} não tem um bloco '## System Prompt'. "
            "Adicione o prompt dentro de ``` logo abaixo desse título."
        )
    return achado.group(1).strip()


class ClienteClaude:
    """Fala com o Claude e devolve resposta já tratada.

    Uso:
        cliente = ClienteClaude()
        dados = cliente.perguntar_json(
            sistema=carregar_prompt("deck-identifier"),
            usuario="Cartas visíveis: Island, Cloudkin Seer...",
        )
        print(dados["identified_deck"]["name"])
        print(cliente.resumo_de_gasto())

    Attributes:
        chamadas: Quantas requisições foram feitas.
        tokens_entrada: Total de tokens enviados.
        tokens_saida: Total de tokens recebidos.
    """

    def __init__(self, modelo: str | None = None) -> None:
        """Prepara o cliente.

        Args:
            modelo: Modelo a usar. Se None, usa o principal do .env.

        Raises:
            RuntimeError: Se a chave da API não estiver configurada.
        """
        if not config.chave_api_configurada():
            raise RuntimeError(
                "ANTHROPIC_API_KEY ausente ou inválida no .env. "
                "Pegue sua chave em https://console.anthropic.com"
            )

        self.modelo: str = modelo or config.claude_model_primary
        self._cliente = Anthropic(api_key=config.anthropic_api_key)

        self.chamadas: int = 0
        self.tokens_entrada: int = 0
        self.tokens_saida: int = 0

    def perguntar(
        self,
        sistema: str,
        usuario: str,
        max_tokens: int | None = None,
        modelo: str | None = None,
        rapido: bool = False,
    ) -> str:
        """Faz uma pergunta e devolve o texto da resposta.

        Args:
            sistema: System prompt (o "papel" da IA).
            usuario: A pergunta em si, com os dados da partida.
            max_tokens: Teto de tokens na resposta.
            modelo: Sobrescreve o modelo desta chamada.
            rapido: Se True, usa o modelo e o esforço do modo rápido —
                pra conselho durante a partida, quando o relógio corre.

        Returns:
            O texto da resposta.

        Raises:
            APIError: Se a API falhar (rede, autenticação, limite).
        """
        if rapido:
            alvo = modelo or config.claude_model_rapido
            parametros = config.parametros_rapidos()
        else:
            alvo = modelo or self.modelo
            parametros = config.parametros_de_geracao(alvo)

        resposta = self._cliente.messages.create(
            model=alvo,
            max_tokens=max_tokens or config.claude_max_tokens_recommendation,
            system=sistema,
            messages=[{"role": "user", "content": usuario}],
            **parametros,  # type: ignore[arg-type]
        )

        self.chamadas += 1
        self.tokens_entrada += resposta.usage.input_tokens
        self.tokens_saida += resposta.usage.output_tokens

        # Com raciocínio adaptativo pode vir um bloco de pensamento ANTES do
        # texto. Por isso pegamos o último bloco de texto, não `content[0]`.
        blocos_de_texto = [
            bloco.text for bloco in resposta.content if hasattr(bloco, "text")
        ]
        if not blocos_de_texto:
            raise RespostaInvalida(
                f"A IA respondeu sem texto (stop_reason={resposta.stop_reason})"
            )
        return blocos_de_texto[-1]

    def perguntar_json(
        self,
        sistema: str,
        usuario: str,
        max_tokens: int | None = None,
        modelo: str | None = None,
        rapido: bool = False,
    ) -> dict:
        """Como `perguntar`, mas devolve a resposta já convertida em dicionário.

        A IA costuma obedecer quando pedimos JSON, mas às vezes embrulha em
        ```json ... ``` ou escreve uma frase antes. Em vez de brigar com o
        modelo, extraímos o JSON de dentro do texto — o mesmo tratamento que
        damos ao log do Arena.

        Args:
            sistema: System prompt.
            usuario: A pergunta.
            max_tokens: Teto de tokens na resposta.
            modelo: Sobrescreve o modelo desta chamada.
            rapido: Usa o modelo e esforço do modo rápido.

        Returns:
            A resposta como dicionário.

        Raises:
            RespostaInvalida: Se não houver JSON válido na resposta.
        """
        texto = self.perguntar(sistema, usuario, max_tokens, modelo, rapido)
        dados = maior_objeto_json(texto)

        if dados is None:
            raise RespostaInvalida(
                "A IA não devolveu JSON válido. Começo da resposta:\n"
                f"{texto[:400]}"
            )
        return dados

    def resumo_de_gasto(self) -> str:
        """Descreve quanto foi gasto até agora, em tokens.

        Deliberadamente em TOKENS e não em reais: o preço por token muda com
        o tempo e varia por modelo, e um número errado em dinheiro é pior que
        nenhum. Token é o que dá pra medir com honestidade aqui.

        Returns:
            Texto legível com o resumo.
        """
        return (
            f"{self.chamadas} chamada(s) | "
            f"{self.tokens_entrada:,} tokens de entrada | "
            f"{self.tokens_saida:,} de saída | modelo: {self.modelo}"
        )


__all__ = ["ClienteClaude", "RespostaInvalida", "carregar_prompt", "APIError"]
