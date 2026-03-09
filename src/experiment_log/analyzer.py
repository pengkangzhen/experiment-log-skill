"""Session analyzer for Claude Code history."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""

    role: str  # "user" or "assistant"
    content: str
    timestamp: int
    session_id: str | None = None
    project: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationContext:
    """Context of a conversation session."""

    session_id: str
    project: str | None
    turns: list[ConversationTurn] = field(default_factory=list)

    def format_history(self, max_turns: int = 10) -> str:
        """Format conversation history as a string."""
        recent_turns = self.turns[-max_turns:] if len(self.turns) > max_turns else self.turns
        lines = []
        for turn in recent_turns:
            prefix = "User" if turn.role == "user" else "Claude"
            lines.append(f"{prefix}: {turn.content}")
        return "\n".join(lines)

    def get_latest_user_message(self) -> str | None:
        """Get the most recent user message."""
        for turn in reversed(self.turns):
            if turn.role == "user":
                return turn.content
        return None


class SessionAnalyzer:
    """Analyzes Claude Code session history from history.jsonl."""

    def __init__(self, history_path: Path | str | None = None):
        """Initialize the analyzer.

        Args:
            history_path: Path to the history.jsonl file. If None, uses
                         the default Claude Code history location.
        """
        if history_path is None:
            history_path = Path.home() / ".claude" / "history.jsonl"
        self.history_path = Path(history_path)
        self.last_position = 0
        self.last_size = 0
        self._ensure_file_exists()

    def _ensure_file_exists(self) -> None:
        """Ensure the history file exists."""
        if not self.history_path.exists():
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            self.history_path.touch()

    def watch(self, poll_interval: float = 1.0) -> Iterator[ConversationContext]:
        """Watch the history file for new entries.

        Args:
            poll_interval: Seconds between polls

        Yields:
            ConversationContext when new user messages are detected
        """
        while True:
            context = self.check_for_updates()
            if context:
                yield context
            time.sleep(poll_interval)

    def check_for_updates(self) -> ConversationContext | None:
        """Check for new entries in the history file.

        Returns:
            ConversationContext if new user message found, None otherwise
        """
        if not self.history_path.exists():
            return None

        current_size = self.history_path.stat().st_size

        # File was truncated or reset
        if current_size < self.last_size:
            self.last_position = 0

        if current_size <= self.last_position:
            return None

        new_lines = self._read_new_lines()
        if not new_lines:
            return None

        return self._process_lines(new_lines)

    def _read_new_lines(self) -> list[dict[str, Any]]:
        """Read new lines from the history file."""
        lines = []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                f.seek(self.last_position)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            lines.append(data)
                        except json.JSONDecodeError:
                            continue
                self.last_position = f.tell()
                self.last_size = self.history_path.stat().st_size
        except (IOError, OSError):
            pass
        return lines

    def _process_lines(self, lines: list[dict[str, Any]]) -> ConversationContext | None:
        """Process history lines and extract conversation context.

        The history.jsonl format from Claude Code:
        {"display": "user message", "timestamp": 1234567890, "project": "...", "sessionId": "..."}
        """
        if not lines:
            return None

        # Group by session
        sessions: dict[str, list[ConversationTurn]] = {}

        for line in lines:
            # Extract fields from the line
            content = line.get("display", line.get("content", ""))
            if not content:
                continue

            timestamp = line.get("timestamp", int(time.time() * 1000))
            session_id = line.get("sessionId", "unknown")
            project = line.get("project")

            # Determine role - in Claude Code history, entries are user messages
            # or assistant responses. User messages typically start with certain patterns
            # or we can infer from context. For now, we'll treat most as user messages
            # and look for specific patterns.
            role = self._determine_role(line, content)

            turn = ConversationTurn(
                role=role,
                content=content,
                timestamp=timestamp,
                session_id=session_id,
                project=project,
                metadata={k: v for k, v in line.items() if k not in ("display", "content", "timestamp", "sessionId", "project")},
            )

            if session_id not in sessions:
                sessions[session_id] = []
            sessions[session_id].append(turn)

        # Find the most recently updated session with user messages
        latest_session = None
        latest_timestamp = 0

        for session_id, turns in sessions.items():
            user_turns = [t for t in turns if t.role == "user"]
            if user_turns:
                last_timestamp = max(t.timestamp for t in user_turns)
                if last_timestamp > latest_timestamp:
                    latest_timestamp = last_timestamp
                    latest_session = session_id

        if not latest_session:
            return None

        turns = sessions[latest_session]
        turns.sort(key=lambda t: t.timestamp)

        # Get project from first turn
        project = turns[0].project if turns else None

        return ConversationContext(
            session_id=latest_session,
            project=project,
            turns=turns,
        )

    def _determine_role(self, line: dict[str, Any], content: str) -> str:
        """Determine if a line is from user or assistant.

        Heuristics:
        - Lines with 'display' field are typically user inputs
        - Lines with specific markers might be assistant responses
        - Short confirmations or code-heavy content might be assistant
        """
        # Check for explicit role markers
        if "role" in line:
            return line["role"]

        # Check for assistant markers in the content or line structure
        # Assistant responses often have code blocks or specific formatting
        if line.get("type") == "assistant" or line.get("source") == "assistant":
            return "assistant"

        # Default to user for most entries in Claude Code history
        # The history.jsonl primarily captures user commands
        return "user"

    def extract_context(self, max_lines: int = 20) -> ConversationContext | None:
        """Extract conversation context from recent history.

        Args:
            max_lines: Maximum number of recent lines to include

        Returns:
            ConversationContext or None if no history available
        """
        if not self.history_path.exists():
            return None

        lines = []
        try:
            with open(self.history_path, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                # Take the last max_lines
                recent_lines = all_lines[-max_lines:] if len(all_lines) > max_lines else all_lines

                for line in recent_lines:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            lines.append(data)
                        except json.JSONDecodeError:
                            continue
        except (IOError, OSError):
            return None

        if not lines:
            return None

        return self._process_lines(lines)

    def get_recent_user_messages(self, count: int = 5) -> list[str]:
        """Get recent user messages.

        Args:
            count: Number of messages to retrieve

        Returns:
            List of message strings
        """
        context = self.extract_context(max_lines=count * 2)
        if not context:
            return []

        user_messages = [t.content for t in context.turns if t.role == "user"]
        return user_messages[-count:]

    def reset_position(self) -> None:
        """Reset the file position to the beginning."""
        self.last_position = 0
        self.last_size = 0

    def get_current_position(self) -> int:
        """Get the current file position."""
        return self.last_position


def analyze_conversation(
    history_path: Path | str | None = None,
    max_turns: int = 10,
) -> ConversationContext | None:
    """Convenience function to analyze the current conversation.

    Args:
        history_path: Path to history file
        max_turns: Maximum number of turns to include

    Returns:
        ConversationContext or None
    """
    analyzer = SessionAnalyzer(history_path)
    return analyzer.extract_context(max_lines=max_turns * 2)
