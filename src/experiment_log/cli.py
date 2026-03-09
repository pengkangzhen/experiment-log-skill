"""Command-line interface for experiment logging."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree as RichTree

from experiment_log.daemon import (
    DaemonConfig,
    ExperimentDaemon,
    get_daemon_status,
    is_daemon_running,
    start_daemon,
    stop_daemon,
)
from experiment_log.exporter import MarkdownExporter
from experiment_log.intention import quick_recognize
from experiment_log.models import NodeType, Status
from experiment_log.recorder import AutoRecorder
from experiment_log.storage import ExperimentStorage
from experiment_log.tree import ExperimentTreeManager

console = Console()


def get_storage() -> ExperimentStorage:
    """Get the storage instance."""
    return ExperimentStorage()


def get_current_tree(storage: ExperimentStorage | None = None) -> ExperimentTreeManager | None:
    """Get the most recent experiment tree manager."""
    if storage is None:
        storage = get_storage()

    tree = storage.load_latest()
    if tree is None:
        return None
    return ExperimentTreeManager(tree)


@click.group()
@click.version_option(version="0.2.0", prog_name="exp-log")
def main() -> None:
    """Experiment Log - Track your code experiments and exploration paths."""
    pass


# =============================================================================
# Manual Recording Commands
# =============================================================================

@main.command()
@click.argument("problem")
@click.option("--description", "-d", default="", help="Detailed description of the problem")
def start(problem: str, description: str) -> None:
    """Start a new experiment with the given problem."""
    storage = get_storage()

    tree = storage.create_experiment(problem, description)
    manager = ExperimentTreeManager(tree)

    console.print(Panel(
        f"[bold green]Created new experiment[/bold green]\n"
        f"[bold]Problem:[/bold] {problem}\n"
        f"[bold]ID:[/bold] {tree.root_id[:8]}",
        title="Experiment Started",
        border_style="green",
    ))


@main.command()
@click.argument("title")
@click.option("--description", "-d", default="", help="Description of the attempt")
@click.option("--branch", "-b", is_flag=True, help="Create as sibling (branch) instead of child")
def try_attempt(title: str, description: str, branch: bool) -> None:
    """Add a new attempt under the current node."""
    storage = get_storage()
    manager = get_current_tree(storage)

    if manager is None:
        console.print("[red]No active experiment. Use 'exp-log start' first.[/red]")
        sys.exit(1)

    node_id = manager.add_attempt(title, description, branch=branch)

    prefix = "(branch) " if branch else ""
    console.print(Panel(
        f"[bold green]Added attempt node[/bold green]\n"
        f"[bold]Title:[/bold] {title}\n"
        f"[bold]Type:[/bold] {prefix}attempt\n"
        f"[bold]ID:[/bold] {node_id[:8]}",
        title="Attempt Recorded",
        border_style="green",
    ))

    storage.save_experiment(manager.tree)


@main.command()
@click.argument("status", type=click.Choice(["success", "failed", "aborted"]))
@click.argument("description", required=False, default="")
def result(status: str, description: str) -> None:
    """Record the result of the current attempt."""
    storage = get_storage()
    manager = get_current_tree(storage)

    if manager is None:
        console.print("[red]No active experiment. Use 'exp-log start' first.[/red]")
        sys.exit(1)

    status_enum = Status(status)
    node_id = manager.add_result(status_enum, description)

    console.print(Panel(
        f"[bold {'green' if status == 'success' else 'red' if status == 'failed' else 'yellow'}]"
        f"Recorded result[/bold]\n"
        f"[bold]Status:[/bold] {status.upper()}\n"
        f"[bold]Description:[/bold] {description or '(none)'}\n"
        f"[bold]ID:[/bold] {node_id[:8]}",
        title="Result Recorded",
        border_style="green" if status == "success" else "red" if status == "failed" else "yellow",
    ))

    storage.save_experiment(manager.tree)


@main.command()
def status() -> None:
    """Show the current experiment status."""
    storage = get_storage()
    manager = get_current_tree(storage)

    if manager is None:
        console.print("[yellow]No active experiments found.[/yellow]")
        return

    summary = manager.get_tree_summary()

    table = Table(title="Experiment Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Experiment ID", summary["experiment_id"])
    table.add_row("Problem", summary["problem"])
    table.add_row("Created", str(summary["created_at"]))
    table.add_row("Updated", str(summary["updated_at"]))
    table.add_row("Current Node", summary["current_node"] or "N/A")

    stats = summary["stats"]
    table.add_row(
        "Nodes",
        f"Total: {stats['total']}, "
        f"Pending: {stats['pending']}, "
        f"Success: {stats['success']}, "
        f"Failed: {stats['failed']}, "
        f"Aborted: {stats['aborted']}"
    )

    console.print(table)


@main.command(name="tree")
def show_tree() -> None:
    """Display the experiment tree."""
    storage = get_storage()
    manager = get_current_tree(storage)

    if manager is None:
        console.print("[yellow]No active experiments found.[/yellow]")
        return

    root = manager.tree.get_root()
    if not root:
        console.print("[red]Invalid experiment data.[/red]")
        return

    # Build rich tree
    def build_rich_tree(node_id: str, parent: RichTree | None = None) -> RichTree:
        node = manager.tree.nodes.get(node_id)
        if not node:
            return parent or RichTree("")

        status_icon = node.status.icon
        current_marker = " [bold yellow]<-- current[/bold yellow]" \
                        if node_id == manager.tree.current_node_id else ""

        label = f"[{node.id[:4]}] {node.title} {status_icon}{current_marker}"

        if parent is None:
            tree = RichTree(label)
        else:
            tree = parent.add(label)

        for child_id in node.children:
            build_rich_tree(child_id, tree)

        return tree

    rich_tree = build_rich_tree(root.id)
    console.print(Panel(rich_tree, title=f"Experiment: {root.title}", border_style="blue"))


@main.command()
def back() -> None:
    """Go back to the parent node."""
    storage = get_storage()
    manager = get_current_tree(storage)

    if manager is None:
        console.print("[red]No active experiment.[/red]")
        sys.exit(1)

    result = manager.go_back()
    if result is None:
        console.print("[yellow]Already at root node.[/yellow]")
        return

    parent = manager.tree.get_current()
    console.print(Panel(
        f"[bold blue]Moved to parent node[/bold blue]\n"
        f"[bold]Current:[/bold] {parent.title if parent else 'Unknown'}\n"
        f"[bold]ID:[/bold] {result[:8] if result else 'N/A'}",
        title="Navigation",
        border_style="blue",
    ))

    storage.save_experiment(manager.tree)


@main.command()
@click.argument("node_id")
def jump(node_id: str) -> None:
    """Jump to a specific node by ID."""
    storage = get_storage()
    manager = get_current_tree(storage)

    if manager is None:
        console.print("[red]No active experiment.[/red]")
        sys.exit(1)

    # Try to find node by partial ID
    full_id = None
    for nid in manager.tree.nodes:
        if nid.startswith(node_id):
            full_id = nid
            break

    if full_id is None:
        console.print(f"[red]Node {node_id} not found.[/red]")
        sys.exit(1)

    manager.set_current(full_id)
    node = manager.tree.get_current()

    console.print(Panel(
        f"[bold blue]Jumped to node[/bold blue]\n"
        f"[bold]Title:[/bold] {node.title if node else 'Unknown'}\n"
        f"[bold]ID:[/bold] {full_id[:8]}",
        title="Navigation",
        border_style="blue",
    ))

    storage.save_experiment(manager.tree)


@main.command()
@click.option("--latest", "-l", is_flag=True, help="Show only the latest experiment")
def list(latest: bool) -> None:
    """List all experiments."""
    storage = get_storage()
    experiments = storage.list_experiments()

    if not experiments:
        console.print("[yellow]No experiments found.[/yellow]")
        return

    if latest:
        experiments = [experiments[0]]

    table = Table(title="Experiments")
    table.add_column("ID", style="cyan")
    table.add_column("Problem", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Nodes", justify="right")
    table.add_column("Updated", style="dim")

    for exp in experiments:
        table.add_row(
            exp["id"],
            exp["problem"][:40] + "..." if len(exp["problem"]) > 40 else exp["problem"],
            exp["status"],
            str(exp["node_count"]),
            exp["updated_at"][:19] if exp["updated_at"] else "",
        )

    console.print(table)


@main.command()
@click.argument("exp_id", required=False)
@click.option("--output", "-o", help="Output file path")
def export(exp_id: str | None, output: str | None) -> None:
    """Export an experiment to Markdown."""
    storage = get_storage()

    if exp_id is None:
        tree = storage.load_latest()
        if tree is None:
            console.print("[red]No experiments found.[/red]")
            sys.exit(1)
        exp_id = tree.root_id[:8]
    else:
        tree = storage.load_experiment(exp_id)
        if tree is None:
            console.print(f"[red]Experiment {exp_id} not found.[/red]")
            sys.exit(1)

    output_path = output or f"experiment_{exp_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    exporter = MarkdownExporter(tree)
    exported_path = exporter.export(output_path)

    console.print(Panel(
        f"[bold green]Exported successfully[/bold green]\n"
        f"[bold]File:[/bold] {exported_path}\n"
        f"[bold]Experiment:[/bold] {tree.get_root().title if tree.get_root() else 'Unknown'}",
        title="Export Complete",
        border_style="green",
    ))


@main.command()
def close() -> None:
    """Close the current experiment (mark as complete)."""
    storage = get_storage()
    manager = get_current_tree(storage)

    if manager is None:
        console.print("[red]No active experiment.[/red]")
        sys.exit(1)

    root = manager.tree.get_root()
    if root:
        root.status = Status.SUCCESS

    storage.save_experiment(manager.tree)

    console.print(Panel(
        f"[bold green]Experiment closed[/bold green]\n"
        f"[bold]Problem:[/bold] {root.title if root else 'Unknown'}\n"
        f"[bold]Status:[/bold] COMPLETED",
        title="Experiment Complete",
        border_style="green",
    ))


# =============================================================================
# Automatic Recording Commands
# =============================================================================

@main.group()
def daemon() -> None:
    """Manage the auto-recording daemon."""
    pass


@daemon.command(name="start")
@click.option("--interval", "-i", default=2.0, help="Polling interval in seconds")
@click.option("--confidence", "-c", default=0.6, help="Minimum confidence threshold")
@click.option("--history", "-h", type=click.Path(), help="Path to history.jsonl")
@click.option("--foreground", "-f", is_flag=True, help="Run in foreground (for debugging)")
def daemon_start(
    interval: float,
    confidence: float,
    history: str | None,
    foreground: bool,
) -> None:
    """Start the auto-recording daemon."""
    if is_daemon_running():
        console.print("[yellow]Daemon is already running.[/yellow]")
        return

    config = DaemonConfig(
        poll_interval=interval,
        min_confidence=confidence,
        history_path=Path(history) if history else None,
        quiet=False,
    )

    daemon = ExperimentDaemon(config)

    if foreground:
        # Run in foreground for debugging
        daemon.run_foreground()
    else:
        # Start as background daemon
        if daemon.start():
            console.print("[green]Daemon started successfully.[/green]")
        else:
            console.print("[red]Failed to start daemon.[/red]")
            sys.exit(1)


@daemon.command(name="stop")
def daemon_stop() -> None:
    """Stop the auto-recording daemon."""
    if stop_daemon():
        console.print("[green]Daemon stopped.[/green]")
    else:
        console.print("[yellow]Daemon was not running.[/yellow]")


@daemon.command(name="status")
def daemon_status() -> None:
    """Show daemon status."""
    status_info = get_daemon_status()

    table = Table(title="Daemon Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Running", "Yes" if status_info["running"] else "No")
    if status_info["pid"]:
        table.add_row("PID", str(status_info["pid"]))

    config = status_info.get("config", {})
    table.add_row("Poll Interval", f"{config.get('poll_interval', 'N/A')}s")
    table.add_row("Min Confidence", str(config.get("min_confidence", "N/A")))

    console.print(table)

    if not status_info["running"]:
        console.print("\n[dim]Use 'exp-log daemon start' to start the daemon.[/dim]")


@daemon.command(name="run-once")
@click.option("--history", "-h", type=click.Path(), help="Path to history.jsonl")
def daemon_run_once(history: str | None) -> None:
    """Run auto-analysis once (for testing)."""
    from experiment_log.analyzer import SessionAnalyzer

    history_path = Path(history) if history else None
    analyzer = SessionAnalyzer(history_path)

    # Check for updates
    context = analyzer.check_for_updates()

    if context:
        console.print(f"[green]Found {len(context.turns)} new turns[/green]")
        console.print(f"Session: {context.session_id}")
        console.print(f"Latest message: {context.get_latest_user_message()[:50]}...")

        # Try to recognize intention
        intention = quick_recognize(context.get_latest_user_message() or "")
        if intention:
            from experiment_log.intention import get_intention_icon, get_intention_label
            icon = get_intention_icon(intention.type)
            label = get_intention_label(intention.type)
            console.print(f"\n{icon} Detected intention: [bold]{label}[/bold]")
            console.print(f"   Description: {intention.description}")
            console.print(f"   Confidence: {intention.confidence:.2f}")

            # Record it
            recorder = AutoRecorder()
            event = recorder.on_intention_detected(intention, context)
            if event:
                console.print(f"\n[green]Recorded to experiment: {event.experiment_id}[/green]")
        else:
            console.print("\n[yellow]No intention detected[/yellow]")
    else:
        console.print("[yellow]No new messages found[/yellow]")


@main.command()
@click.argument("message")
def analyze(message: str) -> None:
    """Analyze a message and show detected intention (for testing)."""
    intention = quick_recognize(message)

    if intention:
        from experiment_log.intention import get_intention_icon, get_intention_label
        icon = get_intention_icon(intention.type)
        label = get_intention_label(intention.type)

        console.print(Panel(
            f"{icon} [bold]{label}[/bold]\n"
            f"Description: {intention.description}\n"
            f"Confidence: {intention.confidence:.2f}",
            title="Detected Intention",
            border_style="blue",
        ))
    else:
        console.print("[yellow]No intention detected in message.[/yellow]")


if __name__ == "__main__":
    main()
