from pathlib import Path, PurePosixPath

from botocore.exceptions import ClientError
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Prompt
from rich.table import Table

from storage.s3_client import S3Client

console = Console()


def download_flow(client: S3Client, username: str) -> None:
    """Browse the user's S3 namespace and download a selected file or folder."""
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
                    "[dim]Use Upload from the main menu to add files first.[/dim]\n"
                )
            else:
                console.print("[yellow]This folder is empty.[/yellow]\n")
            if history:
                prefix = history.pop()
                continue
            return

        _render_listing(prefix, folders, files, username)

        items: list[tuple[str, object]] = (
            [("folder", f) for f in folders] + [("file", f) for f in files]
        )
        choices = [str(i + 1) for i in range(len(items))]
        if history:
            choices.append("b")
        choices.append("q")

        choice = Prompt.ask("Select to navigate or download", choices=choices)

        if choice == "q":
            console.print()
            break
        elif choice == "b":
            prefix = history.pop()
        else:
            idx = int(choice) - 1
            kind, item = items[idx]

            if kind == "folder":
                folder_name = PurePosixPath(item.rstrip("/")).name
                action = Prompt.ask(
                    f"[cyan]{folder_name}/[/cyan] — navigate or download all?",
                    choices=["navigate", "download"],
                    default="navigate",
                )
                if action == "download":
                    _download_folder(client, item)
                    break
                else:
                    history.append(prefix)
                    prefix = item
            else:
                download_single_file(client, item)
                break


def download_single_file(client: S3Client, file_info: dict) -> None:
    """Prompt for a destination and download one file. Importable by browse.py."""
    key = file_info["key"]
    filename = PurePosixPath(key).name
    size = file_info["size"]

    console.print(f"\n[cyan]{filename}[/cyan]  [dim]{_fmt_size(size)}[/dim]")
    dest_str = Prompt.ask("Save to directory", default=str(Path.cwd()))
    local_path = Path(dest_str).expanduser().resolve() / filename

    console.print()
    try:
        with Progress(
            TextColumn("[cyan]{task.description}[/cyan]"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task(filename, total=size)
            client.download_file(
                key,
                local_path,
                callback=lambda n: progress.update(task, advance=n),
            )
        console.print(f"[green]Saved to[/green] {local_path}\n")
    except ClientError as e:
        console.print(f"[red]Download failed:[/red] {e.response['Error']['Message']}\n")
    except Exception as e:
        console.print(f"[red]Download failed:[/red] {e}\n")


def _download_folder(client: S3Client, prefix: str) -> None:
    folder_name = PurePosixPath(prefix.rstrip("/")).name

    all_objects = client.list_all_objects(prefix)
    if not all_objects:
        console.print("[yellow]No files in this folder.[/yellow]\n")
        return

    total = len(all_objects)
    total_size = sum(obj["size"] for obj in all_objects)
    console.print(
        f"\n[cyan]{folder_name}/[/cyan]  "
        f"[dim]{total} files, {_fmt_size(total_size)}[/dim]"
    )

    dest_str = Prompt.ask("Save to directory", default=str(Path.cwd()))
    dest_dir = Path(dest_str).expanduser().resolve()

    successes = 0
    failures: list[tuple[str, str]] = []
    prefix_path = PurePosixPath(prefix.rstrip("/"))

    with Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        overall_task = progress.add_task("[white]Overall[/white]", total=total)
        file_task = progress.add_task("", total=1)

        for i, obj in enumerate(all_objects, 1):
            key = obj["key"]
            relative = PurePosixPath(key).relative_to(prefix_path)
            local_path = dest_dir / folder_name / str(relative)

            progress.update(
                file_task,
                description=f"[cyan]{relative}[/cyan] ({i}/{total})",
                completed=0,
                total=obj["size"],
            )

            try:
                file_task_id = file_task
                client.download_file(
                    key,
                    local_path,
                    callback=lambda n, t=file_task_id: progress.update(t, advance=n),
                )
                successes += 1
            except Exception as e:
                failures.append((str(relative), str(e)))

            progress.update(overall_task, advance=1)

    console.print()
    if successes == total:
        console.print(
            f"[green]All {total} file(s) downloaded to[/green] {dest_dir / folder_name}"
        )
    else:
        console.print(f"[green]{successes}[/green]/[white]{total}[/white] file(s) downloaded.")

    if failures:
        console.print(f"\n[red]{len(failures)} file(s) failed:[/red]")
        for name, err in failures:
            console.print(f"  [red]✗[/red] {name}: {err}")
    console.print()


def _render_listing(
    prefix: str, folders: list[str], files: list[dict], username: str
) -> None:
    display_path = prefix.removeprefix(f"{username}/") or "(root)"

    table = Table(show_header=True, header_style="bold cyan", box=None, padding=(0, 2))
    table.add_column("#", style="cyan", width=4)
    table.add_column("Type", width=6)
    table.add_column("Name")
    table.add_column("Size", justify="right", style="dim")

    idx = 1
    for folder_prefix in folders:
        name = PurePosixPath(folder_prefix.rstrip("/")).name + "/"
        table.add_row(str(idx), "DIR", f"[bold]{name}[/bold]", "")
        idx += 1
    for f in files:
        name = PurePosixPath(f["key"]).name
        table.add_row(str(idx), "FILE", name, _fmt_size(f["size"]))
        idx += 1

    back_hint = "  [b] Back" if prefix != f"{username}/" else ""
    console.print(
        Panel(
            table,
            title=f"[bold cyan]Download[/bold cyan]  [dim]{display_path}[/dim]",
            subtitle=f"[dim]Select to navigate or download{back_hint}  [q] Cancel[/dim]",
            border_style="cyan",
            padding=(1, 2),
        )
    )


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    elif size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / 1024 ** 2:.1f} MB"
