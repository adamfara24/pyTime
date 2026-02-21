from rich.console import Console
from rich.prompt import Prompt

console = Console()


def prompt_username() -> str:
    username = Prompt.ask("[cyan]Enter your username[/cyan]").strip()
    while not username:
        console.print("[red]Username cannot be empty.[/red]")
        username = Prompt.ask("[cyan]Enter your username[/cyan]").strip()
    return username
