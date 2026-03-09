"""Data models for experiment logging."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any
import uuid


class NodeType(Enum):
    """Type of experiment node."""

    ROOT = "root"  # The problem/goal being explored
    ATTEMPT = "attempt"  # An exploration attempt
    RESULT = "result"  # A result/solution


class Status(Enum):
    """Status of an experiment node."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    ABORTED = "aborted"

    def __str__(self) -> str:
        return self.value

    @property
    def icon(self) -> str:
        """Return an icon representing the status."""
        icons = {
            Status.PENDING: "⏳",
            Status.SUCCESS: "✅",
            Status.FAILED: "❌",
            Status.ABORTED: "🚫",
        }
        return icons[self]


@dataclass
class ExperimentNode:
    """A node in the experiment tree representing a step in the exploration."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_id: str | None = None
    node_type: NodeType = NodeType.ATTEMPT
    title: str = ""
    description: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    status: Status = Status.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)
    children: list[str] = field(default_factory=list)

    # 详细实验信息字段
    problem_context: str = ""  # 当前遇到的问题上下文
    possible_actions: list[str] = field(default_factory=list)  # 可能需要的操作列表
    current_action: str = ""  # 当前正在执行的操作
    action_result: str = ""  # 操作执行结果
    error_info: str = ""  # 错误信息（如果有）
    code_snippets: list[str] = field(default_factory=list)  # 相关代码片段
    files_modified: list[str] = field(default_factory=list)  # 修改的文件列表

    def to_dict(self) -> dict[str, Any]:
        """Convert node to dictionary for serialization."""
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "node_type": self.node_type.value,
            "title": self.title,
            "description": self.description,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "metadata": self.metadata,
            "children": self.children,
            "problem_context": self.problem_context,
            "possible_actions": self.possible_actions,
            "current_action": self.current_action,
            "action_result": self.action_result,
            "error_info": self.error_info,
            "code_snippets": self.code_snippets,
            "files_modified": self.files_modified,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentNode:
        """Create node from dictionary."""
        return cls(
            id=data["id"],
            parent_id=data.get("parent_id"),
            node_type=NodeType(data["node_type"]),
            title=data["title"],
            description=data.get("description", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            status=Status(data["status"]),
            metadata=data.get("metadata", {}),
            children=data.get("children", []),
            problem_context=data.get("problem_context", ""),
            possible_actions=data.get("possible_actions", []),
            current_action=data.get("current_action", ""),
            action_result=data.get("action_result", ""),
            error_info=data.get("error_info", ""),
            code_snippets=data.get("code_snippets", []),
            files_modified=data.get("files_modified", []),
        )

    @property
    def label(self) -> str:
        """Get a short label for the node."""
        prefix = {
            NodeType.ROOT: "[P]",
            NodeType.ATTEMPT: "[A]",
            NodeType.RESULT: "[R]",
        }[self.node_type]
        return f"{prefix} {self.title}"


@dataclass
class ExperimentTree:
    """Represents a complete experiment with its tree structure."""

    root_id: str = ""
    nodes: dict[str, ExperimentNode] = field(default_factory=dict)
    current_node_id: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert tree to dictionary for serialization."""
        return {
            "root_id": self.root_id,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "current_node_id": self.current_node_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentTree:
        """Create tree from dictionary."""
        tree = cls(
            root_id=data["root_id"],
            nodes={},
            current_node_id=data.get("current_node_id", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
        for node_id, node_data in data.get("nodes", {}).items():
            tree.nodes[node_id] = ExperimentNode.from_dict(node_data)
        return tree

    def get_root(self) -> ExperimentNode | None:
        """Get the root node of the tree."""
        return self.nodes.get(self.root_id)

    def get_current(self) -> ExperimentNode | None:
        """Get the current active node."""
        return self.nodes.get(self.current_node_id)

    def get_children(self, node_id: str) -> list[ExperimentNode]:
        """Get all children of a node."""
        node = self.nodes.get(node_id)
        if not node:
            return []
        return [self.nodes.get(cid) for cid in node.children if cid in self.nodes]

    def get_parent(self, node_id: str) -> ExperimentNode | None:
        """Get parent of a node."""
        node = self.nodes.get(node_id)
        if not node or not node.parent_id:
            return None
        return self.nodes.get(node.parent_id)

    def get_path_to_root(self, node_id: str) -> list[ExperimentNode]:
        """Get path from node to root (inclusive)."""
        path = []
        current = self.nodes.get(node_id)
        while current:
            path.append(current)
            if current.parent_id:
                current = self.nodes.get(current.parent_id)
            else:
                break
        return list(reversed(path))
