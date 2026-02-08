---
name: tmux
description: 通过发送按键和抓取窗格输出来远程控制用于交互式 CLI 的 tmux 会话。
metadata: {"nanobot":{"emoji":"🧵","os":["darwin","linux"],"requires":{"bins":["tmux"]}}}
---

# tmux 技能 (tmux Skill)

仅在需要交互式 TTY 时使用 tmux。对于长时间运行的非交互式任务，首选 exec 后台模式。

## 快速开始 (隔离 socket, exec 工具)

```bash
SOCKET_DIR="${NANOBOT_TMUX_SOCKET_DIR:-${TMPDIR:-/tmp}/nanobot-tmux-sockets}"
mkdir -p "$SOCKET_DIR"
SOCKET="$SOCKET_DIR/nanobot.sock"
SESSION=nanobot-python

tmux -S "$SOCKET" new -d -s "$SESSION" -n shell
tmux -S "$SOCKET" send-keys -t "$SESSION":0.0 -- 'PYTHON_BASIC_REPL=1 python3 -q' Enter
tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -200
```

启动会话后，始终打印监控命令:

```
监控指令:
  tmux -S "$SOCKET" attach -t "$SESSION"
  tmux -S "$SOCKET" capture-pane -p -J -t "$SESSION":0.0 -S -200
```

## Socket 约定

- 使用 `NANOBOT_TMUX_SOCKET_DIR` 环境变量。
- 默认 socket 路径: `"$NANOBOT_TMUX_SOCKET_DIR/nanobot.sock"`.

## 目标窗格和命名

- 目标格式: `session:window.pane` (默认为 `:0.0`).
- 保持名称简短；避免空格。
- 检查: `tmux -S "$SOCKET" list-sessions`, `tmux -S "$SOCKET" list-panes -a`.

## 查找会话

- 列出 socket 上的会话: `{baseDir}/scripts/find-sessions.sh -S "$SOCKET"`.
- 扫描所有 sockets: `{baseDir}/scripts/find-sessions.sh --all` (使用 `NANOBOT_TMUX_SOCKET_DIR`).

## 安全发送输入

- 首选字面发送: `tmux -S "$SOCKET" send-keys -t target -l -- "$cmd"`.
- 控制键: `tmux -S "$SOCKET" send-keys -t target C-c`.

## 观察输出

- 捕获最近历史: `tmux -S "$SOCKET" capture-pane -p -J -t target -S -200`.
- 等待提示符: `{baseDir}/scripts/wait-for-text.sh -t session:0.0 -p 'pattern'`.
- Attach 是可以的；使用 `Ctrl+b d` detach。

## 衍生进程

- 对于 python REPLs, 设置 `PYTHON_BASIC_REPL=1` (非 basic REPL 会破坏 send-keys 流程).

## Windows / WSL

- macOS/Linux 支持 tmux。在 Windows 上，使用 WSL 并在 WSL 内安装 tmux。
- 此技能限制在 `darwin`/`linux` 并且需要 PATH 上有 `tmux`。

## 编排编码智能体 (Codex, Claude Code)

tmux 擅长并行运行多个编码智能体:

```bash
SOCKET="${TMPDIR:-/tmp}/codex-army.sock"

# 创建多个会话
for i in 1 2 3 4 5; do
  tmux -S "$SOCKET" new-session -d -s "agent-$i"
done

# 在不同工作目录启动智能体
tmux -S "$SOCKET" send-keys -t agent-1 "cd /tmp/project1 && codex --yolo 'Fix bug X'" Enter
tmux -S "$SOCKET" send-keys -t agent-2 "cd /tmp/project2 && codex --yolo 'Fix bug Y'" Enter

# 轮询完成状态 (检查是否返回提示符)
for sess in agent-1 agent-2; do
  if tmux -S "$SOCKET" capture-pane -p -t "$sess" -S -3 | grep -q "❯"; then
    echo "$sess: DONE"
  else
    echo "$sess: Running..."
  fi
done

# 获取完成会话的完整输出
tmux -S "$SOCKET" capture-pane -p -t agent-1 -S -500
```

**提示:**
- 为并行修复使用单独的 git worktrees (无分支冲突)
- 在新克隆中运行 codex 前先 `pnpm install`
- 检查 shell 提示符 (`❯` 或 `$`) 以检测完成
- Codex 需要 `--yolo` 或 `--full-auto` 进行非交互式修复

## 清理

- 杀死会话: `tmux -S "$SOCKET" kill-session -t "$SESSION"`.
- 杀死 socket 上的所有会话: `tmux -S "$SOCKET" list-sessions -F '#{session_name}' | xargs -r -n1 tmux -S "$SOCKET" kill-session -t`.
- 移除私有 socket 上的所有内容: `tmux -S "$SOCKET" kill-server`.

## 助手: wait-for-text.sh

`{baseDir}/scripts/wait-for-text.sh` 轮询窗格以匹配正则表达式（或固定字符串）并带有超时。

```bash
{baseDir}/scripts/wait-for-text.sh -t session:0.0 -p 'pattern' [-F] [-T 20] [-i 0.5] [-l 2000]
```

- `-t`/`--target` 目标窗格 (必需)
- `-p`/`--pattern` 要匹配的正则 (必需); 添加 `-F` 用于固定字符串
- `-T` 超时秒数 (整数, 默认 15)
- `-i` 轮询间隔秒数 (默认 0.5)
- `-l` 搜索的历史行数 (整数, 默认 1000)
