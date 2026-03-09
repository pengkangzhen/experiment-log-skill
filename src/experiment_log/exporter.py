"""Markdown export functionality for experiment logs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from experiment_log.models import ExperimentNode, ExperimentTree, NodeType, Status


class MarkdownExporter:
    """Exports experiment trees to Markdown format."""

    def __init__(self, tree: ExperimentTree):
        self.tree = tree

    def export(self, output_path: Path | str | None = None) -> Path:
        """Export the experiment tree to Markdown.

        Args:
            output_path: Path to save the markdown file. If None, generates
                        a path based on experiment ID and timestamp.

        Returns:
            Path to the exported file
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = Path(f"experiment_{self.tree.root_id[:8]}_{timestamp}.md")
        else:
            output_path = Path(output_path)

        content = self._generate_markdown()

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    def _generate_markdown(self) -> str:
        """Generate the full Markdown content."""
        root = self.tree.get_root()
        if not root:
            return "# No Experiment Data\n\nNo experiment found.\n"

        lines = [
            f"# Experiment Log: {root.title}",
            "",
            "## Metadata",
            "",
            f"- **Experiment ID**: {self.tree.root_id[:8]}",
            f"- **Started**: {self._format_datetime(self.tree.created_at)}",
            f"- **Last Updated**: {self._format_datetime(self.tree.updated_at)}",
            f"- **Status**: {root.status.value.upper()}",
            f"- **Total Nodes**: {len(self.tree.nodes)}",
            "",
            "---",
            "",
            "## Exploration Tree",
            "",
            "```",
        ]

        # Add tree visualization
        lines.extend(self._render_tree_ascii().split("\n"))

        lines.extend([
            "```",
            "",
            "---",
            "",
            "## Detailed Records",
            "",
        ])

        # Add detailed records for each node
        for node_id, node in self._get_nodes_in_order():
            lines.extend(self._render_node_details(node))

        return "\n".join(lines)

    def _render_tree_ascii(self) -> str:
        """Render the tree in ASCII art format."""
        root = self.tree.get_root()
        if not root:
            return ""

        lines = []

        def render(node_id: str, prefix: str = "", is_last: bool = True) -> None:
            node = self.tree.nodes.get(node_id)
            if not node:
                return

            connector = "└── " if is_last else "├── "
            status_icon = self._get_status_icon(node.status)
            lines.append(f"{prefix}{connector}[{node.id[:4]}] {node.title} {status_icon}")

            children = [
                self.tree.nodes.get(cid) for cid in node.children if cid in self.tree.nodes
            ]
            for i, child in enumerate(children):
                if child:
                    extension = "    " if is_last else "│   "
                    render(child.id, prefix + extension, i == len(children) - 1)

        status_icon = self._get_status_icon(root.status)
        lines.append(f"[{root.id[:4]}] {root.title} {status_icon}")

        children = [self.tree.nodes.get(cid) for cid in root.children if cid in self.tree.nodes]
        for i, child in enumerate(children):
            if child:
                render(child.id, "", i == len(children) - 1)

        return "\n".join(lines)

    def _get_status_icon(self, status: Status) -> str:
        """Get a simple icon for a status."""
        icons = {
            Status.PENDING: "⏳",
            Status.SUCCESS: "✅",
            Status.FAILED: "❌",
            Status.ABORTED: "🚫",
        }
        return icons.get(status, "❓")

    def _get_nodes_in_order(self) -> list[tuple[str, ExperimentNode]]:
        """Get nodes in breadth-first order."""
        root = self.tree.get_root()
        if not root:
            return []

        result = []
        queue = [root.id]
        visited = set()

        while queue:
            node_id = queue.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)

            node = self.tree.nodes.get(node_id)
            if node:
                result.append((node_id, node))
                queue.extend(node.children)

        return result

    def _render_node_details(self, node: ExperimentNode) -> list[str]:
        """Render detailed information for a node."""
        lines = [
            f"### [{node.id[:4]}] {node.title}",
            "",
            f"**Type**: {node.node_type.value}",
            f"**Status**: {node.status.value.upper()} {self._get_status_icon(node.status)}",
            f"**Time**: {self._format_datetime(node.timestamp)}",
        ]

        if node.parent_id:
            parent = self.tree.nodes.get(node.parent_id)
            if parent:
                lines.append(f"**Parent**: [{parent.id[:4]}] {parent.title}")

        if node.children:
            children_titles = []
            for cid in node.children:
                child = self.tree.nodes.get(cid)
                if child:
                    children_titles.append(f"[{cid[:4]}] {child.title}")
            if children_titles:
                lines.append(f"**Children**: {', '.join(children_titles)}")

        lines.append("")

        # 问题上下文
        if node.problem_context:
            lines.extend([
                "**问题上下文**:",
                "",
                node.problem_context,
                "",
            ])

        # 可能的操作
        if node.possible_actions:
            lines.append("**可能的操作**:")
            lines.append("")
            for i, action in enumerate(node.possible_actions, 1):
                lines.append(f"  {i}. {action}")
            lines.append("")

        # 当前执行的操作
        if node.current_action:
            lines.extend([
                "**当前操作**:",
                "",
                f"  > {node.current_action}",
                "",
            ])

        # 执行结果
        if node.action_result:
            lines.extend([
                "**执行结果**:",
                "",
                node.action_result,
                "",
            ])

        # 错误信息
        if node.error_info:
            lines.extend([
                "**错误信息**:",
                "",
                f"```",
                node.error_info,
                "```",
                "",
            ])

        # 涉及的文件
        if node.files_modified:
            lines.append("**涉及文件**:")
            lines.append("")
            for f in node.files_modified:
                lines.append(f"  - `{f}`")
            lines.append("")

        # 代码片段
        if node.code_snippets:
            lines.append("**代码片段**:")
            lines.append("")
            for i, code in enumerate(node.code_snippets, 1):
                lines.append(f"  片段 {i}:")
                lines.append("```")
                lines.append(code)
                lines.append("```")
                lines.append("")

        if node.description:
            lines.extend([
                "**描述**:",
                "",
                node.description,
                "",
            ])

        # Metadata sections
        if node.metadata:
            lines.extend(self._render_metadata(node.metadata))

        lines.append("---")
        lines.append("")

        return lines

    def _render_metadata(self, metadata: dict[str, Any]) -> list[str]:
        """Render metadata sections."""
        lines = []

        # Code snippet
        if "code" in metadata:
            code = metadata["code"]
            lang = metadata.get("language", "python")
            lines.extend([
                "**Code**:",
                f"```{lang}",
                code,
                "```",
                "",
            ])

        # Error info
        if "error" in metadata:
            lines.extend([
                "**Error**:",
                "```",
                str(metadata["error"]),
                "```",
                "",
            ])

        # Other metadata
        other_meta = {k: v for k, v in metadata.items()
                     if k not in ("code", "language", "error")}
        if other_meta:
            lines.append("**Additional Info**:")
            lines.append("")
            for key, value in other_meta.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        return lines

    def _format_datetime(self, dt: datetime) -> str:
        """Format datetime for display."""
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def export_experiment(
    tree: ExperimentTree,
    output_path: Path | str | None = None,
) -> Path:
    """Convenience function to export an experiment tree.

    Args:
        tree: The experiment tree to export
        output_path: Optional output path

    Returns:
        Path to the exported file
    """
    exporter = MarkdownExporter(tree)
    return exporter.export(output_path)
