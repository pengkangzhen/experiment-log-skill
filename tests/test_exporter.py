"""Tests for experiment_log exporter."""

from datetime import datetime
from pathlib import Path

import pytest

from experiment_log.exporter import MarkdownExporter, export_experiment
from experiment_log.models import ExperimentNode, ExperimentTree, NodeType, Status
from experiment_log.tree import ExperimentTreeManager


class TestMarkdownExporter:
    """Tests for MarkdownExporter."""

    @pytest.fixture
    def sample_tree(self):
        """Create a sample experiment tree."""
        manager = ExperimentTreeManager()
        manager.create_experiment("Test Performance Problem")

        # Add attempts
        manager.add_attempt("Use Redis Cache", "Try caching with Redis")
        manager.update_status(manager.tree.current_node_id, Status.FAILED)
        manager.tree.nodes[manager.tree.current_node_id].metadata = {
            "code": "redis.set(key, data)",
            "error": "TimeoutError: Connection failed",
        }

        manager.go_back()
        manager.add_attempt("Use Local Cache")
        manager.update_status(manager.tree.current_node_id, Status.SUCCESS)

        return manager.tree

    def test_export_creates_file(self, sample_tree, tmp_path):
        """Test that export creates a file."""
        exporter = MarkdownExporter(sample_tree)
        output_path = tmp_path / "test_export.md"

        result = exporter.export(output_path)

        assert result.exists()
        assert result == output_path

    def test_export_default_path(self, sample_tree):
        """Test default export path generation."""
        exporter = MarkdownExporter(sample_tree)

        result = exporter.export()

        assert result.exists()
        assert result.name.startswith(f"experiment_{sample_tree.root_id[:8]}_")
        assert result.suffix == ".md"

        # Clean up
        result.unlink()

    def test_export_content_structure(self, sample_tree, tmp_path):
        """Test the structure of exported content."""
        exporter = MarkdownExporter(sample_tree)
        output_path = tmp_path / "test_export.md"

        exporter.export(output_path)

        with open(output_path) as f:
            content = f.read()

        # Check main sections
        assert "# Experiment Log: Test Performance Problem" in content
        assert "## Metadata" in content
        assert "## Exploration Tree" in content
        assert "## Detailed Records" in content

    def test_export_metadata(self, sample_tree, tmp_path):
        """Test metadata in exported content."""
        exporter = MarkdownExporter(sample_tree)
        output_path = tmp_path / "test_export.md"

        exporter.export(output_path)

        with open(output_path) as f:
            content = f.read()

        assert "Test Performance Problem" in content
        assert sample_tree.root_id[:8] in content
        assert "Total Nodes" in content

    def test_export_tree_visualization(self, sample_tree, tmp_path):
        """Test tree visualization in export."""
        exporter = MarkdownExporter(sample_tree)
        output_path = tmp_path / "test_export.md"

        exporter.export(output_path)

        with open(output_path) as f:
            content = f.read()

        # Check tree structure
        assert "Test Performance Problem" in content
        assert "Use Redis Cache" in content
        assert "Use Local Cache" in content

    def test_export_node_details(self, sample_tree, tmp_path):
        """Test node details in export."""
        exporter = MarkdownExporter(sample_tree)
        output_path = tmp_path / "test_export.md"

        exporter.export(output_path)

        with open(output_path) as f:
            content = f.read()

        # Check node details
        assert "Use Redis Cache" in content
        assert "Try caching with Redis" in content
        assert "FAILED" in content

    def test_export_code_blocks(self, sample_tree, tmp_path):
        """Test code blocks in export."""
        exporter = MarkdownExporter(sample_tree)
        output_path = tmp_path / "test_export.md"

        exporter.export(output_path)

        with open(output_path) as f:
            content = f.read()

        assert "```" in content
        assert "redis.set(key, data)" in content

    def test_export_error_blocks(self, sample_tree, tmp_path):
        """Test error blocks in export."""
        exporter = MarkdownExporter(sample_tree)
        output_path = tmp_path / "test_export.md"

        exporter.export(output_path)

        with open(output_path) as f:
            content = f.read()

        assert "TimeoutError: Connection failed" in content

    def test_export_empty_tree(self, tmp_path):
        """Test exporting empty tree."""
        tree = ExperimentTree()
        exporter = MarkdownExporter(tree)
        output_path = tmp_path / "empty_export.md"

        exporter.export(output_path)

        with open(output_path) as f:
            content = f.read()

        assert "No Experiment Data" in content

    def test_format_datetime(self, sample_tree):
        """Test datetime formatting."""
        exporter = MarkdownExporter(sample_tree)

        dt = datetime(2024, 3, 8, 14, 30, 0)
        formatted = exporter._format_datetime(dt)

        assert formatted == "2024-03-08 14:30:00"

    def test_get_status_icon(self, sample_tree):
        """Test status icon mapping."""
        exporter = MarkdownExporter(sample_tree)

        assert exporter._get_status_icon(Status.PENDING) == "⏳"
        assert exporter._get_status_icon(Status.SUCCESS) == "✅"
        assert exporter._get_status_icon(Status.FAILED) == "❌"
        assert exporter._get_status_icon(Status.ABORTED) == "🚫"

    def test_get_nodes_in_order(self, sample_tree):
        """Test node ordering."""
        exporter = MarkdownExporter(sample_tree)

        nodes = exporter._get_nodes_in_order()

        # Should be root first (breadth-first)
        assert len(nodes) == 3  # root + 2 attempts
        assert nodes[0][1].node_type == NodeType.ROOT

    def test_render_metadata(self, sample_tree):
        """Test metadata rendering."""
        exporter = MarkdownExporter(sample_tree)

        metadata = {
            "code": "test_code",
            "language": "python",
            "error": "test_error",
            "custom_key": "custom_value",
        }

        lines = exporter._render_metadata(metadata)

        assert "test_code" in "\n".join(lines)
        assert "test_error" in "\n".join(lines)
        assert "custom_key" in "\n".join(lines)
        assert "custom_value" in "\n".join(lines)

    def test_export_convenience_function(self, sample_tree, tmp_path):
        """Test the convenience export function."""
        output_path = tmp_path / "convenience_export.md"

        result = export_experiment(sample_tree, output_path)

        assert result.exists()
        assert result == output_path

        with open(result) as f:
            content = f.read()

        assert "Test Performance Problem" in content
