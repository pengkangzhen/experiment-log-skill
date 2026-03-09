"""Storage layer for experiment data persistence."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from experiment_log.models import ExperimentNode, ExperimentTree, NodeType, Status


def _find_project_root() -> Path:
    """Find the project root directory by looking for common markers.

    Returns:
        Path to project root, or current working directory if not found.
    """
    cwd = Path.cwd()

    # Look for common project root markers
    markers = [".git", "pyproject.toml", "setup.py", "Cargo.toml", "go.mod", "package.json"]

    # Check current directory and parents
    for path in [cwd] + list(cwd.parents):
        for marker in markers:
            if (path / marker).exists():
                return path

    # Fallback to current working directory
    return cwd


class ExperimentStorage:
    """Manages persistence of experiment data."""

    def __init__(self, base_dir: Path | str | None = None):
        if base_dir is None:
            # Default to project root's .experiment_logs directory
            base_dir = _find_project_root() / ".experiment_logs"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_experiment_dir(self, exp_id: str) -> Path:
        """Get the directory for a specific experiment."""
        return self.base_dir / exp_id

    def _get_main_file(self, exp_id: str) -> Path:
        """Get the main data file path for an experiment."""
        return self._get_experiment_dir(exp_id) / "experiment.json"

    def create_experiment(self, problem: str, description: str = "") -> ExperimentTree:
        """Create a new experiment with a root node."""
        tree = ExperimentTree()
        root = ExperimentNode(
            node_type=NodeType.ROOT,
            title=problem,
            description=description,
            status=Status.PENDING,
        )
        tree.root_id = root.id
        tree.current_node_id = root.id
        tree.nodes[root.id] = root

        self.save_experiment(tree)
        return tree

    def save_experiment(self, tree: ExperimentTree, backup: bool = True) -> Path:
        """Save an experiment tree to disk."""
        exp_id = tree.root_id[:8]
        exp_dir = self._get_experiment_dir(exp_id)
        exp_dir.mkdir(parents=True, exist_ok=True)

        main_file = self._get_main_file(exp_id)

        # Create backup if file exists
        if backup and main_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_file = exp_dir / f"experiment.{timestamp}.bak.json"
            shutil.copy2(main_file, backup_file)

        # Save main file
        tree.updated_at = datetime.now()
        with open(main_file, "w", encoding="utf-8") as f:
            json.dump(tree.to_dict(), f, indent=2, ensure_ascii=False)

        return main_file

    def load_experiment(self, exp_id: str) -> ExperimentTree | None:
        """Load an experiment tree from disk."""
        main_file = self._get_main_file(exp_id)
        if not main_file.exists():
            return None

        with open(main_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return ExperimentTree.from_dict(data)

    def load_latest(self) -> ExperimentTree | None:
        """Load the most recently updated experiment."""
        experiments = self.list_experiments()
        if not experiments:
            return None

        # Sort by updated_at, most recent first
        experiments.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return self.load_experiment(experiments[0]["id"])

    def list_experiments(self) -> list[dict[str, Any]]:
        """List all experiments with their metadata."""
        experiments = []

        for exp_dir in self.base_dir.iterdir():
            if not exp_dir.is_dir():
                continue

            main_file = exp_dir / "experiment.json"
            if not main_file.exists():
                continue

            try:
                with open(main_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                root_node = data.get("nodes", {}).get(data.get("root_id", ""), {})

                experiments.append({
                    "id": exp_dir.name,
                    "problem": root_node.get("title", "Unknown"),
                    "status": root_node.get("status", "unknown"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "node_count": len(data.get("nodes", {})),
                })
            except (json.JSONDecodeError, KeyError):
                continue

        return experiments

    def delete_experiment(self, exp_id: str) -> bool:
        """Delete an experiment and all its data."""
        exp_dir = self._get_experiment_dir(exp_id)
        if not exp_dir.exists():
            return False

        shutil.rmtree(exp_dir)
        return True

    def get_backups(self, exp_id: str) -> list[Path]:
        """Get list of backup files for an experiment."""
        exp_dir = self._get_experiment_dir(exp_id)
        if not exp_dir.exists():
            return []

        backups = list(exp_dir.glob("experiment.*.bak.json"))
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return backups

    def restore_backup(self, exp_id: str, backup_file: Path | str | None = None) -> bool:
        """Restore an experiment from a backup."""
        main_file = self._get_main_file(exp_id)

        if backup_file is None:
            # Use most recent backup
            backups = self.get_backups(exp_id)
            if not backups:
                return False
            backup_file = backups[0]
        else:
            backup_file = Path(backup_file)

        if not backup_file.exists():
            return False

        # Backup current state first
        if main_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_backup = self._get_experiment_dir(exp_id) / f"experiment.{timestamp}.safety.json"
            shutil.copy2(main_file, safety_backup)

        shutil.copy2(backup_file, main_file)
        return True


class ExperimentSummary:
    """Summary information about an experiment."""

    def __init__(self, exp_id: str, problem: str, status: str,
                 created_at: str, updated_at: str, node_count: int):
        self.id = exp_id
        self.problem = problem
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at
        self.node_count = node_count

    def __repr__(self) -> str:
        return f"ExperimentSummary({self.id}: {self.problem})"
