import rich
import rich_click as click
from rich.status import Status

from graph_sitter.cli.api.client import RestAPI
from graph_sitter.cli.auth.decorators import requires_auth
from graph_sitter.cli.auth.token_manager import get_current_token
from graph_sitter.cli.errors import ServerError
from graph_sitter.cli.workspace.decorators import requires_init


@click.command(name="expert")
@click.option("--query", "-q", help="The question to ask the expert.")
@requires_auth
@requires_init
def expert_command(query: str):
    """Asks a codegen expert a question."""
    status = Status("Asking expert...", spinner="dots", spinner_style="purple")
    status.start()

    try:
        response = RestAPI(get_current_token()).ask_expert(query)
        status.stop()
        rich.print("[bold green]✓ Response received[/bold green]")
        rich.print(response.response)
    except ServerError as e:
        status.stop()
        raise click.ClickException(str(e))
    finally:
        status.stop()
