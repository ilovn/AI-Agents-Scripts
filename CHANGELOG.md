# 更新记录

## 0.3.1 — 2026-10-18

- 修复 Windows 下 CRLF 换行导致托管规则误报冲突的问题，并保持原有换行风格。
- 修正 Windows 路径断言，关闭矩阵 fail-fast 以便完整反馈各平台结果。

## 0.3.0 — 2026-10-18

- 新增 POSIX install.sh：公开 Git 仓库下载、固定版本、branch/tag/commit 选择、自动 init/upgrade、工具选择及 dry-run。
- 安装前检查 Python/Git 与版本匹配，临时 checkout 自动清理；安装继续沿用冲突保护与备份恢复。
- manifest/status 新增 Git 安装来源 repository/ref/commit；来源变化可恢复，本地安装明确标识来源未提供。
- 补充公开仓库发布文档和真实本地 Git 下载的端到端测试；默认排除本地备份及执行日志。

## 0.2.0 — 2026-10-18

- init/upgrade 自动安装四种任务入口：Claude Code / OpenCode 的项目级 /harness-* 命令，以及 Codex 的项目级 $harness-* Skills。
- 命令与技能文件纳入已有版本、哈希、冲突保护及备份恢复流程；doctor 展示具体入口和安装状态。
- Codex 采用 .agents/skills，不写入已弃用的用户级 custom prompts；TRAE 继续显式接入。

## 0.1.0 — 2026-10-18

- 新增存量项目安装、预览、升级、哈希检测、备份和可逆恢复。
- 新增 CLI / 项目 / schema / 任务版本识别与多项目扫描。
- 新增 Claude Code、Codex、OpenCode 规则入口和 TRAE 手动接入说明。
- 新增九种角色、四种工作流、持久化任务、依赖交接与结果回收。
- 新增真实质量门禁、有界 Loop、超时、停滞检测及交付前证据有效性检查。
