"""Tests for skill module."""

import pytest
from pathlib import Path
from claude_code_skill_dev.skill import BaseSkill, SkillDevSkill, SkillConfig, SkillArgument, SkillTrigger


class MockSkill(BaseSkill):
    """Mock skill for testing."""

    name = "mock-skill"
    description = "A mock skill for testing"

    def invoke(self, args: str) -> str:
        return f"Mock result: {args}"


class TestBaseSkill:
    """Tests for BaseSkill."""

    def test_invoke(self):
        skill = MockSkill()
        result = skill.invoke("test args")
        assert result == "Mock result: test args"

    def test_validate_args(self):
        skill = MockSkill()
        valid, msg = skill.validate_args("test")
        assert valid is True
        assert msg == ""

    def test_get_help_default(self):
        skill = MockSkill()
        help_text = skill.get_help()
        assert "mock-skill" in help_text
        assert "A mock skill for testing" in help_text


class TestSkillDevSkill:
    """Tests for SkillDevSkill."""

    def test_invoke_help(self):
        skill = SkillDevSkill()
        result = skill.invoke("")
        assert "Skill Dev" in result
        assert "/skill-create" in result

    def test_invoke_unknown_command(self):
        skill = SkillDevSkill()
        result = skill.invoke("/unknown")
        assert "未知命令" in result

    def test_create_skill_no_name(self):
        skill = SkillDevSkill()
        result = skill.invoke("/skill-create")
        assert "错误" in result
        assert "请提供技能名称" in result

    def test_validate_skill_no_yaml(self, tmp_path, monkeypatch):
        # 切换到临时目录（没有 skill.yaml）
        monkeypatch.chdir(tmp_path)
        skill = SkillDevSkill()
        result = skill._validate_skill()
        assert "❌" in result
        assert "skill.yaml" in result


class TestSkillConfig:
    """Tests for SkillConfig."""

    def test_config_creation(self):
        config = SkillConfig(
            name="test-skill",
            description="Test skill",
            version="1.0.0",
            author="Test Author",
            entry_point="test:TestSkill",
            triggers=[SkillTrigger(pattern="/test", description="Test trigger")],
            args=[SkillArgument(name="arg1", type="string", required=True, description="Arg 1")],
        )
        assert config.name == "test-skill"
        assert config.version == "1.0.0"
        assert len(config.triggers) == 1
        assert len(config.args) == 1


def test_imports():
    """Test that all main classes can be imported."""
    from claude_code_skill_dev import BaseSkill, SkillDevSkill
    assert BaseSkill is not None
    assert SkillDevSkill is not None
