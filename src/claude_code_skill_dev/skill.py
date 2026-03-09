"""Claude Code 技能开发框架核心模块."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillArgument:
    """技能参数定义."""

    name: str
    type: str
    required: bool = False
    default: Any = None
    description: str = ""


@dataclass
class SkillTrigger:
    """技能触发器定义."""

    pattern: str
    description: str = ""


@dataclass
class SkillConfig:
    """技能配置类."""

    name: str
    description: str
    version: str = "0.1.0"
    author: str = ""
    entry_point: str = ""
    triggers: list[SkillTrigger] = field(default_factory=list)
    args: list[SkillArgument] = field(default_factory=list)
    help_text: str = ""

    @classmethod
    def from_yaml(cls, yaml_path: Path) -> "SkillConfig":
        """从 YAML 文件加载配置."""
        import yaml

        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        triggers = [SkillTrigger(**t) for t in data.get("triggers", [])]
        args = [SkillArgument(**a) for a in data.get("args", [])]

        return cls(
            name=data["name"],
            description=data["description"],
            version=data.get("version", "0.1.0"),
            author=data.get("author", ""),
            entry_point=data.get("entry_point", ""),
            triggers=triggers,
            args=args,
            help_text=data.get("help_text", ""),
        )


class BaseSkill(ABC):
    """技能基类."""

    name: str = ""
    description: str = ""
    config: SkillConfig | None = None

    def __init__(self, config: SkillConfig | None = None):
        """初始化技能."""
        self.config = config

    @abstractmethod
    def invoke(self, args: str) -> str:
        """执行技能.

        Args:
            args: 用户输入的参数

        Returns:
            技能执行结果
        """
        pass

    def validate_args(self, args: str) -> tuple[bool, str]:
        """验证参数.

        Args:
            args: 用户输入的参数

        Returns:
            (是否有效, 错误信息)
        """
        return True, ""

    def get_help(self) -> str:
        """获取帮助信息."""
        if self.config and self.config.help_text:
            return self.config.help_text
        return f"## {self.name}\n\n{self.description}"


class SkillDevSkill(BaseSkill):
    """技能开发主技能."""

    name = "skill-dev"
    description = "Claude Code 技能开发框架"

    TEMPLATES = {
        "basic": "基础技能模板",
        "api": "API 调用技能模板",
        "file": "文件处理技能模板",
    }

    def invoke(self, args: str) -> str:
        """执行技能开发命令."""
        parts = args.strip().split()
        if not parts:
            return self.get_help()

        command = parts[0]

        if command == "/skill-create":
            return self._create_skill(parts[1:])
        elif command == "/skill-test":
            return self._test_skill()
        elif command == "/skill-validate":
            return self._validate_skill()
        else:
            return f"未知命令: {command}\n\n{self.get_help()}"

    def _create_skill(self, args: list[str]) -> str:
        """创建新技能模板."""
        if not args:
            return "错误: 请提供技能名称\n用法: /skill-create <name> [--template basic|api|file]"

        skill_name = args[0]
        template = "basic"

        # 解析参数
        for i, arg in enumerate(args):
            if arg == "--template" and i + 1 < len(args):
                template = args[i + 1]

        if template not in self.TEMPLATES:
            return f"错误: 未知模板 '{template}'\n可用模板: {', '.join(self.TEMPLATES.keys())}"

        # 创建技能目录
        skill_dir = Path(f"skills/{skill_name}")
        skill_dir.mkdir(parents=True, exist_ok=True)

        # 创建技能文件
        self._generate_skill_files(skill_dir, skill_name, template)

        return f"✅ 技能 '{skill_name}' 创建成功!\n📁 位置: {skill_dir}\n📋 模板: {self.TEMPLATES[template]}"

    def _generate_skill_files(self, skill_dir: Path, skill_name: str, template: str) -> None:
        """生成技能文件."""
        class_name = "".join(word.capitalize() for word in skill_name.replace("-", "_").split("_"))

        # 创建 skill.yaml
        yaml_content = f"""name: {skill_name}
description: "{self.TEMPLATES[template]}"
version: "0.1.0"

entry_point: {skill_name}.{class_name}Skill

triggers:
  - pattern: "/{skill_name}"
    description: "触发 {skill_name} 技能"

args:
  - name: input
    type: string
    required: false
    description: "输入参数"

help_text: |
  ## {class_name} Skill

  {self.TEMPLATES[template]}

  ### 用法

  ```
  /{skill_name} [input]
  ```
"""
        (skill_dir / "skill.yaml").write_text(yaml_content, encoding="utf-8")

        # 创建主 Python 文件
        py_content = self._get_template_code(template, skill_name, class_name)
        (skill_dir / f"{skill_name}.py").write_text(py_content, encoding="utf-8")

        # 创建 __init__.py
        (skill_dir / "__init__.py").write_text(f'"""{skill_name} skill."""\n', encoding="utf-8")

    def _get_template_code(self, template: str, skill_name: str, class_name: str) -> str:
        """获取模板代码."""
        if template == "basic":
            return f"""\"\"\"{skill_name} skill implementation.\"\"\"

from claude_code_skill_dev.skill import BaseSkill


class {class_name}Skill(BaseSkill):
    \"\"\"{skill_name} skill.\"\"\"

    name = "{skill_name}"
    description = "{self.TEMPLATES[template]}"

    def invoke(self, args: str) -> str:
        \"\"\"执行技能.\"\"\"
        if not args:
            return self.get_help()
        return f"Hello from {class_name}Skill! Args: {{args}}"
"""

        elif template == "api":
            return f"""\"\"\"{skill_name} skill with API calls.\"\"\"

import requests
from claude_code_skill_dev.skill import BaseSkill


class {class_name}Skill(BaseSkill):
    \"\"\"{skill_name} API skill.\"\"\"

    name = "{skill_name}"
    description = "{self.TEMPLATES[template]}"
    base_url = "https://api.example.com"

    def invoke(self, args: str) -> str:
        \"\"\"执行 API 调用.\"\"\"
        # TODO: 实现 API 调用
        return f"API call with args: {{args}}"

    def _make_request(self, endpoint: str, method: str = "GET", data: dict | None = None) -> dict:
        \"\"\"发起 HTTP 请求.\"\"\"
        url = f"{{self.base_url}}/{{endpoint}}"
        response = requests.request(method, url, json=data)
        response.raise_for_status()
        return response.json()
"""

        elif template == "file":
            return f"""\"\"\"{skill_name} skill with file operations.\"\"\"

from pathlib import Path
from claude_code_skill_dev.skill import BaseSkill


class {class_name}Skill(BaseSkill):
    \"\"\"{skill_name} file processing skill.\"\"\"

    name = "{skill_name}"
    description = "{self.TEMPLATES[template]}"

    def invoke(self, args: str) -> str:
        \"\"\"处理文件.\"\"\"
        file_path = Path(args.strip())
        if not file_path.exists():
            return f"错误: 文件不存在 {{file_path}}"
        # TODO: 实现文件处理逻辑
        return f"Processing file: {{file_path}}"

    def _read_file(self, path: Path) -> str:
        \"\"\"读取文件内容.\"\"\"
        return path.read_text(encoding="utf-8")

    def _write_file(self, path: Path, content: str) -> None:
        \"\"\"写入文件内容.\"\"\"
        path.write_text(content, encoding="utf-8")
"""

        return ""

    def _test_skill(self) -> str:
        """测试当前技能."""
        import subprocess

        try:
            result = subprocess.run(
                ["poetry", "run", "pytest", "-v"],
                capture_output=True,
                text=True,
                check=True,
            )
            return f"✅ 测试通过!\n\n{{result.stdout}}"
        except subprocess.CalledProcessError as e:
            return f"❌ 测试失败!\n\n{{e.stdout}}\n{{e.stderr}}"

    def _validate_skill(self) -> str:
        """验证技能配置."""
        skill_yaml = Path("skill.yaml")
        if not skill_yaml.exists():
            return "❌ 错误: 当前目录下未找到 skill.yaml"

        try:
            config = SkillConfig.from_yaml(skill_yaml)
            issues = []

            if not config.name:
                issues.append("- 缺少技能名称 (name)")
            if not config.description:
                issues.append("- 缺少技能描述 (description)")
            if not config.entry_point:
                issues.append("- 缺少入口点 (entry_point)")
            if not config.triggers:
                issues.append("- 缺少触发器 (triggers)")

            if issues:
                return "⚠️ 配置问题:\n" + "\n".join(issues)

            return f"✅ 技能配置有效!\n\n名称: {{config.name}}\n描述: {{config.description}}\n版本: {{config.version}}"
        except Exception as e:
            return f"❌ 验证失败: {{e}}"

    def get_help(self) -> str:
        """获取帮助信息."""
        return """## Skill Dev 框架

用于开发 Claude Code 技能的通用框架。

### 命令

- `/skill-create <name> [--template basic|api|file]` - 创建新技能
- `/skill-test` - 运行测试
- `/skill-validate` - 验证配置

### 示例

```
/skill-create my-skill --template api
/skill-test
/skill-validate
```

### 可用模板

- `basic` - 基础技能模板
- `api` - API 调用技能模板
- `file` - 文件处理技能模板
"""
