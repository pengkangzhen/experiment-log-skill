"""Tree operations for experiment management."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from experiment_log.models import ExperimentNode, ExperimentTree, NodeType, Status


class ExperimentTreeManager:
    """Manages operations on an experiment tree."""

    def __init__(self, tree: ExperimentTree | None = None):
        self.tree = tree or ExperimentTree()

    def create_experiment(self, problem: str, description: str = "") -> str:
        """Create a new experiment with a root node."""
        root = ExperimentNode(
            node_type=NodeType.ROOT,
            title=problem,
            description=description,
            status=Status.PENDING,
        )
        self.tree.root_id = root.id
        self.tree.current_node_id = root.id
        self.tree.nodes[root.id] = root
        self.tree.created_at = datetime.now()
        self.tree.updated_at = datetime.now()
        return root.id

    def add_attempt(
        self,
        title: str,
        description: str = "",
        metadata: dict[str, Any] | None = None,
        branch: bool = False,
    ) -> str:
        """Add a new attempt node under current node.

        Args:
            title: Title of the attempt
            description: Detailed description
            metadata: Additional metadata (code snippets, errors, etc.)
            branch: If True, add as sibling to current; if False, add as child
        """
        current = self.tree.get_current()
        if not current:
            raise ValueError("No current node selected")

        parent_id = current.id if not branch else current.parent_id
        if branch and not parent_id:
            parent_id = current.id  # Can't branch from root

        node = ExperimentNode(
            parent_id=parent_id,
            node_type=NodeType.ATTEMPT,
            title=title,
            description=description,
            metadata=metadata or {},
            status=Status.PENDING,
        )

        self.tree.nodes[node.id] = node
        parent = self.tree.nodes.get(parent_id)
        if parent:
            parent.children.append(node.id)

        self.tree.current_node_id = node.id
        self.tree.updated_at = datetime.now()
        return node.id

    def add_result(
        self,
        status: Status,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add a result node under current node."""
        current = self.tree.get_current()
        if not current:
            raise ValueError("No current node selected")

        node = ExperimentNode(
            parent_id=current.id,
            node_type=NodeType.RESULT,
            title=f"Result: {status.value}",
            description=description,
            metadata=metadata or {},
            status=status,
        )

        self.tree.nodes[node.id] = node
        current.children.append(node.id)
        current.status = status  # Update parent status too

        self.tree.current_node_id = node.id
        self.tree.updated_at = datetime.now()
        return node.id

    def update_status(self, node_id: str, status: Status) -> None:
        """Update the status of a node."""
        node = self.tree.nodes.get(node_id)
        if not node:
            raise ValueError(f"Node {node_id} not found")
        node.status = status
        self.tree.updated_at = datetime.now()

    def set_current(self, node_id: str) -> None:
        """Set the current active node."""
        if node_id not in self.tree.nodes:
            raise ValueError(f"Node {node_id} not found")
        self.tree.current_node_id = node_id
        self.tree.updated_at = datetime.now()

    def go_back(self) -> str | None:
        """Move current node to parent. Returns new current node id or None if at root."""
        current = self.tree.get_current()
        if not current or not current.parent_id:
            return None
        self.tree.current_node_id = current.parent_id
        return self.tree.current_node_id

    def get_tree_summary(self) -> dict[str, Any]:
        """Get a summary of the experiment tree."""
        root = self.tree.get_root()
        if not root:
            return {"error": "No root node"}

        def count_nodes(node_id: str) -> dict[str, int]:
            node = self.tree.nodes.get(node_id)
            if not node:
                return {"total": 0, "pending": 0, "success": 0, "failed": 0, "aborted": 0}

            counts = {"total": 1, "pending": 0, "success": 0, "failed": 0, "aborted": 0}
            counts[node.status.value] += 1

            for child_id in node.children:
                child_counts = count_nodes(child_id)
                for key in counts:
                    counts[key] += child_counts[key]

            return counts

        stats = count_nodes(root.id)

        return {
            "experiment_id": self.tree.root_id[:8],
            "problem": root.title,
            "created_at": self.tree.created_at,
            "updated_at": self.tree.updated_at,
            "stats": stats,
            "current_node": self.tree.get_current().title if self.tree.get_current() else None,
        }

    def render_tree(self) -> str:
        """Render the tree as a string representation."""
        root = self.tree.get_root()
        if not root:
            return "No experiment started"

        lines = []

        def render_node(node_id: str, prefix: str = "", is_last: bool = True) -> None:
            node = self.tree.nodes.get(node_id)
            if not node:
                return

            connector = "└── " if is_last else "├── "
            current_marker = " <-- current" if node_id == self.tree.current_node_id else ""
            lines.append(f"{prefix}{connector}{node.label} [{node.status.icon}]{current_marker}")

            # 显示当前操作
            if node.current_action:
                lines.append(f"{prefix}    └─ 当前操作: {node.current_action[:50]}")

            # 显示错误信息
            if node.error_info:
                lines.append(f"{prefix}    └─ 错误: {node.error_info[:50]}")

            # 显示结果
            if node.action_result:
                lines.append(f"{prefix}    └─ 结果: {node.action_result[:50]}")

            children = [
                self.tree.nodes.get(cid) for cid in node.children if cid in self.tree.nodes
            ]
            for i, child in enumerate(children):
                if child:
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    render_node(child.id, new_prefix, i == len(children) - 1)

        # 渲染根节点
        lines.append(f"{root.label} [{root.status.icon}]" +
                    (" <-- current" if root.id == self.tree.current_node_id else ""))

        # 显示根节点的结构化信息
        if root.problem_context:
            lines.append(f"  └─ 问题: {root.problem_context[:100]}")
        if root.possible_actions:
            actions_str = ", ".join(root.possible_actions[:3])
            lines.append(f"  └─ 可能操作: {actions_str}")
        if root.current_action:
            lines.append(f"  └─ 当前操作: {root.current_action[:50]}")

        children = [self.tree.nodes.get(cid) for cid in root.children if cid in self.tree.nodes]
        for i, child in enumerate(children):
            if child:
                render_node(child.id, "", i == len(children) - 1)

        return "\n".join(lines)
