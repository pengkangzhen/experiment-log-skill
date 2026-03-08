# 实验日志工具 (Experiment Log)

**自动捕获** Claude Code 对话内容，智能识别实验意图并记录探索过程，形成可追溯的树状实验日志。

---

## 核心特性

- **自动捕获**：后台守护进程监控对话历史，无需手动触发
- **意图识别**：自动识别新问题、尝试、成功、失败等意图
- **树状记录**：自动构建实验探索的树状结构
- **双模式**：支持自动模式和手动模式

---

## 快速开始

### 自动模式（推荐）

```bash
# 1. 启动后台守护进程
exp-log daemon start

# 2. 正常与 Claude 对话，自动记录

# 3. 查看实验进度
exp-log tree
# 或在 Claude 中：/tree

# 4. 导出报告
exp-log export
# 或在 Claude 中：/log-export
```

### 手动模式

```bash
# 在 Claude Code 中使用斜杠命令
/explore 解决 API 响应慢的问题
/try 添加 Redis 缓存
/result success 响应时间从 2s 降到 50ms
/tree
/log-export
```

---

## 安装方法

### 1. 安装 CLI 工具

```bash
# 进入项目目录
cd claude-code-skill-dev

# 安装包（开发模式）
pip install -e .
```

### 2. 复制技能文件

```bash
cp -r skills/experiment-log ~/.claude/skills/
```

### 3. 验证安装

```bash
exp-log --help
exp-log daemon status
```

---

## 自动识别的意图

| 意图类型 | 触发词示例 | 自动操作 |
|---------|-----------|---------|
| 新实验 | "帮我解决..."、"优化..." | 创建新实验 |
| 尝试 | "试试..."、"用...方法" | 添加尝试节点 |
| 成功 | "搞定了"、"成功了" | 标记成功 |
| 失败 | "不行"、"报错" | 标记失败 |
| 放弃 | "算了"、"放弃" | 标记放弃 |

---

## 命令参考

### CLI 命令

```bash
exp-log start <problem>      # 创建新实验
exp-log try <title>          # 添加尝试
exp-log result <status>      # 记录结果
exp-log tree                 # 查看实验树
exp-log list                 # 列出所有实验
exp-log export [id]          # 导出报告

# 守护进程管理
exp-log daemon start         # 启动自动记录
exp-log daemon stop          # 停止自动记录
exp-log daemon status        # 查看状态
```

### 斜杠命令

| 命令 | 用途 |
|------|------|
| `/explore [问题]` | 启动新实验 |
| `/try <描述>` | 记录尝试 |
| `/result <状态>` | 记录结果 |
| `/tree` | 查看实验树 |
| `/log-export` | 导出报告 |

---

## 配置说明

数据存储在**项目根目录**下的 `.experiment_logs/` 目录。

项目根目录通过查找以下标记文件自动识别：
- `.git`
- `pyproject.toml`
- `setup.py`
- `Cargo.toml`
- `go.mod`
- `package.json`

守护进程配置：
```bash
exp-log daemon start --interval 2.0 --confidence 0.6
```

---

## 下一步

- 查看 [USAGE.md](./USAGE.md) 了解完整使用指南
- 查看 [INSTALL.md](./INSTALL.md) 了解详细安装步骤
