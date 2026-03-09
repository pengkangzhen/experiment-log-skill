"""Tests for the intention recognition module."""

from __future__ import annotations

import pytest

from experiment_log.analyzer import ConversationContext, ConversationTurn
from experiment_log.intention import (
    INTENT_PATTERNS,
    Intention,
    IntentionRecognizer,
    IntentionType,
    get_intention_icon,
    get_intention_label,
    quick_recognize,
)


class TestIntentionType:
    """Test IntentionType enum."""

    def test_intention_type_values(self) -> None:
        """Test intention type values."""
        assert IntentionType.NEW_EXPERIMENT.value == "new_experiment"
        assert IntentionType.ATTEMPT.value == "attempt"
        assert IntentionType.BRANCH.value == "branch"
        assert IntentionType.RESULT_SUCCESS.value == "result_success"
        assert IntentionType.RESULT_FAILED.value == "result_failed"
        assert IntentionType.RESULT_ABORTED.value == "result_aborted"
        assert IntentionType.NONE.value == "none"


class TestIntention:
    """Test Intention dataclass."""

    def test_intention_creation(self) -> None:
        """Test creating an intention."""
        intention = Intention(
            type=IntentionType.NEW_EXPERIMENT,
            description="Test problem",
            confidence=0.9,
        )

        assert intention.type == IntentionType.NEW_EXPERIMENT
        assert intention.description == "Test problem"
        assert intention.confidence == 0.9
        assert intention.metadata == {}

    def test_intention_with_metadata(self) -> None:
        """Test creating an intention with metadata."""
        intention = Intention(
            type=IntentionType.ATTEMPT,
            description="Try caching",
            confidence=0.8,
            metadata={"source": "pattern_match"},
        )

        assert intention.metadata == {"source": "pattern_match"}


class TestIntentionRecognizer:
    """Test IntentionRecognizer class."""

    def test_recognizer_creation(self) -> None:
        """Test creating a recognizer."""
        recognizer = IntentionRecognizer(use_llm=False)
        assert recognizer.use_llm is False
        assert recognizer.llm_client is None

    def test_recognize_new_experiment(self) -> None:
        """Test recognizing new experiment intentions."""
        recognizer = IntentionRecognizer(use_llm=False)

        # Chinese patterns
        intention = recognizer.recognize("帮我优化数据库性能")
        assert intention is not None
        assert intention.type == IntentionType.NEW_EXPERIMENT

        intention = recognizer.recognize("解决内存泄漏问题")
        assert intention is not None
        assert intention.type == IntentionType.NEW_EXPERIMENT

        # English patterns
        intention = recognizer.recognize("how to implement caching")
        assert intention is not None
        assert intention.type == IntentionType.NEW_EXPERIMENT

    def test_recognize_attempt(self) -> None:
        """Test recognizing attempt intentions."""
        recognizer = IntentionRecognizer(use_llm=False)

        intention = recognizer.recognize("用Redis缓存试试")
        assert intention is not None
        assert intention.type == IntentionType.ATTEMPT

        intention = recognizer.recognize("尝试加索引")
        assert intention is not None
        assert intention.type == IntentionType.ATTEMPT

        intention = recognizer.recognize("try using async")
        assert intention is not None
        assert intention.type == IntentionType.ATTEMPT

    def test_recognize_branch(self) -> None:
        """Test recognizing branch intentions."""
        recognizer = IntentionRecognizer(use_llm=False)

        # Note: "换个方法试试" is ambiguous as it contains both branch and attempt keywords
        # Use clearer branch-only phrases
        intention = recognizer.recognize("换个方法")
        assert intention is not None
        assert intention.type == IntentionType.BRANCH

        intention = recognizer.recognize("另一种方案")
        assert intention is not None
        assert intention.type == IntentionType.BRANCH

        # Test "instead" pattern - use phrase without "try" to avoid ATTEMPT match
        intention = recognizer.recognize("use instead a different approach")
        assert intention is not None
        assert intention.type == IntentionType.BRANCH

        # Test "another" pattern - use phrase without "try" to avoid ATTEMPT match
        intention = recognizer.recognize("another approach would be using cache")
        assert intention is not None
        assert intention.type == IntentionType.BRANCH

    def test_recognize_success(self) -> None:
        """Test recognizing success results."""
        recognizer = IntentionRecognizer(use_llm=False)

        intention = recognizer.recognize("成功了")
        assert intention is not None
        assert intention.type == IntentionType.RESULT_SUCCESS

        intention = recognizer.recognize("搞定了，响应时间降到100ms")
        assert intention is not None
        assert intention.type == IntentionType.RESULT_SUCCESS

        intention = recognizer.recognize("it works perfectly")
        assert intention is not None
        assert intention.type == IntentionType.RESULT_SUCCESS

    def test_recognize_failed(self) -> None:
        """Test recognizing failed results."""
        recognizer = IntentionRecognizer(use_llm=False)

        intention = recognizer.recognize("不行，报错了")
        assert intention is not None
        assert intention.type == IntentionType.RESULT_FAILED

        intention = recognizer.recognize("没效果")
        assert intention is not None
        assert intention.type == IntentionType.RESULT_FAILED

        intention = recognizer.recognize("error: connection refused")
        assert intention is not None
        assert intention.type == IntentionType.RESULT_FAILED

    def test_recognize_aborted(self) -> None:
        """Test recognizing aborted results."""
        recognizer = IntentionRecognizer(use_llm=False)

        intention = recognizer.recognize("算了，放弃")
        assert intention is not None
        assert intention.type == IntentionType.RESULT_ABORTED

        intention = recognizer.recognize("give up on this approach")
        assert intention is not None
        assert intention.type == IntentionType.RESULT_ABORTED

    def test_recognize_none(self) -> None:
        """Test recognizing no intention."""
        recognizer = IntentionRecognizer(use_llm=False)

        intention = recognizer.recognize("what do you think?")
        assert intention is None

        intention = recognizer.recognize("can you explain this?")
        assert intention is None

    def test_recognize_empty(self) -> None:
        """Test recognizing empty message."""
        recognizer = IntentionRecognizer(use_llm=False)

        intention = recognizer.recognize("")
        assert intention is None

    def test_recognize_from_context(self) -> None:
        """Test recognizing from conversation context."""
        recognizer = IntentionRecognizer(use_llm=False)

        turns = [
            ConversationTurn(role="user", content="Hello", timestamp=1, session_id="s1"),
            ConversationTurn(role="user", content="尝试新方法", timestamp=2, session_id="s1"),
        ]

        context = ConversationContext(
            session_id="s1",
            project="/test",
            turns=turns,
        )

        intention = recognizer.recognize(context)
        assert intention is not None
        assert intention.type == IntentionType.ATTEMPT

    def test_calculate_confidence(self) -> None:
        """Test confidence calculation."""
        recognizer = IntentionRecognizer(use_llm=False)

        # Pattern match without exact text match - base confidence 0.7
        confidence = recognizer._calculate_confidence("try this new method", r"try.*")
        # Should be around 0.7 since "try" is in the message
        assert confidence >= 0.7

        # Short message should have lower confidence
        confidence_short = recognizer._calculate_confidence("试", r"尝试.*")
        assert confidence_short < confidence

    def test_recognize_batch(self) -> None:
        """Test batch recognition."""
        recognizer = IntentionRecognizer(use_llm=False)

        messages = [
            "帮我优化性能",
            "尝试缓存",
            "成功了",
        ]

        results = recognizer.recognize_batch(messages)

        assert len(results) == 3
        assert results[0].type == IntentionType.NEW_EXPERIMENT
        assert results[1].type == IntentionType.ATTEMPT
        assert results[2].type == IntentionType.RESULT_SUCCESS


class TestPatternMatching:
    """Test the pattern matching functionality."""

    def test_patterns_exist(self) -> None:
        """Test that patterns exist for all intention types."""
        assert IntentionType.NEW_EXPERIMENT in INTENT_PATTERNS
        assert IntentionType.ATTEMPT in INTENT_PATTERNS
        assert IntentionType.BRANCH in INTENT_PATTERNS
        assert IntentionType.RESULT_SUCCESS in INTENT_PATTERNS
        assert IntentionType.RESULT_FAILED in INTENT_PATTERNS
        assert IntentionType.RESULT_ABORTED in INTENT_PATTERNS

    def test_patterns_are_lists(self) -> None:
        """Test that patterns are lists of strings."""
        for patterns in INTENT_PATTERNS.values():
            assert isinstance(patterns, list)
            for pattern in patterns:
                assert isinstance(pattern, str)


class TestQuickRecognize:
    """Test the quick_recognize convenience function."""

    def test_quick_recognize_success(self) -> None:
        """Test quick recognition of success."""
        intention = quick_recognize("搞定了！")
        assert intention is not None
        assert intention.type == IntentionType.RESULT_SUCCESS

    def test_quick_recognize_none(self) -> None:
        """Test quick recognition returning None."""
        intention = quick_recognize("random message")
        assert intention is None


class TestHelpers:
    """Test helper functions."""

    def test_get_intention_icon(self) -> None:
        """Test getting intention icons."""
        assert get_intention_icon(IntentionType.NEW_EXPERIMENT) == "📝"
        assert get_intention_icon(IntentionType.ATTEMPT) == "🔬"
        assert get_intention_icon(IntentionType.BRANCH) == "🔀"
        assert get_intention_icon(IntentionType.RESULT_SUCCESS) == "✅"
        assert get_intention_icon(IntentionType.RESULT_FAILED) == "❌"
        assert get_intention_icon(IntentionType.RESULT_ABORTED) == "🚫"
        assert get_intention_icon(IntentionType.NONE) == "⚪"

    def test_get_intention_label(self) -> None:
        """Test getting intention labels."""
        assert get_intention_label(IntentionType.NEW_EXPERIMENT) == "新实验"
        assert get_intention_label(IntentionType.ATTEMPT) == "尝试"
        assert get_intention_label(IntentionType.BRANCH) == "分支"
        assert get_intention_label(IntentionType.RESULT_SUCCESS) == "成功"
        assert get_intention_label(IntentionType.RESULT_FAILED) == "失败"
        assert get_intention_label(IntentionType.RESULT_ABORTED) == "放弃"
        assert get_intention_label(IntentionType.NONE) == "无"
