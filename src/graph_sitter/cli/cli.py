import rich_click as click
from rich.traceback import install

from graph_sitter.cli.commands.config.main import config_command
from graph_sitter.cli.commands.create.main import create_command
from graph_sitter.cli.commands.diagnose.main import diagnose_command
from graph_sitter.cli.commands.doctor.main import doctor_command
from graph_sitter.cli.commands.init.main import init_command
from graph_sitter.cli.commands.inspect.main import inspect_command
from graph_sitter.cli.commands.list.main import list_command
from graph_sitter.cli.commands.lsp.lsp import lsp_command
from graph_sitter.cli.commands.notebook.main import notebook_command
from graph_sitter.cli.commands.parse.main import parse_command
from graph_sitter.cli.commands.rename.main import rename_command
from graph_sitter.cli.commands.reset.main import reset_command
from graph_sitter.cli.commands.run.main import run_command
from graph_sitter.cli.commands.start.main import start_command
from graph_sitter.cli.commands.style_debug.main import style_debug_command
from graph_sitter.cli.commands.transform.main import transform_command
from graph_sitter.cli.commands.update.main import update_command
from graph_sitter.cli.commands.usages.main import usages_command
from graph_sitter.cli.commands.using.main import using_command

click.rich_click.USE_RICH_MARKUP = True
install(show_locals=True)


@click.group()
@click.version_option(prog_name="graph-sitter")
def main():
    """graph_sitter.cli - Analyze and transform codebases."""


# Wrap commands with error handler
main.add_command(init_command)
main.add_command(doctor_command)
main.add_command(diagnose_command)
main.add_command(parse_command)
main.add_command(inspect_command)
main.add_command(usages_command)
main.add_command(using_command)
main.add_command(rename_command)
main.add_command(run_command)
main.add_command(transform_command)
main.add_command(create_command)
main.add_command(list_command)
main.add_command(style_debug_command)
main.add_command(notebook_command)
main.add_command(reset_command)
main.add_command(update_command)
main.add_command(config_command)
main.add_command(lsp_command)
main.add_command(start_command)


if __name__ == "__main__":
    main()
