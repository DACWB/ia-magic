"""Ponto de entrada do Magic AI Advisor.

Rodar com:
    venv\\Scripts\\python.exe -m src.main

No Dia 1 este arquivo só mostra o diagnóstico do ambiente. A cada dia do
roadmap ele ganha uma camada nova, até virar o loop completo:

    captura (OBS) -> visão (OCR) -> estado -> IA -> dashboard
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.utils.config import config
from src.utils.terminal import preparar_terminal

# Precisa vir ANTES de criar o Console: no Windows o terminal nasce em cp1252
# e o Rich decide a estratégia de renderização na criação do objeto.
preparar_terminal()

console = Console()


def mostrar_diagnostico() -> None:
    """Imprime no terminal o estado atual da configuração.

    Serve pra você conferir num relance se o .env está sendo lido e se falta
    alguma coisa antes de começar uma sessão de jogo.
    """
    console.print(
        Panel("🎴 MAGIC AI ADVISOR", style="bold cyan", subtitle="Dia 1 — Setup")
    )

    tabela = Table(show_header=True, header_style="bold")
    tabela.add_column("Item")
    tabela.add_column("Valor")
    tabela.add_column("Status", justify="center")

    chave_ok = config.chave_api_configurada()
    tabela.add_row(
        "Chave Anthropic",
        "configurada" if chave_ok else "faltando no .env",
        "✅" if chave_ok else "❌",
    )
    tabela.add_row("Modelo principal", config.claude_model_primary, "✅")
    tabela.add_row("Modelo fallback", config.claude_model_fallback, "✅")

    banco_existe = config.database_path.exists()
    tabela.add_row(
        "Banco SQLite",
        str(config.database_path),
        "✅" if banco_existe else "⏳ (Dia 2)",
    )

    tabela.add_row(
        "OBS",
        f"{config.obs_host}:{config.obs_port} — fonte '{config.obs_source_name}'",
        "⏳ (Dia 3)",
    )
    tabela.add_row(
        "Captura",
        f"{config.capture_width}x{config.capture_height} a cada "
        f"{config.capture_interval_ms}ms",
        "⏳ (Dia 3)",
    )

    console.print(tabela)

    if not chave_ok:
        console.print(
            Panel(
                "Edite o arquivo [bold].env[/bold] e coloque sua chave real em "
                "[bold]ANTHROPIC_API_KEY[/bold].\n"
                "Pegue em: https://console.anthropic.com",
                title="⚠️  Falta um passo",
                border_style="yellow",
            )
        )


if __name__ == "__main__":
    mostrar_diagnostico()
