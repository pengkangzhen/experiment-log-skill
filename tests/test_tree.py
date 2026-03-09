"""Tests for experiment_log tree operations."""

from datetime import datetime

import pytest

from experiment_log.models import ExperimentNode, ExperimentTree, NodeType, Status
from experiment_log.tree import ExperimentTreeManager


class TestExperimentTreeManager:
    """Tests for ExperimentTreeManager."""

    def test_create_experiment(self):
        """Test creating a new experiment."""
        manager = ExperimentTreeManager()

        exp_id = manager.create_experiment("Test Problem", "Test Description")

        assert manager.tree.root_id == exp_id
        assert manager.tree.current_node_id == exp_id
        assert exp_id in manager.tree.nodes

        root = manager.tree.get_root()
        assert root.title == "Test Problem"
        assert root.description == "Test Description"
        assert root.node_type == NodeType.ROOT
        assert root.status == Status.PENDING

    def test_add_attempt(self):
        """Test adding an attempt node."""
        manager = ExperimentTreeManager()
        manager.create_experiment("Test Problem")

        attempt_id = manager.add_attempt("Test Attempt", "Attempt Description")

        assert attempt_id in manager.tree.nodes
        assert manager.tree.current_node_id == attempt_id

        attempt = manager.tree.nodes[attempt_id]
        assert attempt.title == "Test Attempt"
        assert attempt.description == "Attempt Description"
        assert attempt.node_type == NodeType.ATTEMPT
        assert attempt.parent_id == manager.tree.root_id

        root = manager.tree.get_root()
        assert attempt_id in root.children

    def test_add_attempt_no_current(self):
        """Test adding attempt without current node raises error."""
        manager = ExperimentTreeManager()

        with pytest.raises(ValueError, match="No current node"):
            manager.add_attempt("Test Attempt")

    def test_add_attempt_branch(self):
        """Test adding a branch attempt."""
        manager = ExperimentTreeManager()
        manager.create_experiment("Test Problem")
        first_attempt = manager.add_attempt("First Attempt")

        # Add branch from first attempt
        second_attempt = manager.add_attempt("Second Attempt", branch=True)

        # Both attempts should have root as parent
        assert manager.tree.nodes[first_attempt].parent_id == manager.tree.root_id
        assert manager.tree.nodes[second_attempt].parent_id == manager.tree.root_id

    def test_add_result(self):
        """Test adding a result node."""
        manager = ExperimentTreeManager()
        manager.create_experiment("Test Problem")
        attempt_id = manager.add_attempt("Test Attempt")

        result_id = manager.add_result(Status.SUCCESS, "It worked!")

        assert result_id in manager.tree.nodes
        result = manager.tree.nodes[result_id]
        assert result.node_type == NodeType.RESULT
        assert result.status == Status.SUCCESS
        assert result.description == "It worked!"
        assert result.parent_id == attempt_id

        # Parent attempt should also be updated
        attempt = manager.tree.nodes[attempt_id]
        assert attempt.status == Status.SUCCESS
        assert result_id in attempt.children

    def test_add_result_no_current(self):
        """Test adding result without current node raises error."""
        manager = ExperimentTreeManager()

        with pytest.raises(ValueError, match="No current node"):
            manager.add_result(Status.SUCCESS)

    def test_update_status(self):
        """Test updating node status."""
        manager = ExperimentTreeManager()
        manager.create_experiment("Test Problem")
        attempt_id = manager.add_attempt("Test Attempt")

        manager.update_status(attempt_id, Status.FAILED)

        attempt = manager.tree.nodes[attempt_id]
        assert attempt.status == Status.FAILED

    def test_update_status_invalid_node(self):
        """Test updating status of non-existent node raises error."""
        manager = ExperimentTreeManager()

        with pytest.raises(ValueError, match="Node invalid not found"):
            manager.update_status("invalid", Status.SUCCESS)

    def test_set_current(self):
        """Test setting current node."""
        manager = ExperimentTreeManager()
        manager.create_experiment("Test Problem")
        attempt_id = manager.add_attempt("Test Attempt")

        # Go back to root
        manager.set_current(manager.tree.root_id)
        assert manager.tree.current_node_id == manager.tree.root_id

    def test_set_current_invalid(self):
        """Test setting invalid current node raises error."""
        manager = ExperimentTreeManager()

        with pytest.raises(ValueError, match="Node invalid not found"):
            manager.set_current("invalid")

    def test_go_back(self):
        """Test going back to parent."""
        manager = ExperimentTreeManager()
        manager.create_experiment("Test Problem")
        manager.add_attempt("Test Attempt")

        result = manager.go_back()

        assert result == manager.tree.root_id
        assert manager.tree.current_node_id == manager.tree.root_id

    def test_go_back_from_root(self):
        """Test going back from root returns None."""
        manager = ExperimentTreeManager()
        manager.create_experiment("Test Problem")

        result = manager.go_back()

        assert result is None
        assert manager.tree.current_node_id == manager.tree.root_id

    def test_get_tree_summary(self):
        """Test getting tree summary."""
        manager = ExperimentTreeManager()
        manager.create_experiment("Test Problem")
        manager.add_attempt("Attempt 1")
        manager.add_result(Status.FAILED)

        # Go back twice (from result to attempt1 to root)
        manager.go_back()
        manager.go_back()
        manager.add_attempt("Attempt 2")
        manager.add_result(Status.SUCCESS)

        summary = manager.get_tree_summary()

        assert summary["experiment_id"] == manager.tree.root_id[:8]
        assert summary["problem"] == "Test Problem"
        assert summary["stats"]["total"] == 5  # root + 2 attempts + 2 results
        # Both attempts and results have their respective statuses
        assert summary["stats"]["success"] == 2  # attempt2 + result2
        assert summary["stats"]["failed"] == 2   # attempt1 + result1

    def test_get_tree_summary_no_root(self):
        """Test summary when no root exists."""
        manager = ExperimentTreeManager()

        summary = manager.get_tree_summary()

        assert "error" in summary

    def test_render_tree(self):
        """Test tree rendering."""
        manager = ExperimentTreeManager()
        manager.create_experiment("Test Problem")
        manager.add_attempt("Attempt 1")
        manager.add_result(Status.FAILED)

        output = manager.render_tree()

        assert "Test Problem" in output
        assert "Attempt 1" in output
        assert "Result: failed" in output
        assert "<-- current" in output

    def test_render_tree_no_root(self):
        """Test rendering without root."""
        manager = ExperimentTreeManager()

        output = manager.render_tree()

        assert output == "No experiment started"
