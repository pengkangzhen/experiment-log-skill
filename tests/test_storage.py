"""Tests for experiment_log storage."""

import json
from pathlib import Path

import pytest

from experiment_log.models import ExperimentNode, ExperimentTree, NodeType, Status
from experiment_log.storage import ExperimentStorage


class TestExperimentStorage:
    """Tests for ExperimentStorage."""

    @pytest.fixture
    def temp_storage(self, tmp_path):
        """Create a temporary storage instance."""
        return ExperimentStorage(tmp_path)

    def test_init_default_dir(self, tmp_path, monkeypatch):
        """Test default storage directory."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        storage = ExperimentStorage()
        assert storage.base_dir == tmp_path / ".experiment_logs"
        assert storage.base_dir.exists()

    def test_init_custom_dir(self, tmp_path):
        """Test custom storage directory."""
        custom_dir = tmp_path / "custom_logs"
        storage = ExperimentStorage(custom_dir)
        assert storage.base_dir == custom_dir
        assert storage.base_dir.exists()

    def test_create_experiment(self, temp_storage):
        """Test creating an experiment."""
        tree = temp_storage.create_experiment("Test Problem", "Description")

        assert tree.root_id in tree.nodes
        root = tree.get_root()
        assert root.title == "Test Problem"
        assert root.description == "Description"
        assert root.node_type == NodeType.ROOT

    def test_save_and_load_experiment(self, temp_storage):
        """Test saving and loading an experiment."""
        tree = temp_storage.create_experiment("Test Problem")
        exp_id = tree.root_id[:8]

        # Save
        saved_path = temp_storage.save_experiment(tree)
        assert saved_path.exists()

        # Load
        loaded = temp_storage.load_experiment(exp_id)
        assert loaded is not None
        assert loaded.root_id == tree.root_id
        assert loaded.get_root().title == "Test Problem"

    def test_load_nonexistent(self, temp_storage):
        """Test loading non-existent experiment."""
        result = temp_storage.load_experiment("nonexistent")
        assert result is None

    def test_save_creates_backup(self, temp_storage):
        """Test that saving creates a backup."""
        tree = temp_storage.create_experiment("Test Problem")
        exp_id = tree.root_id[:8]

        # First explicit save (creates backup since file exists after create_experiment)
        temp_storage.save_experiment(tree)

        # Modify and save again
        tree.nodes[tree.root_id].title = "Modified Problem"
        temp_storage.save_experiment(tree)

        # Check backups were created
        exp_dir = temp_storage._get_experiment_dir(exp_id)
        backups = list(exp_dir.glob("experiment.*.bak.json"))
        assert len(backups) == 2

    def test_load_latest(self, temp_storage):
        """Test loading the latest experiment."""
        # Create two experiments
        tree1 = temp_storage.create_experiment("First Problem")
        temp_storage.save_experiment(tree1)

        tree2 = temp_storage.create_experiment("Second Problem")
        temp_storage.save_experiment(tree2)

        # Load latest should return second
        latest = temp_storage.load_latest()
        assert latest is not None
        assert latest.get_root().title == "Second Problem"

    def test_load_latest_empty(self, temp_storage):
        """Test loading latest when no experiments exist."""
        result = temp_storage.load_latest()
        assert result is None

    def test_list_experiments(self, temp_storage):
        """Test listing experiments."""
        # Create experiments
        tree1 = temp_storage.create_experiment("First Problem")
        temp_storage.save_experiment(tree1)

        tree2 = temp_storage.create_experiment("Second Problem")
        temp_storage.save_experiment(tree2)

        experiments = temp_storage.list_experiments()

        assert len(experiments) == 2
        problems = [e["problem"] for e in experiments]
        assert "First Problem" in problems
        assert "Second Problem" in problems

    def test_list_experiments_empty(self, temp_storage):
        """Test listing when no experiments exist."""
        experiments = temp_storage.list_experiments()
        assert experiments == []

    def test_delete_experiment(self, temp_storage):
        """Test deleting an experiment."""
        tree = temp_storage.create_experiment("Test Problem")
        exp_id = tree.root_id[:8]
        temp_storage.save_experiment(tree)

        result = temp_storage.delete_experiment(exp_id)

        assert result is True
        assert not temp_storage._get_experiment_dir(exp_id).exists()

    def test_delete_nonexistent(self, temp_storage):
        """Test deleting non-existent experiment."""
        result = temp_storage.delete_experiment("nonexistent")
        assert result is False

    def test_get_backups(self, temp_storage):
        """Test getting backup files."""
        tree = temp_storage.create_experiment("Test Problem")
        exp_id = tree.root_id[:8]

        # Create multiple saves (each creates a backup since file exists)
        temp_storage.save_experiment(tree)
        tree.nodes[tree.root_id].title = "Modified 1"
        temp_storage.save_experiment(tree)
        tree.nodes[tree.root_id].title = "Modified 2"
        temp_storage.save_experiment(tree)

        backups = temp_storage.get_backups(exp_id)

        # create_experiment saves once, then 3 explicit saves = 3 backups
        assert len(backups) == 3
        # Should be sorted by modification time, newest first
        assert backups[0].stat().st_mtime >= backups[1].stat().st_mtime

    def test_restore_backup(self, temp_storage):
        """Test restoring from a backup."""
        tree = temp_storage.create_experiment("Original Problem")
        exp_id = tree.root_id[:8]
        temp_storage.save_experiment(tree)

        # Modify
        tree.nodes[tree.root_id].title = "Modified Problem"
        temp_storage.save_experiment(tree)

        # Restore
        result = temp_storage.restore_backup(exp_id)

        assert result is True
        loaded = temp_storage.load_experiment(exp_id)
        assert loaded.get_root().title == "Original Problem"

    def test_restore_specific_backup(self, temp_storage):
        """Test restoring a specific backup."""
        tree = temp_storage.create_experiment("Original Problem")
        exp_id = tree.root_id[:8]
        temp_storage.save_experiment(tree)

        # Get the backup file
        backups = temp_storage.get_backups(exp_id)

        # Modify
        tree.nodes[tree.root_id].title = "Modified Problem"
        temp_storage.save_experiment(tree)

        # Restore specific backup
        result = temp_storage.restore_backup(exp_id, backups[0])

        assert result is True

    def test_restore_backup_nonexistent(self, temp_storage):
        """Test restoring non-existent backup."""
        result = temp_storage.restore_backup("nonexistent")
        assert result is False

    def test_experiment_file_structure(self, temp_storage):
        """Test the saved file structure."""
        tree = temp_storage.create_experiment("Test Problem")
        exp_id = tree.root_id[:8]
        temp_storage.save_experiment(tree)

        exp_dir = temp_storage._get_experiment_dir(exp_id)
        main_file = exp_dir / "experiment.json"

        assert main_file.exists()

        with open(main_file) as f:
            data = json.load(f)

        assert "root_id" in data
        assert "nodes" in data
        assert "current_node_id" in data
        assert "created_at" in data
        assert "updated_at" in data

        root_data = data["nodes"][data["root_id"]]
        assert root_data["title"] == "Test Problem"
        assert root_data["node_type"] == "root"
