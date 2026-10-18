# 仓库约定

本仓库提供可复制到存量项目的 Python 标准库工程 Harness，支持 Python 3.10+。

- 入口为 `harness.py` / `python -m harnesskit`；已安装项目入口为 `.harness/run.py`。
- 修改运行时、安装、升级或任务状态后运行 `python3 -m unittest discover -s tests -v`。
- 保留存量项目规则，所有受管文件改动必须经过冲突检查和备份。
- 不伪造供应商功能：角色模板、交接记录、原生子 Agent 和真正进程调度要明确区分。
- 不自动启用跳过权限/审批的工具选项。不要在测试中实际调用付费模型。
- 版本变更同步 `harnesskit/__init__.py`、`pyproject.toml` 和 CHANGELOG.md。
- CLI 输出 JSON；进度和诊断输出到 stderr；保持已安装运行时可独立运行。


<!-- ai-harness:begin -->
## AI Harness 0.3.0

开始工程任务时读取 `.harness/CONTRACT.md` 与 `.harness/project.md`。
任务入口：`python3 .harness/run.py --help`；版本检查：`python3 .harness/run.py status`。
按需读取 `.harness/workflows/` 和 `.harness/roles/`；遵循项目原有具体规则。
<!-- ai-harness:end -->
