"""Intention recognition for experiment logging."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

from experiment_log.analyzer import ConversationContext


class IntentionType(Enum):
    """Types of intentions that can be recognized."""

    NEW_EXPERIMENT = "new_experiment"  # New problem/goal
    ATTEMPT = "attempt"  # Trying a solution
    BRANCH = "branch"  # Alternative approach
    RESULT_SUCCESS = "result_success"  # Successful outcome
    RESULT_FAILED = "result_failed"  # Failed outcome
    RESULT_ABORTED = "result_aborted"  # Abandoned attempt
    NONE = "none"  # No relevant intention


@dataclass
class Intention:
    """Recognized intention from conversation."""

    type: IntentionType
    description: str
    confidence: float = 1.0
    metadata: dict[str, Any] | None = None

    # 结构化信息
    problem_context: str = ""  # 当前问题上下文
    possible_actions: list[str] = field(default_factory=list)  # 可能的操作
    current_action: str = ""  # 当前执行的操作
    error_info: str = ""  # 错误信息
    code_snippets: list[str] = field(default_factory=list)  # 代码片段
    files_involved: list[str] = field(default_factory=list)  # 涉及的文件

    def __post_init__(self) -> None:
        if self.metadata is None:
            self.metadata = {}


# Keyword patterns for fallback when LLM is not available
INTENT_PATTERNS: dict[IntentionType, list[str]] = {
    IntentionType.NEW_EXPERIMENT: [
        r"帮我.*",
        r"解决.*问题",
        r"优化.*",
        r"实现.*",
        r"如何.*",
        r"怎么.*",
        r"问题.*",
        r"需求.*",
        r"fix.*",
        r"solve.*",
        r"implement.*",
        r"optimize.*",
        r"how to.*",
        r"create.*",
        r"build.*",
    ],
    IntentionType.ATTEMPT: [
        r"试试.*",
        r"尝试.*",
        r"用.*方法",
        r"使用.*",
        r"试一下.*",
        r"看看.*",
        r"try.*",
        r"attempt.*",
        r"use.*method",
        r"let's.*",
        r"maybe.*",
    ],
    IntentionType.BRANCH: [
        r"换个.*",
        r"另一种.*",
        r"或者.*",
        r"要不.*",
        r" alternatively.*",
        r"instead.*",
        r"another.*",
        r"different.*",
        r"change.*",
        r"switch.*",
    ],
    IntentionType.RESULT_SUCCESS: [
        r"成功.*",
        r"搞定.*",
        r"解决.*",
        r"可以.*",
        r"worked.*",
        r"success.*",
        r"fixed.*",
        r"done.*",
        r"completed.*",
        r"working.*",
        r"great.*",
        r"perfect.*",
        r"awesome.*",
    ],
    IntentionType.RESULT_FAILED: [
        r"不行.*",
        r"失败.*",
        r"报错.*",
        r"没效果.*",
        r"错误.*",
        r"failed.*",
        r"error.*",
        r"not working.*",
        r"doesn't work.*",
        r"issue.*",
        r"problem.*",
        r"broken.*",
    ],
    IntentionType.RESULT_ABORTED: [
        r"算了.*",
        r"放弃.*",
        r"不.*做.*",
        r"stop.*",
        r"give up.*",
        r"abandon.*",
        r"skip.*",
        r"nevermind.*",
        r"cancel.*",
    ],
}


class IntentionRecognizer:
    """Recognizes intentions from conversation context."""

    def __init__(self, use_llm: bool = False, llm_client: Any | None = None):
        """Initialize the recognizer.

        Args:
            use_llm: Whether to use LLM for recognition
            llm_client: Optional LLM client instance
        """
        self.use_llm = use_llm
        self.llm_client = llm_client

    def recognize(self, context: ConversationContext | str) -> Intention | None:
        """Recognize intention from conversation context.

        Args:
            context: Conversation context or direct message string

        Returns:
            Recognized intention or None
        """
        # Extract the latest user message
        if isinstance(context, ConversationContext):
            message = context.get_latest_user_message()
        else:
            message = context

        if not message:
            return None

        # Try LLM-based recognition if enabled
        if self.use_llm and self.llm_client:
            return self._recognize_with_llm(context, message)

        # Fall back to pattern matching
        return self._recognize_with_patterns(message)

    def _recognize_with_llm(
        self, context: ConversationContext, latest_message: str
    ) -> Intention | None:
        """Use LLM to recognize intention.

        Args:
            context: Full conversation context
            latest_message: The latest user message

        Returns:
            Recognized intention or None
        """
        prompt = self._build_prompt(context)

        try:
            # Call LLM - this is a generic interface
            # Actual implementation depends on the LLM client provided
            response = self._call_llm(prompt)
            return self._parse_llm_response(response, latest_message)
        except Exception:
            # Fall back to pattern matching on error
            return self._recognize_with_patterns(latest_message)

    def _build_prompt(self, context: ConversationContext) -> str:
        """Build the LLM prompt for intention recognition.

        Args:
            context: Conversation context

        Returns:
            Prompt string
        """
        return f"""Analyze the following programming conversation and identify the user's current intention.

Conversation history:
{context.format_history()}

Identify the intention from these options:
1. NEW_EXPERIMENT - User presents a new problem/goal (e.g., "帮我优化...", "解决...问题", "how to implement...")
2. ATTEMPT - User tries a solution (e.g., "试试...", "用...方法", "try using...")
3. BRANCH - User switches to alternative approach (e.g., "换个方法...", "另一种方案...", "alternatively...")
4. RESULT_SUCCESS - User indicates success (e.g., "搞定了", "成功了", "it works!")
5. RESULT_FAILED - User indicates failure (e.g., "不行", "报错", "it failed...")
6. RESULT_ABORTED - User abandons attempt (e.g., "算了", "放弃", "give up...")
7. NONE - No relevant experimental intention

Respond in this exact format:
TYPE: <intention_type>
DESCRIPTION: <brief description of what the user is doing>
CONFIDENCE: <0.0-1.0>

Example:
TYPE: NEW_EXPERIMENT
DESCRIPTION: User wants to optimize database query performance
CONFIDENCE: 0.95
"""

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM with the prompt.

        Args:
            prompt: The prompt to send

        Returns:
            LLM response text

        Raises:
            RuntimeError: If LLM call fails
        """
        if self.llm_client is None:
            raise RuntimeError("No LLM client provided")

        # This is a generic interface - actual implementation
        # depends on the LLM client (OpenAI, Anthropic, etc.)
        # The client should have a 'complete' or similar method
        if hasattr(self.llm_client, 'complete'):
            return self.llm_client.complete(prompt)
        elif hasattr(self.llm_client, 'generate'):
            return self.llm_client.generate(prompt)
        elif hasattr(self.llm_client, 'chat'):
            return self.llm_client.chat([{"role": "user", "content": prompt}])
        else:
            raise RuntimeError("LLM client has no recognized method")

    def _parse_llm_response(self, response: str, message: str) -> Intention | None:
        """Parse the LLM response into an Intention.

        Args:
            response: Raw LLM response
            message: Original user message

        Returns:
            Parsed intention or None
        """
        lines = response.strip().split("\n")
        intent_type = IntentionType.NONE
        description = message
        confidence = 0.5

        for line in lines:
            line = line.strip()
            if line.startswith("TYPE:"):
                type_str = line.split(":", 1)[1].strip().upper()
                try:
                    intent_type = IntentionType[type_str]
                except KeyError:
                    # Try to map common variations
                    type_map = {
                        "NEW EXPERIMENT": IntentionType.NEW_EXPERIMENT,
                        "RESULT SUCCESS": IntentionType.RESULT_SUCCESS,
                        "RESULT FAILED": IntentionType.RESULT_FAILED,
                        "RESULT ABORTED": IntentionType.RESULT_ABORTED,
                    }
                    intent_type = type_map.get(type_str, IntentionType.NONE)
            elif line.startswith("DESCRIPTION:"):
                description = line.split(":", 1)[1].strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except ValueError:
                    confidence = 0.5

        return Intention(
            type=intent_type,
            description=description,
            confidence=confidence,
        )

    def _recognize_with_patterns(self, message: str) -> Intention | None:
        """Recognize intention using keyword patterns.

        Args:
            message: User message to analyze

        Returns:
            Recognized intention or None
        """
        if not message:
            return None

        message_lower = message.lower()

        # Check each pattern type
        best_match: tuple[IntentionType, float] | None = None

        for intent_type, patterns in INTENT_PATTERNS.items():
            for pattern in patterns:
                # Remove regex special chars for simple matching
                if re.search(pattern, message_lower, re.IGNORECASE):
                    # Calculate confidence based on match quality
                    confidence = self._calculate_confidence(message_lower, pattern)
                    if best_match is None or confidence > best_match[1]:
                        best_match = (intent_type, confidence)

        if best_match and best_match[0] != IntentionType.NONE:
            # 提取结构化信息
            extracted = self._extract_structured_info(message)

            return Intention(
                type=best_match[0],
                description=message[:100],  # Truncate long messages
                confidence=best_match[1],
                problem_context=extracted["problem_context"],
                possible_actions=extracted["possible_actions"],
                current_action=extracted["current_action"],
                error_info=extracted["error_info"],
                code_snippets=extracted["code_snippets"],
                files_involved=extracted["files_involved"],
            )

        return None

    def _extract_structured_info(self, message: str) -> dict[str, Any]:
        """Extract structured information from a message.

        从消息中提取：
        - 当前问题上下文
        - 可能的操作列表
        - 当前执行的操作
        - 错误信息
        - 代码片段
        - 涉及的文件

        Args:
            message: User message to analyze

        Returns:
            Dictionary with extracted information
        """
        result = {
            "problem_context": "",
            "possible_actions": [],
            "current_action": "",
            "error_info": "",
            "code_snippets": [],
            "files_involved": [],
        }

        # 提取代码片段 (```code``` 格式)
        code_pattern = r"```[\w]*\n?([\s\S]*?)```"
        code_matches = re.findall(code_pattern, message)
        if code_matches:
            result["code_snippets"] = [c.strip() for c in code_matches if c.strip()]

        # 提取文件路径 (常见模式)
        file_patterns = [
            r"([a-zA-Z0-9_\-/]+\.[a-zA-Z]{1,10})",  # 文件路径如 src/main.py
            r"文件[：:]\s*([^\s,，]+)",  # 中文：文件：xxx.py
            r"file[：:]\s*([^\s,，]+)",  # English
            r"在\s+([a-zA-Z0-9_\-/]+\.[a-zA-Z]{1,10})",  # 在 xxx.py 中
            r"in\s+([a-zA-Z0-9_\-/]+\.[a-zA-Z]{1,10})",  # in xxx.py
        ]
        for pattern in file_patterns:
            file_matches = re.findall(pattern, message, re.IGNORECASE)
            for f in file_matches:
                if f not in result["files_involved"] and len(f) > 2:
                    result["files_involved"].append(f)

        # 提取错误信息
        error_patterns = [
            r"错误[：:]\s*(.+?)(?:\n|$)",
            r"Error[：:]\s*(.+?)(?:\n|$)",
            r"报错[：:?\s]*(.+?)(?:\n|$)",
            r"Exception[：:]\s*(.+?)(?:\n|$)",
            r"failed[：:]\s*(.+?)(?:\n|$)",
            r"失败[：:?\s]*(.+?)(?:\n|$)",
        ]
        for pattern in error_patterns:
            error_match = re.search(pattern, message, re.IGNORECASE)
            if error_match:
                result["error_info"] = error_match.group(1).strip()
                break

        # 提取问题上下文（关键词后跟的内容）
        problem_patterns = [
            r"(?:问题|problem|issue)[是为：:\s]+(.+?)(?:\n|$|，|,)",
            r"(?:需要|want|need)[是要]\s*(.+?)(?:\n|$|，|,)",
            r"(?:帮我|help me)[要帮]?\s*(.+?)(?:\n|$|，|,)",
            r"(?:解决|solve|fix)[掉]?\s*(.+?)(?:\n|$|，|,)",
        ]
        for pattern in problem_patterns:
            problem_match = re.search(pattern, message, re.IGNORECASE)
            if problem_match:
                result["problem_context"] = problem_match.group(1).strip()
                break

        # 如果没有匹配到问题上下文，使用整个消息（截断）
        if not result["problem_context"]:
            result["problem_context"] = message[:200] if len(message) > 200 else message

        # 提取当前执行的操作
        action_patterns = [
            r"(?:试试|尝试|try|attempt)[要用]?\s*(.+?)(?:\n|$|，|,|看看)",
            r"(?:用|use|using)\s*(.+?)(?:方法|方案|method|approach)",
            r"(?:修改|modify|change|update)[更]?\s*(.+?)(?:\n|$|，|,)",
            r"(?:添加|add|create)[创]?\s*(.+?)(?:\n|$|，|,)",
            r"(?:删除|delete|remove)[删]?\s*(.+?)(?:\n|$|，|,)",
            r"(?:正在|now|currently)\s*(.+?)(?:\n|$|，|,)",
        ]
        for pattern in action_patterns:
            action_match = re.search(pattern, message, re.IGNORECASE)
            if action_match:
                result["current_action"] = action_match.group(1).strip()
                break

        # 提取可能的操作列表（通过枚举词识别）
        list_patterns = [
            r"[一二三四五六七八九十1-9][、.．]\s*(.+?)(?=[一二三四五六七八九十1-9][、.．]|$|\n)",
            r"[-•·]\s*(.+?)(?=[-•·]|$|\n)",
            r"[首其]先\s*(.+?)[，,]?(?:然后|接着|再)",
            r"然后\s*(.+?)[，,]?(?:然后|接着|再|最后)",
            r"最后\s*(.+?)(?:\n|$)",
        ]
        for pattern in list_patterns:
            action_list = re.findall(pattern, message)
            if action_list:
                result["possible_actions"] = [a.strip() for a in action_list if a.strip()]
                break

        return result

    def _calculate_confidence(self, message: str, pattern: str) -> float:
        """Calculate confidence score for a pattern match.

        Args:
            message: The message text
            pattern: The matched pattern

        Returns:
            Confidence score between 0 and 1
        """
        # Base confidence
        confidence = 0.7

        # Increase confidence for exact matches
        # Remove regex wildcards for comparison
        pattern_clean = pattern.replace(".*", "").replace("\\", "")
        if pattern_clean in message:
            confidence += 0.2

        # Decrease for very short messages (might be ambiguous)
        if len(message) < 10:
            confidence -= 0.1

        # Cap at 0.95 for pattern-based matching
        return min(0.95, max(0.3, confidence))

    def recognize_batch(
        self, messages: list[str], context: ConversationContext | None = None
    ) -> list[Intention | None]:
        """Recognize intentions for multiple messages.

        Args:
            messages: List of messages to analyze
            context: Optional conversation context

        Returns:
            List of recognized intentions
        """
        results = []
        for message in messages:
            if context:
                # Update context with this message as latest
                # This is a simplified approach
                intention = self.recognize(message)
            else:
                intention = self.recognize(message)
            results.append(intention)
        return results


def quick_recognize(message: str) -> Intention | None:
    """Quick intention recognition without LLM.

    Args:
        message: Message to analyze

    Returns:
        Recognized intention or None
    """
    recognizer = IntentionRecognizer(use_llm=False)
    return recognizer.recognize(message)


def get_intention_icon(intention_type: IntentionType) -> str:
    """Get an icon for an intention type.

    Args:
        intention_type: The intention type

    Returns:
        Icon string
    """
    icons = {
        IntentionType.NEW_EXPERIMENT: "📝",
        IntentionType.ATTEMPT: "🔬",
        IntentionType.BRANCH: "🔀",
        IntentionType.RESULT_SUCCESS: "✅",
        IntentionType.RESULT_FAILED: "❌",
        IntentionType.RESULT_ABORTED: "🚫",
        IntentionType.NONE: "⚪",
    }
    return icons.get(intention_type, "⚪")


def get_intention_label(intention_type: IntentionType) -> str:
    """Get a human-readable label for an intention type.

    Args:
        intention_type: The intention type

    Returns:
        Label string
    """
    labels = {
        IntentionType.NEW_EXPERIMENT: "新实验",
        IntentionType.ATTEMPT: "尝试",
        IntentionType.BRANCH: "分支",
        IntentionType.RESULT_SUCCESS: "成功",
        IntentionType.RESULT_FAILED: "失败",
        IntentionType.RESULT_ABORTED: "放弃",
        IntentionType.NONE: "无",
    }
    return labels.get(intention_type, "未知")
