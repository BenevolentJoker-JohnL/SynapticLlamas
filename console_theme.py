from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.live import Live
from rich.layout import Layout
from rich import box

# Custom SynapticLlamas theme - Black background, Red accents, Cyan highlights
SYNAPSE_THEME = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "primary": "bold red",
    "secondary": "cyan",
    "accent": "bright_cyan",
    "dim": "dim white",
    "highlight": "bold bright_red",
    "node": "cyan",
    "agent": "red",
    "metric": "bright_cyan",
    "command": "bold cyan",
    "value": "bright_red"
})

# Global console instance
console = Console(theme=SYNAPSE_THEME, force_terminal=True)


def print_banner():
    """Print SynapticLlamas banner."""
    banner = """
[bold red]╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║              [bright_red]🧠  S Y N A P T I C   L L A M A S  🧠[/bright_red]               ║
║                                                                      ║
║           [cyan]Distributed Multi-Agent AI Orchestration[/cyan]              ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝[/bold red]
"""
    console.print(banner)


def print_section(title: str, content: str = None):
    """Print a section with red border."""
    panel = Panel(
        content or "",
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
        box=box.DOUBLE
    )
    console.print(panel)


def print_info(message: str):
    """Print info message in cyan."""
    console.print(f"[cyan]ℹ[/cyan]  {message}")


def print_success(message: str):
    """Print success message."""
    console.print(f"[green]✓[/green]  {message}")


def print_error(message: str):
    """Print error message in red."""
    console.print(f"[bold red]✗[/bold red]  {message}")


def print_warning(message: str):
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow]  {message}")


def print_command(command: str, description: str):
    """Print command with description."""
    console.print(f"  [bold cyan]{command:<20}[/bold cyan] [dim white]{description}[/dim white]")


def print_status_table(data: dict):
    """Print status as a table with red borders."""
    table = Table(
        title="[bold red]SYSTEM STATUS[/bold red]",
        border_style="red",
        box=box.DOUBLE,
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Property", style="cyan")
    table.add_column("Value", style="bright_red")

    for key, value in data.items():
        table.add_row(key, str(value))

    console.print(table)


def print_node_table(nodes: list):
    """Print nodes in a table."""
    table = Table(
        title="[bold red]OLLAMA NODES[/bold red]",
        border_style="red",
        box=box.DOUBLE,
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Name", style="cyan")
    table.add_column("URL", style="dim white")
    table.add_column("Status", style="green")
    table.add_column("GPU", style="bright_cyan")
    table.add_column("Load", style="red")

    for node in nodes:
        status = "✓ Healthy" if node.get('is_healthy') else "✗ Down"
        gpu = "🎮 Yes" if node.get('has_gpu') else "💻 No"
        load = f"{node.get('load_score', 0):.2f}"

        table.add_row(
            node.get('name', 'unknown'),
            node.get('url', ''),
            status,
            gpu,
            load
        )

    console.print(table)


def print_metrics_table(metrics: dict):
    """Print performance metrics."""
    table = Table(
        title="[bold red]PERFORMANCE METRICS[/bold red]",
        border_style="red",
        box=box.DOUBLE,
        show_header=True,
        header_style="bold cyan"
    )

    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bright_red")

    for key, value in metrics.items():
        if isinstance(value, float):
            table.add_row(key, f"{value:.2f}")
        else:
            table.add_row(key, str(value))

    console.print(table)


def print_json_output(data: dict):
    """Print JSON with syntax highlighting."""
    import json
    json_str = json.dumps(data, indent=2)

    panel = Panel(
        Syntax(json_str, "json", theme="monokai", background_color="default"),
        title="[bold red]JSON OUTPUT[/bold red]",
        border_style="red",
        box=box.DOUBLE
    )
    console.print(panel)


def create_progress_bar(description: str = "Processing"):
    """Create a progress bar with custom styling."""
    return Progress(
        SpinnerColumn(style="red"),
        TextColumn("[cyan]{task.description}[/cyan]"),
        BarColumn(complete_style="red", finished_style="green"),
        TimeElapsedColumn(),
        console=console
    )


def print_divider():
    """Print a divider line."""
    console.print("[red]" + "─" * 70 + "[/red]")


def print_agent_message(agent_name: str, phase: str, status: str = ""):
    """Print agent activity message."""
    emoji_map = {
        "Researcher": "📚",
        "Critic": "🔍",
        "Editor": "✨"
    }

    emoji = emoji_map.get(agent_name, "🤖")
    status_suffix = f" [dim white]{status}[/dim white]" if status else ""

    console.print(f"[red]{emoji}  {agent_name}[/red] [cyan]→[/cyan] [dim white]{phase}[/dim white]{status_suffix}")


def print_mode_switch(mode: str):
    """Print mode switch message."""
    console.print(f"\n[bold red]╔═══ MODE SWITCH ═══╗[/bold red]")
    console.print(f"[bold red]║[/bold red]  [bright_cyan]{mode.upper()}[/bright_cyan]")
    console.print(f"[bold red]╚═══════════════════╝[/bold red]\n")
