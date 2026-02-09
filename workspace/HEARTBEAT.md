# 心跳任务 (Auto-Maintenance) 🐈

此文件由 Nanobot 定期读取。是否自动执行取决于是否启用 Heartbeat/Cron。

## 秘书日常 (Automatic Routines)
- [ ] **每日记忆整理**: 每 24 小时检查一次 `memory/MEMORY.md`，精炼日记。
- [ ] **系统健康自检**: 每 12 小时运行 `nanobot doctor`，检查 `audit.log` 中的异常记录。
- [ ] **运行环境审计**: 检查最近的 `gateway.log`（位于 `NANOBOT_HOME`）。若日志文件超过 **50MB**，执行压缩归档后清理原文件，严禁在此阈值下直接删除。

## 待办任务 (Active Boss Requests)
<!-- 在此行下方添加老板临时交办的定期检查任务 -->

---
## 已完成 (Completed History)
- [x] **系统健康巡检**: (2026-02-08 23:36) 运行 `nanobot doctor`，已修复 Playwright 依赖。🐾
