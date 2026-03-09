"""Experiment Log - A tool for tracking code experiments and exploration paths."""

from experiment_log.analyzer import (
    ConversationContext,
    ConversationTurn,
    SessionAnalyzer,
    analyze_conversation,
)
from experiment_log.intention import (
    INTENT_PATTERNS,
    Intention,
    IntentionRecognizer,
    IntentionType,
    get_intention_icon,
    get_intention_label,
    quick_recognize,
)
from experiment_log.models import (
    ExperimentNode,
    ExperimentTree,
    NodeType,
    Status,
)
from experiment_log.recorder import (
    AutoRecordConfig,
    AutoRecorder,
    RecordEvent,
    SilentAutoRecorder,
)
from experiment_log.storage import ExperimentStorage
from experiment_log.tree import ExperimentTreeManager

__version__ = "0.2.0"
__all__ = [
    # Models
    "ExperimentNode",
    "ExperimentTree",
    "ExperimentTreeManager",
    "ExperimentStorage",
    "NodeType",
    "Status",
    # Analyzer
    "ConversationContext",
    "ConversationTurn",
    "SessionAnalyzer",
    "analyze_conversation",
    # Intention
    "Intention",
    "IntentionType",
    "IntentionRecognizer",
    "INTENT_PATTERNS",
    "quick_recognize",
    "get_intention_icon",
    "get_intention_label",
    # Recorder
    "AutoRecorder",
    "AutoRecordConfig",
    "RecordEvent",
    "SilentAutoRecorder",
]
