"""Configuração central do sistema, carregada do arquivo .env.

Por que um módulo só pra isso? Porque assim NENHUM outro arquivo do projeto
precisa saber que existe um .env. Todos importam `config` e pronto. Se um dia
trocarmos .env por outra fonte (variáveis do sistema, arquivo YAML, etc.),
mudamos só aqui.

Esse é o mesmo princípio que usamos em sistemas clínicos: a camada de
configuração fica isolada da camada de regra de negócio.
"""

from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do projeto = duas pastas acima deste arquivo (src/utils/config.py)
DIRETORIO_RAIZ: Path = Path(__file__).resolve().parents[2]

# Modelos da geração 4.7+ que REMOVERAM os parâmetros de amostragem.
# Mandar `temperature` pra eles devolve erro 400:
#     "`temperature` is deprecated for this model."
#
# No lugar dela existe o raciocínio adaptativo: em vez de você regular o
# quanto o modelo "inventa", ele decide sozinho quanto precisa pensar antes
# de responder, e você regula o ESFORÇO.
#
# Testado na prática em 18/07/2026: opus-4-8 recusa temperature,
# haiku-4-5 ainda aceita. Por isso a checagem é por modelo, não global.
MODELOS_SEM_TEMPERATURE: frozenset[str] = frozenset(
    {
        "claude-opus-4-8",
        "claude-opus-4-7",
        "claude-fable-5",
        "claude-mythos-5",
    }
)

# Carrega o .env para as variáveis de ambiente do processo
load_dotenv(DIRETORIO_RAIZ / ".env")


class Configuracao(BaseSettings):
    """Todas as configurações do sistema, validadas pelo Pydantic.

    O Pydantic lê cada campo da variável de ambiente com o mesmo nome
    (case-insensitive) e valida o tipo. Se faltar algo obrigatório ou vier com
    tipo errado, o erro aparece AQUI, na inicialização — e não lá na frente,
    no meio de uma partida.

    Attributes:
        anthropic_api_key: Chave da API da Anthropic (obrigatória).
        obs_host: Endereço do OBS Studio rodando o WebSocket.
        obs_port: Porta do WebSocket do OBS (padrão 4455).
        obs_password: Senha do WebSocket do OBS.
        obs_source_name: Nome exato da fonte de captura configurada no OBS.
        database_path: Caminho do arquivo SQLite com as cartas.
        capture_interval_ms: Intervalo entre capturas de tela, em milissegundos.
        capture_width: Largura do frame capturado, em pixels.
        capture_height: Altura do frame capturado, em pixels.
        claude_model_primary: Modelo usado nas análises principais.
        claude_model_fallback: Modelo barato usado como fallback.
        claude_max_tokens_recommendation: Teto de tokens por recomendação.
        claude_temperature: Temperatura da geração (0 = determinístico).
        log_level: Nível de log da aplicação.
        debug_mode: Liga logs e checagens extras.
        save_screenshots_debug: Salva frames capturados em logs/ para inspeção.
    """

    model_config = SettingsConfigDict(
        env_file=DIRETORIO_RAIZ / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignora variáveis de ambiente que não usamos
    )

    # --- Claude API ---
    anthropic_api_key: str = Field(
        default="",
        description="Chave da API Anthropic. Fica só no .env, nunca no código.",
    )

    # --- OBS Studio ---
    obs_host: str = "localhost"
    obs_port: int = 4455
    obs_password: str = ""
    obs_source_name: str = "Game Capture 1903"

    # --- Banco de dados ---
    database_path: Path = DIRETORIO_RAIZ / "data" / "magic-ai.db"

    # --- Captura de tela ---
    capture_interval_ms: int = 300
    capture_width: int = 1280
    capture_height: int = 720

    # --- Inteligência artificial ---
    claude_model_primary: str = "claude-sonnet-4-6"
    claude_model_fallback: str = "claude-haiku-4-5"
    claude_max_tokens_recommendation: int = 2500

    # Só é usada em modelos antigos (ver MODELOS_SEM_TEMPERATURE).
    claude_temperature: float = 0.3

    # Substitui a temperatura nos modelos novos: regula quanto o modelo pensa
    # antes de responder. "high" é o equilíbrio bom pra decisão de jogada;
    # "low" serve pra tarefas mecânicas e sai mais barato.
    claude_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"

    # --- Idioma ---
    # Em qual idioma MOSTRAR as cartas pra você. Não afeta o que é enviado
    # pra IA: pra ela vai sempre o nome em inglês, porque toda a literatura
    # estratégica de Magic é em inglês. Como o log traz o `grpId` numérico,
    # jogar em português não custa nada.
    idioma_exibicao: Literal["ptBR", "enUS"] = "ptBR"

    # --- Aplicação ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    debug_mode: bool = False
    save_screenshots_debug: bool = False

    @field_validator("database_path")
    @classmethod
    def _resolver_caminho_do_banco(cls, caminho: Path) -> Path:
        """Transforma caminho relativo do .env em caminho absoluto.

        O .env traz `DATABASE_PATH=./data/magic-ai.db`, que é relativo ao
        diretório de onde o comando foi executado. Se você rodar o sistema de
        outra pasta, o SQLite criaria um banco novo e VAZIO em outro lugar —
        e você passaria meia hora procurando as 30 mil cartas que sumiram.

        Ancorando na raiz do projeto, o banco é sempre o mesmo arquivo.

        Args:
            caminho: Caminho como veio do .env (relativo ou absoluto).

        Returns:
            Caminho absoluto, ancorado na raiz do projeto quando relativo.
        """
        if caminho.is_absolute():
            return caminho
        return (DIRETORIO_RAIZ / caminho).resolve()

    def parametros_de_geracao(self, modelo: str | None = None) -> dict[str, object]:
        """Monta os parâmetros de geração corretos para o modelo escolhido.

        Existe porque os modelos não aceitam os mesmos parâmetros, e descobrir
        isso em produção custa caro: a chamada volta 400 no meio de uma
        partida, quando você mais precisa da recomendação.

        - Modelos 4.7+ (Opus 4.8, Opus 4.7, Fable 5): sem `temperature`.
          Usam raciocínio adaptativo e o parâmetro de esforço.
        - Modelos anteriores (Haiku 4.5, Sonnet 4.6): `temperature` normal.

        Uso:
            cliente.messages.create(
                model=config.claude_model_primary,
                max_tokens=2500,
                messages=[...],
                **config.parametros_de_geracao(),
            )

        Args:
            modelo: Nome do modelo. Se None, usa o modelo principal do .env.

        Returns:
            Dicionário pronto pra ser expandido na chamada da API.
        """
        alvo = modelo or self.claude_model_primary

        if alvo in MODELOS_SEM_TEMPERATURE:
            return {
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": self.claude_effort},
            }

        return {"temperature": self.claude_temperature}

    def chave_api_configurada(self) -> bool:
        """Diz se a chave da Anthropic foi realmente preenchida.

        Não basta a variável existir: o .env.example vem com um valor de
        exemplo (`sk-ant-api-XXXX...`) que passaria numa checagem ingênua de
        "a variável está definida?". Aqui rejeitamos o placeholder também.

        Returns:
            True se a chave parece uma chave real, False caso contrário.
        """
        chave = self.anthropic_api_key.strip()
        if not chave:
            return False
        if "XXXX" in chave:  # ainda é o placeholder do .env.example
            return False
        return chave.startswith("sk-ant-")


# Instância única, importada por todo o resto do projeto:
#   from src.utils.config import config
config = Configuracao()
