"""Tests for experiment_log models."""

import json
from datetime import datetime

import pytest

from experiment_log.models import (
    ExperimentNode,
    ExperimentTree,
    NodeType,
    Status,
)


class TestStatus:
    """Tests for Status enum."""

    def test_status_values(self):
        """Test status enum values."""
        assert Status.PENDING.value == "pending"
        assert Status.SUCCESS.value == "success"
        assert Status.FAILED.value == "failed"
        assert Status.ABORTED.value == "aborted"

    def test_status_icons(self):
        """Test status icons."""
        assert Status.PENDING.icon == "⏳"
        assert Status.SUCCESS.icon == "✅"
        assert Status.FAILED.icon == "❌"
        assert Status.ABORTED.icon == "🚫"


class TestExperimentNode:
    """Tests for ExperimentNode."""

    def test_node_creation(self):
        """Test basic node creation."""
        node = ExperimentNode(
            title="Test Node",
            description="Test Description",
            node_type=NodeType.ATTEMPT,
        )

        assert node.title == "Test Node"
        assert node.description == "Test Description"
        assert node.node_type == NodeType.ATTEMPT
        assert node.status == Status.PENDING
        assert len(node.id) == 8  # UUID truncated to 8 chars
        assert node.parent_id is None

    def test_node_to_dict(self):
        """Test node serialization."""
        node = ExperimentNode(
            id="test1234",
            parent_id="parent5678",
            node_type=NodeType.ATTEMPT,
            title="Test",
            description="Description",
            timestamp=datetime(2024, 3, 8, 10, 0, 0),
            status=Status.SUCCESS,
            metadata={"key": "value"},
            children=["child1", "child2"],
        )

        data = node.to_dict()

        assert data["id"] == "test1234"
        assert data["parent_id"] == "parent5678"
        assert data["node_type"] == "attempt"
        assert data["title"] == "Test"
        assert data["description"] == "Description"
        assert data["timestamp"] == "2024-03-08T10:00:00"
        assert data["status"] == "success"
        assert data["metadata"] == {"key": "value"}
        assert data["children"] == ["child1", "child2"]

    def test_node_from_dict(self):
        """Test node deserialization."""
        data = {
            "id": "test1234",
            "parent_id": "parent5678",
            "node_type": "attempt",
            "title": "Test",
            "description": "Description",
            "timestamp": "2024-03-08T10:00:00",
            "status": "success",
            "metadata": {"key": "value"},
            "children": ["child1", "child2"],
        }

        node = ExperimentNode.from_dict(data)

        assert node.id == "test1234"
        assert node.parent_id == "parent5678"
        assert node.node_type == NodeType.ATTEMPT
        assert node.title == "Test"
        assert node.description == "Description"
        assert node.timestamp == datetime(2024, 3, 8, 10, 0, 0)
        assert node.status == Status.SUCCESS
        assert node.metadata == {"key": "value"}
        assert node.children == ["child1", "child2"]

    def test_node_label(self):
        """Test node label generation."""
        root = ExperimentNode(title="Root Problem", node_type=NodeType.ROOT)
        attempt = ExperimentNode(title="Test Attempt", node_type=NodeType.ATTEMPT)
        result = ExperimentNode(title="Test Result", node_type=NodeType.RESULT)

        assert root.label == "[P] Root Problem"
        assert attempt.label == "[A] Test Attempt"
        assert result.label == "[R] Test Result"


class TestExperimentTree:
    """Tests for ExperimentTree."""

    def test_tree_creation(self):
        """Test basic tree creation."""
        tree = ExperimentTree()

        assert tree.root_id == ""
        assert tree.nodes == {}
        assert tree.current_node_id == ""

    def test_tree_to_dict(self):
        """Test tree serialization."""
        root = ExperimentNode(id="root1234", title="Root", node_type=NodeType.ROOT)
        tree = ExperimentTree(
            root_id="root1234",
            nodes={"root1234": root},
            current_node_id="root1234",
            created_at=datetime(2024, 3, 8, 10, 0, 0),
            updated_at=datetime(2024, 3, 8, 11, 0, 0),
        )

        data = tree.to_dict()

        assert data["root_id"] == "root1234"
        assert "root1234" in data["nodes"]
        assert data["current_node_id"] == "root1234"
        assert data["created_at"] == "2024-03-08T10:00:00"
        assert data["updated_at"] == "2024-03-08T11:00:00"

    def test_tree_from_dict(self):
        """Test tree deserialization."""
        data = {
            "root_id": "root1234",
            "nodes": {
                "root1234": {
                    "id": "root1234",
                    "parent_id": None,
                    "node_type": "root",
                    "title": "Root",
                    "description": "",
                    "timestamp": "2024-03-08T10:00:00",
                    "status": "pending",
                    "metadata": {},
                    "children": [],
                }
            },
            "current_node_id": "root1234",
            "created_at": "2024-03-08T10:00:00",
            "updated_at": "2024-03-08T11:00:00",
        }

        tree = ExperimentTree.from_dict(data)

        assert tree.root_id == "root1234"
        assert len(tree.nodes) == 1
        assert tree.current_node_id == "root1234"
        assert "root1234" in tree.nodes

    def test_get_root(self):
        """Test getting root node."""
        root = ExperimentNode(id="root1234", title="Root", node_type=NodeType.ROOT)
        tree = ExperimentTree(root_id="root1234", nodes={"root1234": root})

        assert tree.get_root() == root

    def test_get_current(self):
        """Test getting current node."""
        node = ExperimentNode(id="node1234", title="Node")
        tree = ExperimentTree(
            current_node_id="node1234",
            nodes={"node1234": node}
        )

        assert tree.get_current() == node

    def test_get_children(self):
        """Test getting children of a node."""
        parent = ExperimentNode(id="parent1234", children=["child1", "child2"])
        child1 = ExperimentNode(id="child1", parent_id="parent1234")
        child2 = ExperimentNode(id="child2", parent_id="parent1234")

        tree = ExperimentTree(nodes={
            "parent1234": parent,
            "child1": child1,
            "child2": child2,
        })

        children = tree.get_children("parent1234")
        assert len(children) == 2
        assert child1 in children
        assert child2 in children

    def test_get_parent(self):
        """Test getting parent of a node."""
        parent = ExperimentNode(id="parent1234")
        child = ExperimentNode(id="child1234", parent_id="parent1234")

        tree = ExperimentTree(nodes={
            "parent1234": parent,
            "child1234": child,
        })

        assert tree.get_parent("child1234") == parent
        assert tree.get_parent("parent1234") is None

    def test_get_path_to_root(self):
        """Test getting path from node to root."""
        root = ExperimentNode(id="root1234", node_type=NodeType.ROOT)
        child = ExperimentNode(id="child1234", parent_id="root1234")
        grandchild = ExperimentNode(id="grandchild1234", parent_id="child1234")

        tree = ExperimentTree(
            root_id="root1234",
            nodes={
                "root1234": root,
                "child1234": child,
                "grandchild1234": grandchild,
            }
        )

        path = tree.get_path_to_root("grandchild1234")
        assert len(path) == 3
        assert path[0] == root
        assert path[1] == child
        assert path[2] == grandchild
