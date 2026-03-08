# 实验日志工具 - 安装指南

本指南详细介绍实验日志工具的安装步骤、配置方法和故障排查。

---

## 系统要求

### 必备条件

- **Claude Code** 已安装并配置
- **Python** 3.8 或更高版本
- **文件系统权限**：能够在项目目录下创建 `.experiment_logs/` 目录

### 依赖组件

实验日志工具依赖以下 Python 模块：
- `experiment_log` - 核心实验日志库
- `datetime` - 时间处理（标准库）
- `pathlib` - 路径处理（标准库）
- `re` - 正则表达式（标准库）

---

## 安装步骤

### 方法一：复制到用户技能目录（推荐）

将技能安装到 Claude Code 的用户技能目录，所有项目均可使用。

```bash
# 1. 确定 Claude Code 技能目录
# 通常是 ~/.claude/skills/
mkdir -p ~/.claude/skills/

# 2. 复制技能文件
cp -r skills/experiment-log ~/.claude/skills/

# 3. 验证文件结构
ls ~/.claude/skills/experiment-log/
# 应该看到：skill.yaml, experiment_log_skill.py, natural_language.py
```

### 方法二：复制到项目技能目录

仅在当前项目使用此技能。

```bash
# 在项目根目录执行
mkdir -p skills/
cp -r /path/to/experiment-log skills/
```

---

## 配置文件说明

### skill.yaml

```yaml
name: experiment-log
description: |
  实验日志自动整理工具 - 记录代码实验的问题探索过程

triggers:
  # 斜杠命令定义
  - pattern: "/explore"
    description: "开始新实验或查看当前实验"
    examples:
      - "/explore 解决模块A的性能问题"

  # 自然语言触发器
  - pattern: "启动实验*"
    description: "启动实验日志工具"
    natural_language:
      - "启动实验"
      - "开始记录实验"

config:
  auto_save: true                    # 自动保存开关
  base_dir: ".experiment_logs"       # 数据存储路径（项目根目录下）
  natural_language:
    enabled: true                    # 自然语言功能开关
    confidence_threshold: 0.7        # 识别置信度阈值（0-1）
```

### 配置项说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `auto_save` | 是否自动保存实验数据 | `true` |
| `base_dir` | 实验数据存储目录（相对于项目根目录） | `.experiment_logs` |
| `natural_language.enabled` | 是否启用自然语言识别 | `true` |
| `natural_language.confidence_threshold` | 自然语言识别置信度阈值，低于此值不处理 | `0.7` |

### 修改配置

编辑 `~/.claude/skills/experiment-log/skill.yaml`（或项目对应路径）。

**示例：更改存储路径**

```yaml
config:
  base_dir: "~/Documents/experiments"  # 改为文档目录
```

**示例：降低自然语言识别门槛**

```yaml
config:
  natural_language:
    enabled: true
    confidence_threshold: 0.6  # 更容易触发自然语言识别
```

---

## 验证安装

### 步骤 1：检查技能加载

在 Claude Code 中输入：

```
/status
```

**预期输出：**
```
No active experiments.
```

或如果已有实验：
```
Experiment Status
=================
ID: a1b2c3d4
...
```

### 步骤 2：测试基本功能

```
# 测试创建实验
/explore 测试安装

# 预期输出包含：
# ✅ Created new experiment
# Problem: 测试安装
```

### 步骤 3：测试自然语言

```
启动实验，验证自然语言功能
```

**预期输出：** 创建新实验的确认信息。

### 步骤 4：检查数据存储

```bash
ls .experiment_logs/
# 应该看到实验数据目录（以实验 ID 命名）
```

---

## 故障排查

### 问题 1：命令无响应

**现象：** 输入 `/status` 或 `/explore` 没有反应。

**排查步骤：**

1. 检查技能文件是否存在
   ```bash
   ls ~/.claude/skills/experiment-log/skill.yaml
   ```

2. 检查 Claude Code 是否正确加载技能
   - 重启 Claude Code
   - 查看 Claude Code 启动日志中是否有技能加载信息

3. 检查 Python 语法错误
   ```bash
   cd ~/.claude/skills/experiment-log
   python3 -m py_compile experiment_log_skill.py natural_language.py
   ```

---

### 问题 2：自然语言识别失败

**现象：** 输入 "启动实验，解决性能问题" 没有触发实验创建。

**排查步骤：**

1. 检查自然语言功能是否启用
   - 查看 `skill.yaml` 中 `natural_language.enabled` 是否为 `true`

2. 测试自然语言模块
   ```bash
   cd ~/.claude/skills/experiment-log
   python3 natural_language.py
   ```
   - 应该看到测试用例运行结果

3. 尝试更明确的触发词
   - "启动实验，..."
   - "开始记录实验，..."

4. 降低置信度阈值（如果识别过于严格）
   ```yaml
   config:
     natural_language:
       confidence_threshold: 0.6
   ```

---

### 问题 3：数据未保存

**现象：** 实验创建后，重启 Claude Code 找不到之前的实验。

**排查步骤：**

1. 检查自动保存设置
   ```yaml
   config:
     auto_save: true
   ```

2. 检查存储目录权限
   ```bash
   ls -la .experiment_logs/
   # 确保目录存在且有写权限
   ```

3. 检查存储路径配置
   - 如果修改了 `base_dir`，确保路径有效且可写

4. 手动验证保存功能
   ```
   /explore 测试保存
   /try 测试尝试
   /log-list
   ```
   - 应该能看到刚创建的实验

---

### 问题 4：导出失败

**现象：** `/log-export` 提示错误或没有生成文件。

**排查步骤：**

1. 检查是否有活动实验
   ```
   /status
   ```

2. 检查当前目录写入权限
   ```bash
   pwd
   touch test_write && rm test_write
   ```

3. 指定完整路径导出
   - 暂时切换到可写目录再导出

---

## 卸载

如需卸载实验日志工具：

```bash
# 删除技能目录
rm -rf ~/.claude/skills/experiment-log

# 可选：删除项目中的实验数据（注意备份）
rm -rf .experiment_logs/
```

---

## 获取帮助

如有问题：

1. 查看 Claude Code 输出日志
2. 检查 Python 错误追踪
3. 验证技能文件完整性
4. 参考 [README.md](./README.md) 和 [USAGE.md](./USAGE.md)
