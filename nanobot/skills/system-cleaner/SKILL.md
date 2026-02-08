# 系统清理技能 (System Cleaner Skill) 🧹

此技能使 Nanobot 能够主动分析和清理系统垃圾、缓存以及冗余的开发文件。

## 指令 (Commands)

### 📊 `analyze-junk` (分析垃圾)
深度扫描常见的垃圾位置，并报告具体、可执行的发现。
```bash
# 扫描废纸篓、缓存和日志
echo "--- 废纸篓 (Trash) ---" && du -sh ~/.Trash
echo "--- 用户缓存 (User Caches) ---" && du -sh ~/Library/Caches
echo "--- 用户日志 (User Logs) ---" && du -sh ~/Library/Logs

# 扫描开发垃圾
echo "--- venv/node_modules 扫描 ---"
find ~/Downloads -name "node_modules" -type d -prune -exec du -sh {} + 2>/dev/null
find ~/Downloads -name ".venv" -type d -prune -exec du -sh {} + 2>/dev/null
find ~/Downloads -name "venv" -type d -prune -exec du -sh {} + 2>/dev/null

# 扫描大文件下载
echo "--- 大文件下载 (>100M) ---"
find ~/Downloads -type f -size +100M -exec ls -lh {} +
```

### 🧹 `clean-all-safe` (安全清理所有)
清理可以安全删除的缓存和日志。
```bash
rm -rf ~/Library/Caches/*
rm -rf ~/Library/Logs/*
rm -rf ~/.Trash/*
brew cleanup
```

## 指导原则 (Guiding Principles)
1.  **不要总结，要分析**: 给老板具体的路径和大小。
2.  **安全第一**: 未经确认，切勿删除用户文档或未知文件夹。
3.  **主动建议**: 如果发现一个几个月没动过的 `.venv`，建议删除它。
