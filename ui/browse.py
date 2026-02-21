from datetime import datetime
from pathlib import PurePosixPath

from botocore.exceptions import ClientError
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from storage.s3_client import S3Client

console = Console()


def browse_flow(client: S3Client, username: str) -> None:
    root_prefix = f"{username}/"
    prefix = root_prefix
    history: list[str] = []

    while True:
        try:
            folders, files = client.list_folder(prefix)
        except ClientError as e:
            console.print(f"[red]Failed to list files:[/red] {e.response['Error']['Message']}\n")
            return

        if not folders and not files:
            if prefix == root_prefix:
                console.print(
                    "[yellow]Nothing uploaded yet.[/yellow]\n"
                    "[dim]Use Upload from the main menu to add files.[/dim]\n"
                )
            else:
                console.print("[yellow]This folder is empty.[/yellow]\n")

            if history:
                prefix = history.pop()
                continue
            return

        items: list[tuple[str, object]] = (
            [("folder", f) for f in folders] + [("file", f) for f in files]
        )

        _render_listing(prefix, folders, files, username)

        choices = [str(i + 1) for i in range(len(items))]
        if history:
            choices.append("b")
        choices.append("q")

        choice = Prompt.ask("Select", choices=choices)

        if choice == "q":
            console.print()
            break
        elif choice == "b":
            prefix = history.pop()
        else:
            idx = int(choice) - 1
            kind, item = items[idx]
            if kind == "folder":
                history.append(prefix)
                prefix = item
            else:
                console.print(f"\n[dim]File download available in Sprint 5.[/dim]\n")


def _render_listing(
    prefix: str,
    folders: list[str],
    files: list[dict],
    username: str,
) -> None:
    display_path = prefix.removeprefix(f"{username}/") or "(root)"

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("#", style="cyan", width=4)
    table.add_column("Type", width=6)
    table.add_column("Name")
    table.add_column("Size", justify="right", style="dim")
    table.add_column("Last Modified", style="dim")

    idx = 1
    for folder_prefix in folders:
        name = PurePosixPath(folder_prefix.rstrip("/")).name + "/"
        table.add_row(str(idx), "DIR", f"[bold]{name}[/bold]", "", "")
        idx += 1

    for f in files:
        name = PurePosixPath(f["key"]).name
        table.add_row(
            str(idx),
            "FILE",
            name,
            _fmt_size(f["size"]),
            _fmt_date(f["last_modified"]),
        )
        idx += 1

    back_hint = "  [b] Back" if prefix != f"{username}/" else ""
    panel = Panel(
        table,
        title=f"[bold cyan]Browse[/bold cyan]  [dim]{display_path}[/dim]",
        subtitle=f"[dim]Select a number to navigate{back_hint}  [q] Main menu[/dim]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / 1024 ** 2:.1f} MB"


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")
