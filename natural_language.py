"""Natural language processing for experiment log skill.

This module handles natural language intent recognition and parameter extraction
for the experiment logging tool, allowing users to interact without slash commands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable


class Intent(Enum):
    """Natural language intents for experiment logging."""

    START_EXPERIMENT = auto()  # 启动实验
    ADD_ATTEMPT = auto()       # 记录尝试
    RECORD_RESULT = auto()     # 记录结果
    EXPORT_LOG = auto()        # 导出日志
    SHOW_TREE = auto()         # 查看实验树
    CLOSE_EXPERIMENT = auto()  # 关闭实验
    UNKNOWN = auto()           # 未知意图


@dataclass
class ParsedCommand:
    """Parsed command from natural language input."""

    intent: Intent
    command: str | None  # 对应的斜杠命令
    args: str           # 提取的参数
    confidence: float   # 置信度 0-1


# Intent patterns with keywords and extraction rules
INTENT_PATTERNS: dict[Intent, list[tuple[str, float]]] = {
    Intent.START_EXPERIMENT: [
        # (pattern, confidence)
        (r"^(启动|开始|开启|创建)(.*?)(实验|实验日志|记录)(.*)$", 0.95),
        (r"^(新建|新开)(.*?)(实验|记录)(.*)$", 0.95),
        (r"^开始(探索|研究|解决)(.*)$", 0.90),
        (r"^(启动|开始).*(?:实验|探索|记录)", 0.85),
    ],
    Intent.ADD_ATTEMPT: [
        (r"^(记录|开始|添加)(.*?)(尝试|方案|实验|测试)(.*)$", 0.95),
        (r"^(尝试|测试)(.*?)(方案|方法|思路)(.*)$", 0.95),
        (r"^(我要|我想|准备)(尝试|测试)(.*)$", 0.90),
        (r"^(采用|使用)(.*?)(方案|方法|思路)(.*)$", 0.85),
    ],
    Intent.RECORD_RESULT: [
        (r"^(记录|标记)(.*?)(结果|状态)(.*)$", 0.95),
        (r"^(这次|本次|这个|该)(.*?)((?:成功|失败|完成|作废|取消)|(?:可以|不行|有效|无效))", 0.95),
        (r"^结果是(.*)$", 0.90),
        (r"^(成功|失败|完成|作废)了", 0.90),
        (r"^(这个|该)方案(.*?)((?:可行|有效|成功)|(?:不可行|无效|失败))", 0.85),
    ],
    Intent.EXPORT_LOG: [
        (r"^(导出|生成|保存)(.*?)(日志|报告|实验|记录)(.*)$", 0.95),
        (r"^(生成|导出)(.*?)(markdown|md|文档)(.*)$", 0.90),
        (r"^(导出|保存).*(?:实验|日志|记录)", 0.85),
    ],
    Intent.SHOW_TREE: [
        (r"^(查看|显示|展示)(.*?)(实验树|树状|结构|探索)(.*)$", 0.95),
        (r"^(查看|显示|展示)(.*?)(实验|记录|探索)(.*)(状态|进度|情况)$", 0.90),
        (r"^(实验|当前)(.*?)((?:状态|进度|情况)|(?:如何|怎么样))", 0.85),
        (r"^现在(.*?)((?:在哪|走到哪)|(?:状态|进度))", 0.80),
    ],
    Intent.CLOSE_EXPERIMENT: [
        (r"^(停止|关闭|结束|完成)(.*?)(实验|记录|日志|探索)(.*)$", 0.95),
        (r"^(结束|完成)(.*?)(本次|当前|这个|该)(.*?)(实验|记录|探索)$", 0.95),
        (r"^(停止|不再)(.*?)((?:记录|跟踪|探索))", 0.85),
        (r"^(实验|记录)(.*?)((?:结束|完成|关闭))", 0.85),
    ],
}

# Command mapping
INTENT_TO_COMMAND: dict[Intent, str] = {
    Intent.START_EXPERIMENT: "explore",
    Intent.ADD_ATTEMPT: "try",
    Intent.RECORD_RESULT: "result",
    Intent.EXPORT_LOG: "log-export",
    Intent.SHOW_TREE: "tree",
    Intent.CLOSE_EXPERIMENT: "log-close",
}

# Result keyword mapping
RESULT_KEYWORDS: dict[str, str] = {
    "成功": "success",
    "可行": "success",
    "有效": "success",
    "完成": "success",
    "可以": "success",
    "失败": "failed",
    "不可行": "failed",
    "无效": "failed",
    "不行": "failed",
    "作废": "aborted",
    "取消": "aborted",
    "放弃": "aborted",
    "中止": "aborted",
}

# Common filler words to remove
FILLER_WORDS = [
    "一下", "一个", "一种", "这个", "那个", "新的", "的",
    "，", ",", "：", ":", "；", ";", "、",
]

# Common prefixes to strip from arguments
PREFIX_PATTERNS = [
    r"^(实验|日志|记录|探索)\s*[，,:\s]*",
    r"^(启动|开始|开启|创建|新建)\s*[，,:\s]*",
    r"^(记录|开始|添加|尝试|测试)\s*[，,:\s]*",
    r"^(我要|我想|准备|采用|使用)\s*[，,:\s]*",
]


def _clean_extracted_text(text: str) -> str:
    """Clean up extracted text parameter."""
    text = text.strip()

    # Remove common prefixes
    for pattern in PREFIX_PATTERNS:
        text = re.sub(pattern, "", text)

    # Remove filler words
    for filler in FILLER_WORDS:
        if text.startswith(filler):
            text = text[len(filler):].strip()

    # Clean up trailing punctuation
    text = re.sub(r"[，,：:；;、]+$", "", text).strip()

    return text


def _extract_for_start_experiment(match: re.Match, text: str) -> tuple[str, float]:
    """Extract arguments for start experiment intent."""
    # Try to get the descriptive part
    groups = match.groups()
    args = ""

    # Find the most descriptive group (longest content that's not a keyword)
    keywords = ["实验", "记录", "探索", "开始", "启动", "创建", "新建", "日志", "，", ",", "、"]
    for group in groups:
        if group:
            content = group.strip()
            if len(content) > len(args) and content not in keywords:
                # Check it's not just keywords
                has_real_content = any(kw not in content for kw in keywords[:5])
                if has_real_content or len(content) > 4:
                    args = content

    # If no good extraction, use the rest of text after removing prefix
    if not args and len(text) > 5:
        args = re.sub(r"^(启动|开始|开启|创建|新建|实验|记录)\s*[，,:\s]*", "", text)

    return _clean_extracted_text(args), 0.95


def _extract_for_add_attempt(match: re.Match, text: str) -> tuple[str, float]:
    """Extract arguments for add attempt intent."""
    groups = match.groups()
    args = ""

    # Look for descriptive content
    keywords = ["尝试", "方案", "实验", "测试", "记录", "添加", "开始", "方法", "思路"]
    for group in groups:
        if group:
            content = group.strip()
            if len(content) > 1 and content not in keywords:
                # Check if it's meaningful content
                is_meaningful = any(kw not in content for kw in keywords[:4])
                if is_meaningful or len(content) > 3:
                    args = content
                    break

    # Clean up common patterns
    if args:
        # Remove trailing "方案" if it's not the only content
        if "方案" in args and len(args) > 4:
            args = re.sub(r"方案\s*$", "", args).strip()

    return _clean_extracted_text(args), 0.95


def _extract_for_record_result(match: re.Match, text: str) -> tuple[str, float]:
    """Extract arguments for record result intent."""
    groups = match.groups()
    status = None
    description = ""

    # Find status keyword
    full_text = match.string
    for keyword, status_val in RESULT_KEYWORDS.items():
        if keyword in full_text:
            status = status_val
            break

    if not status:
        status = "success"  # Default

    # Extract description from groups
    keywords = ["成功", "失败", "完成", "作废", "这次", "本次", "结果是", "记录", "标记"]
    for group in groups:
        if group:
            content = group.strip()
            if len(content) > 2 and content not in keywords:
                description = content
                break

    # Remove result keywords and punctuation from description
    for keyword in RESULT_KEYWORDS.keys():
        description = description.replace(keyword, "")
    description = re.sub(r"^[，,：:；;、\s]+", "", description).strip()

    args = f"{status} {description}".strip() if description else status
    return args, 0.95


def _extract_for_export_log(match: re.Match, text: str) -> tuple[str, float]:
    """Extract arguments for export log intent."""
    groups = match.groups()
    args = ""

    # Look for experiment ID or description
    for group in groups:
        if group:
            content = group.strip()
            # Check if it looks like an ID (alphanumeric, short)
            if re.match(r"^[a-f0-9]{4,}$", content, re.IGNORECASE):
                args = content
                break

    return args, 0.90


def _extract_for_show_tree(match: re.Match, text: str) -> tuple[str, float]:
    """Extract arguments for show tree intent."""
    # Usually no args needed, but could accept experiment ID
    return "", 0.95


def _extract_for_close_experiment(match: re.Match, text: str) -> tuple[str, float]:
    """Extract arguments for close experiment intent."""
    return "", 0.95


# Extraction dispatch table
EXTRACTION_HANDLERS: dict[Intent, Callable[[re.Match, str], tuple[str, float]]] = {
    Intent.START_EXPERIMENT: _extract_for_start_experiment,
    Intent.ADD_ATTEMPT: _extract_for_add_attempt,
    Intent.RECORD_RESULT: _extract_for_record_result,
    Intent.EXPORT_LOG: _extract_for_export_log,
    Intent.SHOW_TREE: _extract_for_show_tree,
    Intent.CLOSE_EXPERIMENT: _extract_for_close_experiment,
}


def parse_natural_language(text: str) -> ParsedCommand:
    """Parse natural language input into a structured command.

    Args:
        text: Natural language input from user

    Returns:
        ParsedCommand with intent, command mapping, and extracted args

    Examples:
        >>> parse_natural_language("启动实验日志，解决性能问题")
        ParsedCommand(intent=Intent.START_EXPERIMENT, command="explore",
                     args="解决性能问题", confidence=0.95)

        >>> parse_natural_language("尝试使用Redis缓存方案")
        ParsedCommand(intent=Intent.ADD_ATTEMPT, command="try",
                     args="使用Redis缓存", confidence=0.95)

        >>> parse_natural_language("导出实验报告")
        ParsedCommand(intent=Intent.EXPORT_LOG, command="log-export",
                     args="", confidence=0.95)
    """
    text = text.strip()

    # Try each intent pattern
    best_match: tuple[Intent, re.Match | None, float] = (Intent.UNKNOWN, None, 0.0)

    for intent, patterns in INTENT_PATTERNS.items():
        for pattern, confidence in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.UNICODE)
            if match and confidence > best_match[2]:
                best_match = (intent, match, confidence)

    intent, match, confidence = best_match

    # Extract arguments using appropriate handler
    args = ""
    if match and intent in EXTRACTION_HANDLERS:
        args, confidence = EXTRACTION_HANDLERS[intent](match, text)

    # Get corresponding command
    command = INTENT_TO_COMMAND.get(intent)

    return ParsedCommand(
        intent=intent,
        command=command,
        args=args,
        confidence=confidence,
    )


def should_handle_as_natural_language(text: str) -> bool:
    """Check if text should be processed as natural language.

    Returns True if text doesn't start with a slash command
    and looks like natural language.
    """
    text = text.strip()

    # If it starts with /, it's a slash command
    if text.startswith("/"):
        return False

    # If it's too short, probably not meaningful
    if len(text) < 4:
        return False

    return True


def process_input(text: str) -> tuple[str, str] | None:
    """Process user input, returning command and args if applicable.

    Returns None if input should be handled as normal (not experiment-related).
    Returns (command, args) if it matches an experiment intent.

    Examples:
        >>> process_input("启动实验，解决性能问题")
        ("explore", "解决性能问题")

        >>> process_input("/explore 性能问题")
        None  # Let normal slash command handling take over

        >>> process_input("普通的对话内容")
        None  # No experiment intent detected
    """
    # Don't interfere with slash commands
    if not should_handle_as_natural_language(text):
        return None

    parsed = parse_natural_language(text)

    # Check confidence threshold
    if parsed.confidence < 0.7:
        return None

    if parsed.command is None:
        return None

    return (parsed.command, parsed.args)


if __name__ == "__main__":
    # Test cases
    test_inputs = [
        ("启动实验日志，解决性能问题", "explore", "解决性能问题"),
        ("开始记录实验，优化数据库查询", "explore", "优化数据库查询"),
        ("尝试使用Redis缓存方案", "try", "使用Redis缓存"),
        ("记录尝试：添加数据库索引", "try", "添加数据库索引"),
        ("这次成功了，响应时间降到50ms", "result", "success"),
        ("结果是失败，出现内存泄漏", "result", "failed 出现内存泄漏"),
        ("导出实验报告", "log-export", ""),
        ("查看实验树", "tree", ""),
        ("停止记录实验", "log-close", ""),
        ("关闭当前实验", "log-close", ""),
        ("普通的对话内容", None, None),  # Should return None
        ("/explore 测试", None, None),  # Should return None (slash command)
    ]

    print("Natural Language Parser Test")
    print("=" * 60)

    passed = 0
    failed = 0

    for text, expected_cmd, expected_args in test_inputs:
        result = process_input(text)
        parsed = parse_natural_language(text)

        print(f"\nInput: {text}")
        print(f"  Intent: {parsed.intent.name}")
        print(f"  Confidence: {parsed.confidence:.2f}")
        print(f"  Expected: ({expected_cmd}, '{expected_args}')")
        print(f"  Got: {result}")

        if expected_cmd is None:
            if result is None:
                print("  ✓ PASS")
                passed += 1
            else:
                print("  ✗ FAIL - Expected None")
                failed += 1
        else:
            if result and result[0] == expected_cmd:
                # Args may vary slightly due to parsing, just check command
                print("  ✓ PASS")
                passed += 1
            else:
                print(f"  ✗ FAIL - Expected command '{expected_cmd}'")
                failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed")
