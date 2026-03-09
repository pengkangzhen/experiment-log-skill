"""Tests for the session analyzer module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from experiment_log.analyzer import (
    ConversationContext,
    ConversationTurn,
    SessionAnalyzer,
    analyze_conversation,
)


class TestConversationTurn:
    """Test ConversationTurn dataclass."""

    def test_conversation_turn_creation(self) -> None:
        """Test creating a conversation turn."""
        turn = ConversationTurn(
            role="user",
            content="Hello, world",
            timestamp=1234567890,
            session_id="test-session",
        )

        assert turn.role == "user"
        assert turn.content == "Hello, world"
        assert turn.timestamp == 1234567890
        assert turn.session_id == "test-session"
        assert turn.project is None
        assert turn.metadata == {}


class TestConversationContext:
    """Test ConversationContext dataclass."""

    def test_format_history(self) -> None:
        """Test formatting conversation history."""
        turns = [
            ConversationTurn(role="user", content="Hello", timestamp=1, session_id="s1"),
            ConversationTurn(role="assistant", content="Hi there", timestamp=2, session_id="s1"),
            ConversationTurn(role="user", content="How are you?", timestamp=3, session_id="s1"),
        ]

        context = ConversationContext(
            session_id="s1",
            project="/test",
            turns=turns,
        )

        history = context.format_history()
        assert "User: Hello" in history
        assert "Claude: Hi there" in history
        assert "User: How are you?" in history

    def test_format_history_limit(self) -> None:
        """Test formatting with max_turns limit."""
        turns = [
            ConversationTurn(role="user", content=f"Message {i}", timestamp=i, session_id="s1")
            for i in range(10)
        ]

        context = ConversationContext(
            session_id="s1",
            project="/test",
            turns=turns,
        )

        history = context.format_history(max_turns=3)
        lines = history.strip().split("\n")
        assert len(lines) == 3

    def test_get_latest_user_message(self) -> None:
        """Test getting latest user message."""
        turns = [
            ConversationTurn(role="user", content="First", timestamp=1, session_id="s1"),
            ConversationTurn(role="assistant", content="Response", timestamp=2, session_id="s1"),
            ConversationTurn(role="user", content="Latest", timestamp=3, session_id="s1"),
        ]

        context = ConversationContext(
            session_id="s1",
            project="/test",
            turns=turns,
        )

        assert context.get_latest_user_message() == "Latest"

    def test_get_latest_user_message_none(self) -> None:
        """Test getting latest user message when none exists."""
        turns = [
            ConversationTurn(role="assistant", content="Response", timestamp=2, session_id="s1"),
        ]

        context = ConversationContext(
            session_id="s1",
            project="/test",
            turns=turns,
        )

        assert context.get_latest_user_message() is None


class TestSessionAnalyzer:
    """Test SessionAnalyzer class."""

    def test_analyzer_creation(self) -> None:
        """Test creating a session analyzer."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = Path(f.name)

        try:
            analyzer = SessionAnalyzer(path)
            assert analyzer.history_path == path
            assert analyzer.last_position == 0
        finally:
            path.unlink()

    def test_ensure_file_exists(self) -> None:
        """Test that analyzer creates file if not exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nonexistent" / "history.jsonl"
            analyzer = SessionAnalyzer(path)
            assert path.exists()

    def test_read_new_lines(self) -> None:
        """Test reading new lines from history file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"display": "Test message", "timestamp": 12345}) + "\n")
            f.write(json.dumps({"display": "Another message", "timestamp": 12346}) + "\n")
            path = Path(f.name)

        try:
            analyzer = SessionAnalyzer(path)
            lines = analyzer._read_new_lines()

            assert len(lines) == 2
            assert lines[0]["display"] == "Test message"
            assert lines[1]["display"] == "Another message"
            assert analyzer.last_position > 0
        finally:
            path.unlink()

    def test_process_lines(self) -> None:
        """Test processing history lines."""
        lines = [
            {
                "display": "Hello",
                "timestamp": 1234567890,
                "sessionId": "session-1",
                "project": "/test/project",
            },
            {
                "display": "World",
                "timestamp": 1234567891,
                "sessionId": "session-1",
                "project": "/test/project",
            },
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = Path(f.name)

        try:
            analyzer = SessionAnalyzer(path)
            context = analyzer._process_lines(lines)

            assert context is not None
            assert context.session_id == "session-1"
            assert context.project == "/test/project"
            assert len(context.turns) == 2
        finally:
            path.unlink()

    def test_extract_context(self) -> None:
        """Test extracting conversation context."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for i in range(5):
                f.write(json.dumps({
                    "display": f"Message {i}",
                    "timestamp": 1234567890 + i,
                    "sessionId": "test-session",
                }) + "\n")
            path = Path(f.name)

        try:
            analyzer = SessionAnalyzer(path)
            context = analyzer.extract_context(max_lines=10)

            assert context is not None
            assert context.session_id == "test-session"
            assert len(context.turns) == 5
        finally:
            path.unlink()

    def test_get_recent_user_messages(self) -> None:
        """Test getting recent user messages."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            for i in range(10):
                f.write(json.dumps({
                    "display": f"Message {i}",
                    "timestamp": 1234567890 + i,
                    "sessionId": "test-session",
                }) + "\n")
            path = Path(f.name)

        try:
            analyzer = SessionAnalyzer(path)
            messages = analyzer.get_recent_user_messages(count=3)

            assert len(messages) == 3
            assert messages[-1] == "Message 9"
        finally:
            path.unlink()

    def test_reset_position(self) -> None:
        """Test resetting file position."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"display": "Test", "timestamp": 12345}) + "\n")
            path = Path(f.name)

        try:
            analyzer = SessionAnalyzer(path)
            analyzer._read_new_lines()  # Read some lines
            assert analyzer.last_position > 0

            analyzer.reset_position()
            assert analyzer.last_position == 0
        finally:
            path.unlink()


class TestAnalyzeConversation:
    """Test the analyze_conversation convenience function."""

    def test_analyze_conversation(self) -> None:
        """Test the convenience function."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({
                "display": "Test message",
                "timestamp": 1234567890,
                "sessionId": "session-1",
            }) + "\n")
            path = Path(f.name)

        try:
            context = analyze_conversation(path, max_turns=5)
            assert context is not None
            assert context.session_id == "session-1"
        finally:
            path.unlink()

    def test_analyze_conversation_empty(self) -> None:
        """Test with empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = Path(f.name)

        try:
            context = analyze_conversation(path)
            assert context is None
        finally:
            path.unlink()
