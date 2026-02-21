from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from sharing.code_provider import CodeProvider
from storage.s3_client import S3Client
from ui.browse import browse_flow
from ui.download import download_flow
from ui.share import share_flow
from ui.upload import upload_flow

console = Console()

MENU_OPTIONS = {
    "1": ("Upload", "Upload a file or directory to S3"),
    "2": ("Download", "Download files from S3"),
    "3": ("Browse", "Browse your S3 files"),
    "4": ("Share", "Share a directory with another user"),
    "5": ("Exit", "Quit pyTime"),
}


def show_main_menu(client: S3Client, username: str, code_provider: CodeProvider) -> None:
    while True:
        _render_menu(username)
        choice = Prompt.ask("Select an option", choices=list(MENU_OPTIONS.keys()))

        if choice == "1":
            upload_flow(client, username)
        elif choice == "2":
            download_flow(client, username)
        elif choice == "3":
            browse_flow(client, username)
        elif choice == "4":
            share_flow(client, username, code_provider)
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
