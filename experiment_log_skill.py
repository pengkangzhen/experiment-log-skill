"""Claude Code Skill implementation for experiment logging."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from experiment_log.exporter import MarkdownExporter
from experiment_log.models import Status
from experiment_log.storage import ExperimentStorage
from experiment_log.tree import ExperimentTreeManager

# Import natural language processing
try:
    from natural_language import process_input, should_handle_as_natural_language
except ImportError:
    # Fallback if natural_language module is not available
    def process_input(text: str) -> tuple[str, str] | None:
        return None

    def should_handle_as_natural_language(text: str) -> bool:
        return False


class ExperimentLogSkill:
    """Skill for managing experiment logs in Claude Code."""

    def __init__(self) -> None:
        self.storage = ExperimentStorage()
        self._current_manager: ExperimentTreeManager | None = None

    def _get_manager(self) -> ExperimentTreeManager | None:
        """Get or load the current experiment manager."""
        if self._current_manager is None:
            tree = self.storage.load_latest()
            if tree:
                self._current_manager = ExperimentTreeManager(tree)
        return self._current_manager

    def explore(self, args: str) -> str:
        """Start a new experiment or show current one.

        Usage: /explore [problem description]
        """
        args = args.strip()

        if not args:
            # Show current experiment
            manager = self._get_manager()
            if not manager:
                return "No active experiment. Start one with: /explore <problem description>"

            root = manager.tree.get_root()
            current = manager.tree.get_current()

            return f"""Current Experiment
==================
Problem: {root.title if root else 'Unknown'}
ID: {manager.tree.root_id[:8]}
Nodes: {len(manager.tree.nodes)}
Current: {current.title if current else 'Unknown'}

Use '/tree' to see the full exploration tree.
"""

        # Start new experiment
        tree = self.storage.create_experiment(args)
        self._current_manager = ExperimentTreeManager(tree)

        return f"""✅ Created new experiment

Problem: {args}
ID: {tree.root_id[:8]}

Next steps:
  /try <description>  - Add an attempt
  /tree               - View the exploration tree
"""

    def try_attempt(self, args: str) -> str:
        """Add a new attempt node.

        Usage: /try <description> [--branch]
        """
        args = args.strip()
        if not args:
            return "Usage: /try <description> [--branch]"

        manager = self._get_manager()
        if not manager:
            return "No active experiment. Start with: /explore <problem>"

        # Parse --branch flag
        branch = False
        if " --branch" in args:
            args = args.replace(" --branch", "").strip()
            branch = True
        elif args.endswith("--branch"):
            args = args[:-8].strip()
            branch = True

        node_id = manager.add_attempt(args, branch=branch)
        self.storage.save_experiment(manager.tree)

        prefix = "(branch) " if branch else ""
        return f"""✅ Added {prefix}attempt

Title: {args}
ID: {node_id[:8]}

Current node is now this attempt.
Use '/result' to record the outcome.
"""

    def result(self, args: str) -> str:
        """Record the result of current attempt.

        Usage: /result <success|failed|aborted> [description]
        """
        args = args.strip()
        if not args:
            return "Usage: /result <success|failed|aborted> [description]"

        parts = args.split(None, 1)
        status_str = parts[0].lower()
        description = parts[1] if len(parts) > 1 else ""

        if status_str not in ("success", "failed", "aborted"):
            return f"Invalid status: {status_str}. Use: success, failed, or aborted"

        manager = self._get_manager()
        if not manager:
            return "No active experiment. Start with: /explore <problem>"

        status = Status(status_str)
        manager.tree.get_current().status = status

        if description:
            manager.tree.get_current().description = description

        self.storage.save_experiment(manager.tree)

        icon = "✅" if status == Status.SUCCESS else "❌" if status == Status.FAILED else "🚫"

        return f"""{icon} Result recorded

Status: {status.value.upper()}
{description and f"Description: {description}" or ""}

Use '/back' to return to parent, or '/try' for another attempt.
"""

    def back(self, args: str) -> str:
        """Go back to parent node.

        Usage: /back
        """
        manager = self._get_manager()
        if not manager:
            return "No active experiment."

        result = manager.go_back()
        if result is None:
            return "Already at root node."

        self.storage.save_experiment(manager.tree)

        parent = manager.tree.get_current()
        return f"""⬅️  Back to parent

Current: {parent.title if parent else 'Unknown'}
ID: {result[:8] if result else 'N/A'}
"""

    def jump(self, args: str) -> str:
        """Jump to a specific node.

        Usage: /jump <node_id>
        """
        args = args.strip()
        if not args:
            return "Usage: /jump <node_id>"

        manager = self._get_manager()
        if not manager:
            return "No active experiment."

        # Find node by partial ID
        full_id = None
        for nid in manager.tree.nodes:
            if nid.startswith(args):
                full_id = nid
                break

        if full_id is None:
            return f"Node {args} not found."

        manager.set_current(full_id)
        self.storage.save_experiment(manager.tree)

        node = manager.tree.get_current()
        return f"""➡️  Jumped to node

Title: {node.title if node else 'Unknown'}
ID: {full_id[:8]}
"""

    def tree(self, args: str) -> str:
        """Display the exploration tree.

        Usage: /tree
        """
        manager = self._get_manager()
        if not manager:
            return "No active experiment. Start with: /explore <problem>"

        return manager.render_tree()

    def status(self, args: str) -> str:
        """Show current experiment status.

        Usage: /status
        """
        manager = self._get_manager()
        if not manager:
            return "No active experiments."

        summary = manager.get_tree_summary()
        stats = summary["stats"]

        return f"""Experiment Status
=================
ID: {summary['experiment_id']}
Problem: {summary['problem']}
Created: {summary['created_at']}
Updated: {summary['updated_at']}
Current Node: {summary['current_node'] or 'N/A'}

Statistics
----------
Total Nodes: {stats['total']}
Pending: {stats['pending']}
Success: {stats['success']}
Failed: {stats['failed']}
Aborted: {stats['aborted']}
"""

    def log_list(self, args: str) -> str:
        """List all experiments.

        Usage: /log-list
        """
        experiments = self.storage.list_experiments()

        if not experiments:
            return "No experiments found."

        lines = ["Experiments", "========="]
        for exp in experiments:
            lines.append(
                f"\n{exp['id']}: {exp['problem'][:50]}"
                f"{'...' if len(exp['problem']) > 50 else ''}"
                f"\n  Status: {exp['status']} | Nodes: {exp['node_count']}"
                f" | Updated: {exp['updated_at'][:19]}"
            )

        return "\n".join(lines)

    def log_export(self, args: str) -> str:
        """Export experiment to Markdown.

        Usage: /log-export [exp_id]
        """
        args = args.strip()

        if args:
            tree = self.storage.load_experiment(args)
            if not tree:
                return f"Experiment {args} not found."
        else:
            tree = self.storage.load_latest()
            if not tree:
                return "No experiments found."
            args = tree.root_id[:8]

        output_path = f"experiment_{args}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        exporter = MarkdownExporter(tree)
        exported = exporter.export(output_path)

        return f"""✅ Export complete

File: {exported}
Experiment: {tree.get_root().title if tree.get_root() else 'Unknown'}
"""

    def log_close(self, args: str) -> str:
        """Close the current experiment.

        Usage: /log-close
        """
        manager = self._get_manager()
        if not manager:
            return "No active experiment."

        root = manager.tree.get_root()
        if root:
            root.status = Status.SUCCESS

        self.storage.save_experiment(manager.tree)
        self._current_manager = None

        return f"""✅ Experiment closed

Problem: {root.title if root else 'Unknown'}
Status: COMPLETED

Use '/explore <problem>' to start a new experiment.
"""


def _dispatch_command(skill: ExperimentLogSkill, command: str, args: str) -> str:
    """Dispatch to appropriate handler."""
    handlers = {
        "explore": skill.explore,
        "try": skill.try_attempt,
        "result": skill.result,
        "back": skill.back,
        "jump": skill.jump,
        "tree": skill.tree,
        "status": skill.status,
        "log-list": skill.log_list,
        "log-export": skill.log_export,
        "log-close": skill.log_close,
    }

    handler = handlers.get(command)
    if handler:
        return handler(args)

    return f"Unknown command: {command}. Available: {', '.join(handlers.keys())}"


# Skill interface for Claude Code
def handle_skill_command(command: str, args: str) -> str:
    """Handle skill commands from Claude Code.

    This function handles traditional slash commands like:
    - /explore <problem>
    - /try <description>
    - /result <status>
    - /tree
    - /log-export
    - /log-close
    """
    skill = ExperimentLogSkill()
    return _dispatch_command(skill, command, args)


def handle_natural_language_input(text: str) -> str | None:
    """Handle natural language input for experiment logging.

    This function processes natural language commands like:
    - "启动实验日志，解决性能问题"
    - "尝试使用Redis缓存方案"
    - "这次成功了"
    - "导出实验报告"
    - "查看实验树"
    - "关闭实验"

    Returns:
        Response string if input was handled as experiment command
        None if input should be processed normally (not experiment-related)
    """
    # Check if this looks like natural language we should handle
    if not should_handle_as_natural_language(text):
        return None

    # Try to parse as experiment command
    result = process_input(text)
    if result is None:
        return None

    command, args = result

    # Execute the command
    skill = ExperimentLogSkill()
    return _dispatch_command(skill, command, args)


def handle_user_input(text: str) -> str | None:
    """Main entry point for handling user input.

    This function handles both:
    1. Traditional slash commands (/explore, /try, etc.)
    2. Natural language commands ("启动实验", "尝试方案", etc.)

    Returns:
        Response string if input was handled
        None if input should be processed by other handlers
    """
    text = text.strip()

    # Handle slash commands
    if text.startswith("/"):
        # Parse command and args
        parts = text[1:].split(None, 1)
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        return handle_skill_command(command, args)

    # Handle natural language
    return handle_natural_language_input(text)


if __name__ == "__main__":
    # For testing
    skill = ExperimentLogSkill()
    print(skill.explore("Test problem"))
    print(skill.try_attempt("Try solution A"))
    print(skill.result("failed Doesn't work"))

    # Test natural language processing
    print("\n--- Natural Language Tests ---")
    test_inputs = [
        "启动实验日志，解决性能问题",
        "尝试使用Redis缓存",
        "这次成功了，响应时间降到50ms",
        "导出实验报告",
        "查看实验树",
        "关闭实验",
    ]
    for text in test_inputs:
        result = handle_natural_language_input(text)
        print(f"\nInput: {text}")
        print(f"Result: {result[:100] if result else 'None'}...")
