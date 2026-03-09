"""Auto-recorder for experiment logging based on recognized intentions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from experiment_log.analyzer import ConversationContext
from experiment_log.intention import (
    Intention,
    IntentionRecognizer,
    IntentionType,
    get_intention_icon,
    get_intention_label,
)
from experiment_log.models import Status
from experiment_log.storage import ExperimentStorage
from experiment_log.tree import ExperimentTreeManager


@dataclass
class AutoRecordConfig:
    """Configuration for auto-recording."""

    min_confidence: float = 0.6  # Minimum confidence to record
    auto_create_experiments: bool = True  # Auto-create new experiments
    auto_record_attempts: bool = True  # Auto-record attempts
    auto_record_results: bool = True  # Auto-record results
    confirm_before_record: bool = False  # Ask for confirmation
    quiet_mode: bool = False  # Suppress console output
    on_record_callback: Any | None = None  # Callback when recording


@dataclass
class RecordEvent:
    """Event representing a recorded experiment action."""

    action: str  # "create", "attempt", "branch", "result"
    intention_type: IntentionType
    description: str
    node_id: str | None = None
    experiment_id: str | None = None


class AutoRecorder:
    """Automatically records experiments based on recognized intentions."""

    def __init__(
        self,
        storage: ExperimentStorage | None = None,
        recognizer: IntentionRecognizer | None = None,
        config: AutoRecordConfig | None = None,
    ):
        """Initialize the auto-recorder.

        Args:
            storage: Storage instance for persistence
            recognizer: Intention recognizer
            config: Recording configuration
        """
        self.storage = storage or ExperimentStorage()
        self.recognizer = recognizer or IntentionRecognizer(use_llm=False)
        self.config = config or AutoRecordConfig()
        self.current_manager: ExperimentTreeManager | None = None
        self._last_intention: Intention | None = None

    def on_intention_detected(
        self, intention: Intention, context: ConversationContext | None = None
    ) -> RecordEvent | None:
        """Handle a detected intention.

        Args:
            intention: The recognized intention
            context: Optional conversation context

        Returns:
            RecordEvent if recorded, None otherwise
        """
        # Check confidence threshold
        if intention.confidence < self.config.min_confidence:
            return None

        # Skip NONE intentions
        if intention.type == IntentionType.NONE:
            return None

        self._last_intention = intention

        # Handle based on intention type
        match intention.type:
            case IntentionType.NEW_EXPERIMENT:
                if self.config.auto_create_experiments:
                    return self._create_experiment(intention, context)
            case IntentionType.ATTEMPT:
                if self.config.auto_record_attempts:
                    return self._add_attempt(intention, context, branch=False)
            case IntentionType.BRANCH:
                if self.config.auto_record_attempts:
                    return self._add_attempt(intention, context, branch=True)
            case IntentionType.RESULT_SUCCESS:
                if self.config.auto_record_results:
                    return self._record_result(intention, Status.SUCCESS, context)
            case IntentionType.RESULT_FAILED:
                if self.config.auto_record_results:
                    return self._record_result(intention, Status.FAILED, context)
            case IntentionType.RESULT_ABORTED:
                if self.config.auto_record_results:
                    return self._record_result(intention, Status.ABORTED, context)

        return None

    def _create_experiment(
        self, intention: Intention, context: ConversationContext | None
    ) -> RecordEvent | None:
        """Create a new experiment.

        Args:
            intention: The NEW_EXPERIMENT intention
            context: Conversation context

        Returns:
            RecordEvent if created
        """
        problem = intention.description

        # Create the experiment with structured info
        tree = self.storage.create_experiment(
            problem=problem,
            description=intention.problem_context or "Auto-recorded from conversation",
        )
        self.current_manager = ExperimentTreeManager(tree)

        # 更新根节点的结构化信息
        root = tree.get_root()
        if root:
            root.possible_actions = intention.possible_actions
            root.current_action = intention.current_action
            root.error_info = intention.error_info
            root.code_snippets = intention.code_snippets
            root.files_modified = intention.files_involved
            self.storage.save_experiment(tree)

        if not self.config.quiet_mode:
            icon = get_intention_icon(IntentionType.NEW_EXPERIMENT)
            label = get_intention_label(IntentionType.NEW_EXPERIMENT)
            print(f"{icon} Auto-recorded [{label}]: {problem[:60]}...")
            if intention.possible_actions:
                print(f"   可能的操作: {', '.join(intention.possible_actions[:3])}")
            if intention.current_action:
                print(f"   当前操作: {intention.current_action[:50]}")

        event = RecordEvent(
            action="create",
            intention_type=IntentionType.NEW_EXPERIMENT,
            description=problem,
            node_id=tree.root_id,
            experiment_id=tree.root_id[:8],
        )

        self._trigger_callback(event)
        return event

    def _add_attempt(
        self,
        intention: Intention,
        context: ConversationContext | None,
        branch: bool = False,
    ) -> RecordEvent | None:
        """Add an attempt node.

        Args:
            intention: The ATTEMPT or BRANCH intention
            context: Conversation context
            branch: Whether this is a branch (sibling) or child attempt

        Returns:
            RecordEvent if added
        """
        # Ensure we have a current experiment
        if self.current_manager is None:
            # Try to load the latest experiment
            tree = self.storage.load_latest()
            if tree:
                self.current_manager = ExperimentTreeManager(tree)
            else:
                if not self.config.quiet_mode:
                    print("⚠️  No active experiment. Creating one automatically.")
                # Auto-create an experiment with a generic name
                auto_intention = Intention(
                    type=IntentionType.NEW_EXPERIMENT,
                    description="Auto-created experiment",
                    confidence=1.0,
                )
                self._create_experiment(auto_intention, None)

        if not self.current_manager:
            return None

        # Add the attempt with structured info
        description = intention.description
        node_id = self.current_manager.add_attempt(
            title=description[:100],
            description=intention.problem_context or description,
            branch=branch,
        )

        # 更新节点的结构化信息
        node = self.current_manager.tree.nodes.get(node_id)
        if node:
            node.possible_actions = intention.possible_actions
            node.current_action = intention.current_action or description
            node.error_info = intention.error_info
            node.code_snippets = intention.code_snippets
            node.files_modified = intention.files_involved

        # Save the experiment
        self.storage.save_experiment(self.current_manager.tree)

        if not self.config.quiet_mode:
            icon = get_intention_icon(intention.type)
            label = get_intention_label(intention.type)
            prefix = "(branch) " if branch else ""
            print(f"{icon} Auto-recorded [{label}]: {prefix}{description[:60]}...")
            if intention.current_action:
                print(f"   当前操作: {intention.current_action[:50]}")
            if intention.files_involved:
                print(f"   涉及文件: {', '.join(intention.files_involved[:3])}")

        event = RecordEvent(
            action="branch" if branch else "attempt",
            intention_type=intention.type,
            description=description,
            node_id=node_id,
            experiment_id=self.current_manager.tree.root_id[:8],
        )

        self._trigger_callback(event)
        return event

    def _record_result(
        self,
        intention: Intention,
        status: Status,
        context: ConversationContext | None,
    ) -> RecordEvent | None:
        """Record a result.

        Args:
            intention: The result intention
            status: The result status
            context: Conversation context

        Returns:
            RecordEvent if recorded
        """
        if self.current_manager is None:
            # Try to load the latest experiment
            tree = self.storage.load_latest()
            if tree:
                self.current_manager = ExperimentTreeManager(tree)
            else:
                if not self.config.quiet_mode:
                    print("⚠️  No active experiment to record result for.")
                return None

        description = intention.description
        node_id = self.current_manager.add_result(
            status=status,
            description=description,
        )

        # 更新当前节点的结构化信息
        current = self.current_manager.tree.get_current()
        if current:
            current.action_result = description
            current.error_info = intention.error_info or current.error_info
            current.code_snippets = intention.code_snippets or current.code_snippets
            current.files_modified = intention.files_involved or current.files_modified

        # Save the experiment
        self.storage.save_experiment(self.current_manager.tree)

        if not self.config.quiet_mode:
            icon = get_intention_icon(intention.type)
            label = get_intention_label(intention.type)
            print(f"{icon} Auto-recorded [{label}]: {description[:60]}...")
            if intention.error_info:
                print(f"   错误信息: {intention.error_info[:50]}")

        event = RecordEvent(
            action="result",
            intention_type=intention.type,
            description=description,
            node_id=node_id,
            experiment_id=self.current_manager.tree.root_id[:8],
        )

        self._trigger_callback(event)
        return event

    def _trigger_callback(self, event: RecordEvent) -> None:
        """Trigger the record callback if configured.

        Args:
            event: The record event
        """
        if self.config.on_record_callback:
            try:
                self.config.on_record_callback(event)
            except Exception:
                # Don't let callbacks break the recording
                pass

    def process_message(self, message: str) -> RecordEvent | None:
        """Process a single message and record if applicable.

        Args:
            message: The message to process

        Returns:
            RecordEvent if recorded
        """
        intention = self.recognizer.recognize(message)
        if intention:
            return self.on_intention_detected(intention)
        return None

    def process_context(self, context: ConversationContext) -> RecordEvent | None:
        """Process a conversation context and record if applicable.

        Args:
            context: The conversation context

        Returns:
            RecordEvent if recorded
        """
        intention = self.recognizer.recognize(context)
        if intention:
            return self.on_intention_detected(intention, context)
        return None

    def get_current_experiment(self) -> ExperimentTreeManager | None:
        """Get the current experiment manager.

        Returns:
            Current ExperimentTreeManager or None
        """
        return self.current_manager

    def set_current_experiment(self, experiment_id: str) -> bool:
        """Set the current experiment by ID.

        Args:
            experiment_id: The experiment ID

        Returns:
            True if set successfully
        """
        tree = self.storage.load_experiment(experiment_id)
        if tree:
            self.current_manager = ExperimentTreeManager(tree)
            return True
        return False

    def get_last_intention(self) -> Intention | None:
        """Get the last recognized intention.

        Returns:
            Last intention or None
        """
        return self._last_intention


class SilentAutoRecorder(AutoRecorder):
    """Auto-recorder that operates silently (no console output)."""

    def __init__(
        self,
        storage: ExperimentStorage | None = None,
        recognizer: IntentionRecognizer | None = None,
    ):
        """Initialize silent recorder."""
        config = AutoRecordConfig(quiet_mode=True)
        super().__init__(storage, recognizer, config)
