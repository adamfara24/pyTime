from pathlib import PurePosixPath

from botocore.exceptions import ClientError
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from sharing.code_provider import CodeProvider
from storage.s3_client import S3Client
from ui.download import _download_folder

console = Console()


def share_flow(client: S3Client, username: str, code_provider: CodeProvider) -> None:
    console.print()
    action = Prompt.ask(
        "Share menu",
        choices=["generate", "redeem", "revoke"],
        default="generate",
    )
    console.print()

    if action == "generate":
        _generate_share_code(client, username, code_provider)
    elif action == "redeem":
        _redeem_share_code(client, code_provider)
    else:
        _revoke_share_code(code_provider)


def _generate_share_code(
    client: S3Client, username: str, code_provider: CodeProvider
) -> None:
    root_prefix = f"{username}/"

    try:
        folders, _ = client.list_folder(root_prefix)
    except ClientError as e:
        console.print(f"[red]Error listing folders:[/red] {e.response['Error']['Message']}\n")
        return

    if not folders:
        console.print(
            "[yellow]No folders found to share.[/yellow]\n"
            "[dim]Upload a directory first using the Upload menu.[/dim]\n"
        )
        return

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("#", style="cyan", width=4)
    table.add_column("Folder")

    for i, prefix in enumerate(folders, 1):
        name = PurePosixPath(prefix.rstrip("/")).name + "/"
        table.add_row(str(i), f"[bold]{name}[/bold]")

    console.print(
        Panel(
            table,
            title="[bold cyan]Select a folder to share[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    choice = Prompt.ask("Select folder", choices=[str(i) for i in range(1, len(folders) + 1)])
    selected_prefix = folders[int(choice) - 1]
    folder_name = PurePosixPath(selected_prefix.rstrip("/")).name

    expires_hours = _prompt_expiry()

    try:
        code = code_provider.generate_code(selected_prefix, expires_hours=expires_hours)
    except Exception as e:
        console.print(f"[red]Failed to generate code:[/red] {e}\n")
        return

    expiry_note = f"{expires_hours}h" if expires_hours else "no expiry"
    console.print(
        Panel(
            f"[bold cyan]{code}[/bold cyan]",
            title="[bold]Share Code[/bold]",
            subtitle=f"[dim]{folder_name}/  ·  {expiry_note}[/dim]",
            border_style="green",
            padding=(1, 4),
        )
    )
    console.print("[dim]Give this code to another pyTime user.[/dim]\n")


def _redeem_share_code(client: S3Client, code_provider: CodeProvider) -> None:
    code = Prompt.ask("[cyan]Enter share code[/cyan]").strip().upper()

    try:
        path = code_provider.resolve_code(code)
    except Exception as e:
        console.print(f"[red]Error resolving code:[/red] {e}\n")
        return

    if path is None:
        console.print("[red]Invalid or expired share code.[/red]\n")
        return

    folder_name = PurePosixPath(path.rstrip("/")).name
    console.print(
        f"[green]Code valid![/green] Shared folder: [cyan]{folder_name}/[/cyan]\n"
    )

    _download_folder(client, path)


def _revoke_share_code(code_provider: CodeProvider) -> None:
    code = Prompt.ask("[cyan]Enter code to revoke[/cyan]").strip().upper()

    try:
        path = code_provider.resolve_code(code)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}\n")
        return

    if path is None:
        console.print("[yellow]Code not found or already expired.[/yellow]\n")
        return

    folder_name = PurePosixPath(path.rstrip("/")).name
    try:
        code_provider.revoke_code(code)
    except Exception as e:
        console.print(f"[red]Failed to revoke code:[/red] {e}\n")
        return

    console.print(
        f"[green]Code [cyan]{code}[/cyan] revoked.[/green]"
        f" Access to [cyan]{folder_name}/[/cyan] has been removed.\n"
    )


def _prompt_expiry() -> int | None:
    """Ask the user for an optional expiry duration in hours. Returns None for no expiry."""
    raw = Prompt.ask(
        "Expire after how many hours? [dim](press Enter for no expiry)[/dim]",
        default="",
    ).strip()

    if not raw:
        return None

    try:
        hours = int(raw)
        if hours <= 0:
            console.print("[yellow]Expiry must be a positive number. Setting no expiry.[/yellow]")
            return None
        return hours
    except ValueError:
        console.print("[yellow]Invalid input. Setting no expiry.[/yellow]")
        return None
