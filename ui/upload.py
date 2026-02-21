import os
from pathlib import Path

from botocore.exceptions import ClientError
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Prompt

from storage.s3_client import S3Client

console = Console()


def upload_flow(client: S3Client, username: str) -> None:
    """Entry point — asks the user whether to upload a file or directory."""
    choice = Prompt.ask(
        "Upload a",
        choices=["file", "directory"],
        default="file",
    )
    if choice == "file":
        _upload_file_flow(client, username)
    else:
        _upload_directory_flow(client, username)


def _upload_file_flow(client: S3Client, username: str) -> None:
    path_str = Prompt.ask("[cyan]Local file path[/cyan]").strip()
    local_path = Path(path_str).expanduser().resolve()

    if not local_path.exists():
        console.print(f"[red]File not found:[/red] {local_path}\n")
        return

    if not local_path.is_file():
        console.print(f"[red]That path points to a directory, not a file.[/red]")
        console.print("[dim]Choose 'directory' from the upload menu to upload a folder.[/dim]\n")
        return

    s3_key = f"{username}/{local_path.name}"
    file_size = local_path.stat().st_size

    console.print(
        f"\nUploading [cyan]{local_path.name}[/cyan]"
        f" → [cyan]s3://{client.bucket}/{s3_key}[/cyan]\n"
    )

    try:
        with Progress(
            TextColumn("[cyan]{task.description}[/cyan]"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task(local_path.name, total=file_size)
            client.upload_file(
                local_path,
                s3_key,
                callback=lambda n: progress.update(task, advance=n),
            )

        console.print(f"[green]Upload complete.[/green] Stored as [cyan]{s3_key}[/cyan]\n")

    except ClientError as e:
        console.print(f"[red]Upload failed:[/red] {e.response['Error']['Message']}\n")
    except Exception as e:
        console.print(f"[red]Upload failed:[/red] {e}\n")


def _upload_directory_flow(client: S3Client, username: str) -> None:
    path_str = Prompt.ask("[cyan]Local directory path[/cyan]").strip()
    local_dir = Path(path_str).expanduser().resolve()

    if not local_dir.exists():
        console.print(f"[red]Directory not found:[/red] {local_dir}\n")
        return

    if not local_dir.is_dir():
        console.print(f"[red]That path points to a file, not a directory.[/red]")
        console.print("[dim]Choose 'file' from the upload menu to upload a single file.[/dim]\n")
        return

    all_files = [
        Path(root) / filename
        for root, _, files in os.walk(local_dir)
        for filename in files
    ]

    if not all_files:
        console.print(f"[yellow]No files found in {local_dir.name}.[/yellow]\n")
        return

    folder_name = local_dir.name
    total = len(all_files)
    console.print(f"\nFound [cyan]{total}[/cyan] file(s) in [cyan]{folder_name}/[/cyan]\n")

    successes = 0
    failures: list[tuple[str, str]] = []

    with Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as progress:
        overall_task = progress.add_task(
            f"[white]Overall[/white]", total=total
        )
        file_task = progress.add_task("", total=1)

        for i, file_path in enumerate(all_files, 1):
            relative = file_path.relative_to(local_dir)
            s3_key = f"{username}/{folder_name}/{relative.as_posix()}"
            file_size = file_path.stat().st_size

            progress.update(
                file_task,
                description=f"[cyan]{relative.as_posix()}[/cyan] ({i}/{total})",
                completed=0,
                total=file_size,
            )

            try:
                file_task_id = file_task
                client.upload_file(
                    file_path,
                    s3_key,
                    callback=lambda n, t=file_task_id: progress.update(t, advance=n),
                )
                successes += 1
            except Exception as e:
                failures.append((relative.as_posix(), str(e)))

            progress.update(overall_task, advance=1)

    _print_summary(folder_name, total, successes, failures)


def _print_summary(
    folder_name: str,
    total: int,
    successes: int,
    failures: list[tuple[str, str]],
) -> None:
    console.print()
    if successes == total:
        console.print(
            f"[green]All {total} file(s) uploaded successfully[/green]"
            f" from [cyan]{folder_name}/[/cyan]"
        )
    else:
        console.print(
            f"[green]{successes}[/green]/[white]{total}[/white] file(s) uploaded successfully."
        )

    if failures:
        console.print(f"\n[red]{len(failures)} file(s) failed:[/red]")
        for name, err in failures:
            console.print(f"  [red]✗[/red] {name}: {err}")

    console.print()
