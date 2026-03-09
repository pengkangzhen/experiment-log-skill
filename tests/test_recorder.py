"""Tests for the auto-recorder module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from experiment_log.analyzer import ConversationContext, ConversationTurn
from experiment_log.intention import Intention, IntentionRecognizer, IntentionType
from experiment_log.models import Status
from experiment_log.recorder import (
    AutoRecordConfig,
    AutoRecorder,
    RecordEvent,
    SilentAutoRecorder,
)
from experiment_log.storage import ExperimentStorage


class TestAutoRecordConfig:
    """Test AutoRecordConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = AutoRecordConfig()

        assert config.min_confidence == 0.6
        assert config.auto_create_experiments is True
        assert config.auto_record_attempts is True
        assert config.auto_record_results is True
        assert config.confirm_before_record is False
        assert config.quiet_mode is False
        assert config.on_record_callback is None

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = AutoRecordConfig(
            min_confidence=0.8,
            auto_create_experiments=False,
            quiet_mode=True,
        )

        assert config.min_confidence == 0.8
        assert config.auto_create_experiments is False
        assert config.quiet_mode is True


class TestRecordEvent:
    """Test RecordEvent dataclass."""

    def test_event_creation(self) -> None:
        """Test creating a record event."""
        event = RecordEvent(
            action="create",
            intention_type=IntentionType.NEW_EXPERIMENT,
            description="Test experiment",
            node_id="abc123",
            experiment_id="exp123",
        )

        assert event.action == "create"
        assert event.intention_type == IntentionType.NEW_EXPERIMENT
        assert event.description == "Test experiment"
        assert event.node_id == "abc123"
        assert event.experiment_id == "exp123"


class TestAutoRecorder:
    """Test AutoRecorder class."""

    def test_recorder_creation(self) -> None:
        """Test creating an auto-recorder."""
        recorder = AutoRecorder()

        assert recorder.storage is not None
        assert recorder.recognizer is not None
        assert recorder.config is not None
        assert recorder.current_manager is None

    def test_recorder_with_custom_config(self) -> None:
        """Test creating recorder with custom config."""
        config = AutoRecordConfig(min_confidence=0.8, quiet_mode=True)
        recorder = AutoRecorder(config=config)

        assert recorder.config.min_confidence == 0.8
        assert recorder.config.quiet_mode is True

    def test_on_intention_detected_low_confidence(self) -> None:
        """Test that low confidence intentions are ignored."""
        recorder = AutoRecorder()

        intention = Intention(
            type=IntentionType.NEW_EXPERIMENT,
            description="Test",
            confidence=0.3,  # Below default threshold
        )

        result = recorder.on_intention_detected(intention)
        assert result is None

    def test_on_intention_detected_none_type(self) -> None:
        """Test that NONE type intentions are ignored."""
        recorder = AutoRecorder()

        intention = Intention(
            type=IntentionType.NONE,
            description="Test",
            confidence=0.9,
        )

        result = recorder.on_intention_detected(intention)
        assert result is None

    def test_create_experiment(self) -> None:
        """Test creating a new experiment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=AutoRecordConfig(quiet_mode=True))

            intention = Intention(
                type=IntentionType.NEW_EXPERIMENT,
                description="Test problem",
                confidence=0.9,
            )

            event = recorder.on_intention_detected(intention)

            assert event is not None
            assert event.action == "create"
            assert event.intention_type == IntentionType.NEW_EXPERIMENT
            assert recorder.current_manager is not None

    def test_add_attempt(self) -> None:
        """Test adding an attempt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=AutoRecordConfig(quiet_mode=True))

            # First create an experiment
            create_intention = Intention(
                type=IntentionType.NEW_EXPERIMENT,
                description="Test problem",
                confidence=0.9,
            )
            recorder.on_intention_detected(create_intention)

            # Then add an attempt
            attempt_intention = Intention(
                type=IntentionType.ATTEMPT,
                description="Try solution A",
                confidence=0.9,
            )
            event = recorder.on_intention_detected(attempt_intention)

            assert event is not None
            assert event.action == "attempt"
            assert event.intention_type == IntentionType.ATTEMPT

    def test_add_branch(self) -> None:
        """Test adding a branch attempt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=AutoRecordConfig(quiet_mode=True))

            # Create experiment
            create_intention = Intention(
                type=IntentionType.NEW_EXPERIMENT,
                description="Test problem",
                confidence=0.9,
            )
            recorder.on_intention_detected(create_intention)

            # Add branch
            branch_intention = Intention(
                type=IntentionType.BRANCH,
                description="Alternative approach",
                confidence=0.9,
            )
            event = recorder.on_intention_detected(branch_intention)

            assert event is not None
            assert event.action == "branch"
            assert event.intention_type == IntentionType.BRANCH

    def test_record_success_result(self) -> None:
        """Test recording a success result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=AutoRecordConfig(quiet_mode=True))

            # Create experiment
            create_intention = Intention(
                type=IntentionType.NEW_EXPERIMENT,
                description="Test problem",
                confidence=0.9,
            )
            recorder.on_intention_detected(create_intention)

            # Add attempt
            attempt_intention = Intention(
                type=IntentionType.ATTEMPT,
                description="Try solution A",
                confidence=0.9,
            )
            recorder.on_intention_detected(attempt_intention)

            # Record success
            success_intention = Intention(
                type=IntentionType.RESULT_SUCCESS,
                description="It works!",
                confidence=0.9,
            )
            event = recorder.on_intention_detected(success_intention)

            assert event is not None
            assert event.action == "result"
            assert event.intention_type == IntentionType.RESULT_SUCCESS

    def test_record_failed_result(self) -> None:
        """Test recording a failed result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=AutoRecordConfig(quiet_mode=True))

            # Create experiment
            create_intention = Intention(
                type=IntentionType.NEW_EXPERIMENT,
                description="Test problem",
                confidence=0.9,
            )
            recorder.on_intention_detected(create_intention)

            # Add attempt
            attempt_intention = Intention(
                type=IntentionType.ATTEMPT,
                description="Try solution A",
                confidence=0.9,
            )
            recorder.on_intention_detected(attempt_intention)

            # Record failure
            failed_intention = Intention(
                type=IntentionType.RESULT_FAILED,
                description="Got an error",
                confidence=0.9,
            )
            event = recorder.on_intention_detected(failed_intention)

            assert event is not None
            assert event.action == "result"
            assert event.intention_type == IntentionType.RESULT_FAILED

    def test_record_aborted_result(self) -> None:
        """Test recording an aborted result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=AutoRecordConfig(quiet_mode=True))

            # Create experiment
            create_intention = Intention(
                type=IntentionType.NEW_EXPERIMENT,
                description="Test problem",
                confidence=0.9,
            )
            recorder.on_intention_detected(create_intention)

            # Add attempt
            attempt_intention = Intention(
                type=IntentionType.ATTEMPT,
                description="Try solution A",
                confidence=0.9,
            )
            recorder.on_intention_detected(attempt_intention)

            # Record abort
            aborted_intention = Intention(
                type=IntentionType.RESULT_ABORTED,
                description="Giving up",
                confidence=0.9,
            )
            event = recorder.on_intention_detected(aborted_intention)

            assert event is not None
            assert event.action == "result"
            assert event.intention_type == IntentionType.RESULT_ABORTED

    def test_result_without_experiment(self) -> None:
        """Test that result without active experiment returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=AutoRecordConfig(quiet_mode=True))

            # Try to record result without experiment
            success_intention = Intention(
                type=IntentionType.RESULT_SUCCESS,
                description="It works!",
                confidence=0.9,
            )
            event = recorder.on_intention_detected(success_intention)

            assert event is None

    def test_process_message(self) -> None:
        """Test processing a single message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=AutoRecordConfig(quiet_mode=True))

            event = recorder.process_message("帮我优化性能")

            assert event is not None
            assert event.action == "create"
            assert event.intention_type == IntentionType.NEW_EXPERIMENT

    def test_process_context(self) -> None:
        """Test processing a conversation context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=AutoRecordConfig(quiet_mode=True))

            turns = [
                ConversationTurn(role="user", content="Hello", timestamp=1, session_id="s1"),
                ConversationTurn(role="user", content="试试新方法", timestamp=2, session_id="s1"),
            ]

            context = ConversationContext(
                session_id="s1",
                project="/test",
                turns=turns,
            )

            # First create an experiment
            create_context = ConversationContext(
                session_id="s1",
                project="/test",
                turns=[ConversationTurn(role="user", content="创建实验", timestamp=1, session_id="s1")],
            )
            recorder.process_context(create_context)

            # Then process attempt
            event = recorder.process_context(context)

            assert event is not None
            assert event.action == "attempt"

    def test_get_current_experiment(self) -> None:
        """Test getting current experiment."""
        recorder = AutoRecorder()
        assert recorder.get_current_experiment() is None

    def test_get_last_intention(self) -> None:
        """Test getting last intention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=AutoRecordConfig(quiet_mode=True))

            assert recorder.get_last_intention() is None

            intention = Intention(
                type=IntentionType.NEW_EXPERIMENT,
                description="Test",
                confidence=0.9,
            )
            recorder.on_intention_detected(intention)

            assert recorder.get_last_intention() == intention

    def test_callback_triggered(self) -> None:
        """Test that callback is triggered on record."""
        callback_calls = []

        def callback(event: RecordEvent) -> None:
            callback_calls.append(event)

        config = AutoRecordConfig(quiet_mode=True, on_record_callback=callback)

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=config)

            intention = Intention(
                type=IntentionType.NEW_EXPERIMENT,
                description="Test",
                confidence=0.9,
            )
            recorder.on_intention_detected(intention)

            assert len(callback_calls) == 1
            assert callback_calls[0].action == "create"

    def test_callback_error_ignored(self) -> None:
        """Test that callback errors are ignored."""
        def bad_callback(event: RecordEvent) -> None:
            raise ValueError("Test error")

        config = AutoRecordConfig(quiet_mode=True, on_record_callback=bad_callback)

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = AutoRecorder(storage=storage, config=config)

            intention = Intention(
                type=IntentionType.NEW_EXPERIMENT,
                description="Test",
                confidence=0.9,
            )
            # Should not raise
            event = recorder.on_intention_detected(intention)
            assert event is not None


class TestSilentAutoRecorder:
    """Test SilentAutoRecorder class."""

    def test_silent_creation(self) -> None:
        """Test creating a silent recorder."""
        recorder = SilentAutoRecorder()

        assert recorder.config.quiet_mode is True

    def test_silent_records(self) -> None:
        """Test that silent recorder still records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = ExperimentStorage(tmpdir)
            recorder = SilentAutoRecorder(storage=storage)

            intention = Intention(
                type=IntentionType.NEW_EXPERIMENT,
                description="Test",
                confidence=0.9,
            )
            event = recorder.on_intention_detected(intention)

            assert event is not None
            assert recorder.current_manager is not None
