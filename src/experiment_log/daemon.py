"""Daemon for automatic experiment logging."""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiment_log.analyzer import SessionAnalyzer
from experiment_log.intention import IntentionRecognizer
from experiment_log.recorder import AutoRecorder, AutoRecordConfig
from experiment_log.storage import ExperimentStorage


def _get_project_experiment_dir() -> Path:
    """Get the experiment logs directory in the project root."""
    # Import here to avoid circular import
    from experiment_log.storage import _find_project_root
    return _find_project_root() / ".experiment_logs"


# Default paths (under project root)
DEFAULT_PID_FILE = None  # Will be set dynamically
DEFAULT_LOG_FILE = None  # Will be set dynamically
DEFAULT_STATE_FILE = None  # Will be set dynamically


def _get_default_pid_file() -> Path:
    """Get the default PID file path."""
    return _get_project_experiment_dir() / "daemon.pid"


def _get_default_log_file() -> Path:
    """Get the default log file path."""
    return _get_project_experiment_dir() / "daemon.log"


def _get_default_state_file() -> Path:
    """Get the default state file path."""
    return _get_project_experiment_dir() / "daemon_state.json"


@dataclass
class DaemonConfig:
    """Configuration for the daemon."""

    poll_interval: float = 2.0  # Seconds between checks
    min_confidence: float = 0.6
    history_path: Path | None = None
    storage_path: Path | None = None
    pid_file: Path | None = None  # Will be set dynamically
    log_file: Path | None = None  # Will be set dynamically
    state_file: Path | None = None  # Will be set dynamically
    quiet: bool = False
    auto_create: bool = True

    def __post_init__(self):
        # Set default paths if not provided
        if self.pid_file is None:
            self.pid_file = _get_default_pid_file()
        if self.log_file is None:
            self.log_file = _get_default_log_file()
        if self.state_file is None:
            self.state_file = _get_default_state_file()


class ExperimentDaemon:
    """Daemon that watches for experiment intentions and records them."""

    def __init__(self, config: DaemonConfig | None = None):
        """Initialize the daemon.

        Args:
            config: Daemon configuration
        """
        self.config = config or DaemonConfig()
        self.analyzer: SessionAnalyzer | None = None
        self.recognizer: IntentionRecognizer | None = None
        self.recorder: AutoRecorder | None = None
        self._running = False
        self._pid: int | None = None

    def _setup_components(self) -> None:
        """Set up the analyzer, recognizer, and recorder."""
        # Initialize analyzer
        self.analyzer = SessionAnalyzer(self.config.history_path)

        # Initialize recognizer (pattern-based, no LLM by default)
        self.recognizer = IntentionRecognizer(use_llm=False)

        # Initialize storage
        storage = ExperimentStorage(self.config.storage_path)

        # Initialize recorder
        record_config = AutoRecordConfig(
            min_confidence=self.config.min_confidence,
            auto_create_experiments=self.config.auto_create,
            quiet_mode=self.config.quiet,
        )
        self.recorder = AutoRecorder(
            storage=storage,
            recognizer=self.recognizer,
            config=record_config,
        )

    def start(self) -> bool:
        """Start the daemon.

        Returns:
            True if started successfully
        """
        # Check if already running
        if self.is_running():
            pid = self._read_pid()
            print(f"Daemon already running (PID: {pid})")
            return False

        # Fork to background (Unix-like systems)
        if os.name != "nt":  # Not Windows
            try:
                pid = os.fork()
                if pid > 0:
                    # Parent process
                    print(f"Daemon started (PID: {pid})")
                    return True
            except OSError as e:
                print(f"Fork failed: {e}")
                return False

        # Child process or Windows
        self._daemonize()
        return True

    def _daemonize(self) -> None:
        """Daemonize the process."""
        # Create session
        if os.name != "nt":
            os.setsid()

        # Redirect standard file descriptors
        self._redirect_fds()

        # Write PID file
        self._write_pid(os.getpid())

        # Set up signal handlers
        self._setup_signals()

        # Set up components
        self._setup_components()

        # Save initial state
        self._save_state()

        # Start main loop
        self._run()

    def _redirect_fds(self) -> None:
        """Redirect standard file descriptors to /dev/null or log file."""
        # Redirect stdout and stderr to log file
        if self.config.log_file:
            self.config.log_file.parent.mkdir(parents=True, exist_ok=True)
            log_fd = open(self.config.log_file, "a")
            os.dup2(log_fd.fileno(), sys.stdout.fileno())
            os.dup2(log_fd.fileno(), sys.stderr.fileno())
            log_fd.close()

        # Redirect stdin from /dev/null
        devnull = open(os.devnull, "r")
        os.dup2(devnull.fileno(), sys.stdin.fileno())
        devnull.close()

    def _setup_signals(self) -> None:
        """Set up signal handlers."""
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        self._running = False

    def _run(self) -> None:
        """Main daemon loop."""
        self._running = True

        if not self.config.quiet:
            print(f"Experiment daemon started (PID: {os.getpid()})")
            print(f"Watching: {self.analyzer.history_path if self.analyzer else 'N/A'}")

        while self._running:
            try:
                self._check_once()
            except Exception as e:
                if not self.config.quiet:
                    print(f"Error in daemon loop: {e}")

            time.sleep(self.config.poll_interval)

        # Cleanup
        self._cleanup()

        if not self.config.quiet:
            print("Daemon stopped")

    def _check_once(self) -> None:
        """Check for new history entries once."""
        if not self.analyzer or not self.recorder:
            return

        # Check for updates
        context = self.analyzer.check_for_updates()
        if context:
            # Process the context
            self.recorder.process_context(context)
            # Update state
            self._save_state()

    def stop(self) -> bool:
        """Stop the daemon.

        Returns:
            True if stopped successfully
        """
        pid = self._read_pid()
        if not pid:
            print("Daemon not running")
            return False

        try:
            # Send SIGTERM
            os.kill(pid, signal.SIGTERM)

            # Wait for process to terminate
            for _ in range(10):
                if not self.is_running():
                    break
                time.sleep(0.5)

            # Force kill if still running
            if self.is_running():
                os.kill(pid, signal.SIGKILL)

            # Remove PID file
            self._remove_pid()
            print(f"Daemon stopped (PID: {pid})")
            return True

        except ProcessLookupError:
            # Process doesn't exist
            self._remove_pid()
            print("Daemon not running (stale PID file)")
            return False
        except PermissionError:
            print(f"Permission denied to stop daemon (PID: {pid})")
            return False

    def status(self) -> dict[str, Any]:
        """Get daemon status.

        Returns:
            Status dictionary
        """
        pid = self._read_pid()
        is_running = self.is_running()

        status = {
            "running": is_running,
            "pid": pid,
            "config": {
                "poll_interval": self.config.poll_interval,
                "min_confidence": self.config.min_confidence,
                "history_path": str(self.config.history_path) if self.config.history_path else None,
                "storage_path": str(self.config.storage_path) if self.config.storage_path else None,
            },
        }

        # Load state if exists
        if self.config.state_file.exists():
            try:
                with open(self.config.state_file, "r") as f:
                    state = json.load(f)
                    status["state"] = state
            except (json.JSONDecodeError, IOError):
                pass

        return status

    def is_running(self) -> bool:
        """Check if the daemon is running.

        Returns:
            True if running
        """
        pid = self._read_pid()
        if not pid:
            return False

        try:
            # Check if process exists
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            # Process doesn't exist, clean up stale PID file
            self._remove_pid()
            return False

    def _read_pid(self) -> int | None:
        """Read PID from PID file.

        Returns:
            PID or None
        """
        if not self.config.pid_file.exists():
            return None

        try:
            with open(self.config.pid_file, "r") as f:
                return int(f.read().strip())
        except (ValueError, IOError):
            return None

    def _write_pid(self, pid: int) -> None:
        """Write PID to PID file.

        Args:
            pid: Process ID
        """
        self.config.pid_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config.pid_file, "w") as f:
            f.write(str(pid))

    def _remove_pid(self) -> None:
        """Remove the PID file."""
        try:
            self.config.pid_file.unlink()
        except FileNotFoundError:
            pass

    def _save_state(self) -> None:
        """Save daemon state to file."""
        if not self.analyzer:
            return

        state = {
            "last_position": self.analyzer.get_current_position(),
            "timestamp": time.time(),
        }

        try:
            with open(self.config.state_file, "w") as f:
                json.dump(state, f)
        except IOError:
            pass

    def _cleanup(self) -> None:
        """Clean up resources."""
        self._remove_pid()

    def run_foreground(self) -> None:
        """Run the daemon in foreground (for testing/debugging)."""
        # Set up components
        self._setup_components()

        # Restore state if exists
        if self.config.state_file.exists():
            try:
                with open(self.config.state_file, "r") as f:
                    state = json.load(f)
                    if self.analyzer and "last_position" in state:
                        self.analyzer.last_position = state["last_position"]
            except (json.JSONDecodeError, IOError):
                pass

        # Set up signal handlers
        self._setup_signals()

        print(f"Experiment daemon running in foreground (PID: {os.getpid()})")
        print(f"Watching: {self.analyzer.history_path if self.analyzer else 'N/A'}")
        print("Press Ctrl+C to stop\n")

        self._run()


def start_daemon(
    poll_interval: float = 2.0,
    min_confidence: float = 0.6,
    history_path: Path | str | None = None,
    quiet: bool = False,
) -> bool:
    """Start the experiment daemon.

    Args:
        poll_interval: Seconds between checks
        min_confidence: Minimum confidence to record
        history_path: Path to history.jsonl
        quiet: Suppress output

    Returns:
        True if started
    """
    config = DaemonConfig(
        poll_interval=poll_interval,
        min_confidence=min_confidence,
        history_path=Path(history_path) if history_path else None,
        quiet=quiet,
    )
    daemon = ExperimentDaemon(config)
    return daemon.start()


def stop_daemon() -> bool:
    """Stop the experiment daemon.

    Returns:
        True if stopped
    """
    config = DaemonConfig()
    daemon = ExperimentDaemon(config)
    return daemon.stop()


def get_daemon_status() -> dict[str, Any]:
    """Get daemon status.

    Returns:
        Status dictionary
    """
    config = DaemonConfig()
    daemon = ExperimentDaemon(config)
    return daemon.status()


def is_daemon_running() -> bool:
    """Check if daemon is running.

    Returns:
        True if running
    """
    config = DaemonConfig()
    daemon = ExperimentDaemon(config)
    return daemon.is_running()
