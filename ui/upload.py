from pathlib import Path

from botocore.exceptions import ClientError
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.prompt import Prompt

from storage.s3_client import S3Client

console = Console()


def upload_file_flow(client: S3Client, username: str) -> None:
    path_str = Prompt.ask("[cyan]Local file path[/cyan]").strip()
    local_path = Path(path_str).expanduser().resolve()

    if not local_path.exists():
        console.print(f"[red]File not found:[/red] {local_path}\n")
        return

    if not local_path.is_file():
        console.print(f"[red]That path points to a directory, not a file.[/red]")
        console.print("[dim]Directory upload is coming in Sprint 3.[/dim]\n")
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
