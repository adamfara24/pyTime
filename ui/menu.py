from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from storage.s3_client import S3Client

console = Console()

MENU_OPTIONS = {
    "1": ("Upload", "Upload a file or directory to S3"),
    "2": ("Download", "Download files from S3"),
    "3": ("Browse", "Browse your S3 files"),
    "4": ("Share", "Share a directory with another user"),
    "5": ("Exit", "Quit pyTime"),
}


def show_main_menu(client: S3Client, username: str) -> None:
    while True:
        _render_menu(username)
        choice = Prompt.ask("Select an option", choices=list(MENU_OPTIONS.keys()))

        if choice == "1":
            console.print("[dim]Upload — coming in Sprint 2[/dim]\n")
        elif choice == "2":
            console.print("[dim]Download — coming in Sprint 5[/dim]\n")
        elif choice == "3":
            console.print("[dim]Browse — coming in Sprint 4[/dim]\n")
        elif choice == "4":
            console.print("[dim]Share — coming in Sprint 6[/dim]\n")
        elif choice == "5":
            console.print("\n[cyan]Goodbye![/cyan]\n")
            break


def _render_menu(username: str) -> None:
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan bold", width=4)
    table.add_column("Option", style="white")
    table.add_column("Description", style="dim")

    for key, (name, desc) in MENU_OPTIONS.items():
        table.add_row(f"[{key}]", name, desc)

    panel = Panel(
        table,
        title=f"[bold cyan]pyTime[/bold cyan]  [dim]logged in as: {username}[/dim]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)
