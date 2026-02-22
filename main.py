import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from config import load_config, run_setup_wizard, save_config, validate_config
from sharing.s3_code_provider import S3CodeProvider
from storage.s3_client import S3Client
from ui.menu import show_main_menu
from ui.prompts import prompt_username

console = Console()


def main() -> None:
    console.print(
        Panel.fit(
            "[bold cyan]pyTime[/bold cyan]\n[dim]S3 File Manager[/dim]",
            border_style="cyan",
            padding=(1, 4),
        )
    )

    # Load config — run setup wizard on first launch or if config is invalid
    config = load_config()
    if config is None:
        console.print(
            "[yellow]No configuration found. Running first-time setup...[/yellow]\n"
        )
        config = run_setup_wizard()
        save_config(config)
        console.print("\n[green]Configuration saved to ~/.pytime/config.json[/green]\n")
    elif not validate_config(config):
        console.print(
            "[yellow]Saved configuration is incomplete or corrupted. Re-running setup...[/yellow]\n"
        )
        config = run_setup_wizard()
        save_config(config)
        console.print("\n[green]Configuration updated.[/green]\n")

    # Prompt for username every launch
    username = prompt_username()
    console.print()

    # Verify S3 connection
    console.print("[dim]Connecting to AWS S3...[/dim]")
    client = S3Client(config)

    if not client.verify_connection():
        console.print(
            "[red]Failed to connect to AWS. Please check your credentials.[/red]"
        )
        reconfigure = Prompt.ask("Reconfigure credentials?", choices=["y", "n"], default="y")
        if reconfigure == "y":
            config = run_setup_wizard()
            save_config(config)
            client = S3Client(config)
            if not client.verify_connection():
                console.print("[red]Still unable to connect. Exiting.[/red]")
                sys.exit(1)
        else:
            sys.exit(1)

    # Ensure bucket exists (creates it if not)
    client.ensure_bucket_exists()
    console.print(
        f"[green]Connected.[/green] Bucket: [cyan]{config['bucket_name']}[/cyan]\n"
    )

    # Hand off to main menu
    code_provider = S3CodeProvider(client)
    show_main_menu(client, username, code_provider)


if __name__ == "__main__":
    main()
