# 公开 Git 仓库与一键安装

## 用户安装

前提：Python 3.10+、Git；使用 macOS、Linux 或 WSL 的 POSIX shell。curl 用于取得脚本，安装器用 Git 下载指定源。原生 Windows 可继续使用 Python 入口；PowerShell 安装器暂未实现。

公开仓库：[ilovn/AI-Agents-Scripts](https://github.com/ilovn/AI-Agents-Scripts)。安装到当前业务项目：

```bash
cd /path/to/business-project
curl -fsSL https://raw.githubusercontent.com/ilovn/AI-Agents-Scripts/v0.3.0/install.sh | sh
```

这条命令默认安装当前脚本对应的固定版本 v0.3.0。目标项目未初始化时执行 init，已初始化时执行 upgrade；不需要保留源码 checkout，不需要 sudo、pip 或修改 PATH。

install.sh 已预设 `DEFAULT_REPO=ilovn/AI-Agents-Scripts`，无需用户重复提供仓库地址。需要选择工具或目标项目时可附加参数：

```bash
curl -fsSL https://raw.githubusercontent.com/ilovn/AI-Agents-Scripts/v0.3.0/install.sh \
  | sh -s -- --project /path/to/project --tools codex,claude
```

也可以先下载审阅，再运行：

```bash
curl -fsSL https://raw.githubusercontent.com/ilovn/AI-Agents-Scripts/v0.3.0/install.sh -o /tmp/ai-harness-install.sh
sh /tmp/ai-harness-install.sh --repo ilovn/AI-Agents-Scripts --project /path/to/project --dry-run
sh /tmp/ai-harness-install.sh --repo ilovn/AI-Agents-Scripts --project /path/to/project --tools codex,claude
```

## 参数与版本

| 参数 | 行为 |
| --- | --- |
| `--repo OWNER/REPO` | GitHub 简写，也支持 HTTPS/SSH Git URL 或本地 Git 路径 |
| `--project DIR` | 安装到指定项目；默认调用脚本时所在目录 |
| `--version 0.3.0` | 获取 v0.3.0 tag，并验证代码报告的版本相符；允许 v 前缀 |
| `--ref main` | 显式选择分支、tag 或完整 commit；与 --version 互斥 |
| `--tools codex,claude` | 选择适配器；不指定时首次安装全部，升级保留已有选择 |
| `--mode auto/init/upgrade` | 默认自动判断，也可强制模式 |
| `--dry-run` | 获取源码并预览，不写目标项目 |
| `--replace-modified` | 显式覆盖有冲突的受管内容，保留备份；默认拒绝覆盖 |
| `--python /path/to/python3` | 指定 Python，也可设 HARNESS_PYTHON |

`HARNESS_REPO` 可作为 --repo 的默认值。预设的 DEFAULT_REPO 只用于省略参数；运行时参数优先。安装器需要 0.3.0+ 源码，旧版本仍可从其 checkout 使用 Python 入口安装。

例如安装到含空格的路径：

```bash
sh install.sh --repo ilovn/AI-Agents-Scripts --version v0.3.0 \
  --project '/path/to/my project' --tools codex,opencode
```

对于其他 Git 服务，提供完整 URL；脚本可以从对应服务的 raw 文件链接下载，不依赖 GitHub API 或 Release API。

## 升级与追溯

安装新版本时重新运行对应版本的脚本；auto 模式自动升级。默认保留冲突保护，不自动覆盖团队定制文件。

维护者发布 v0.4.0 后，用户可执行（此版本仅为说明格式，当前尚未发布）：

```bash
curl -fsSL https://raw.githubusercontent.com/ilovn/AI-Agents-Scripts/v0.4.0/install.sh \
  | sh -s -- --repo ilovn/AI-Agents-Scripts --version 0.4.0
```

开发测试也可以显式 `--ref main` 或使用完整 commit。分支和 tag 可能被移动；manifest 的 source.commit 记录本次实际检出的完整 commit，不把分支名当作唯一版本证据。需要不可变复现时使用完整 commit。

```bash
python3 .harness/run.py status
```

输出中包含：

```json
{
  "kit_version": "0.3.0",
  "project_version": "0.3.0",
  "source": {
    "repository": "https://github.com/ilovn/AI-Agents-Scripts.git",
    "ref": "v0.3.0",
    "commit": "完整的 Git commit 哈希"
  }
}
```

source 随 manifest 一起备份和恢复。直接从本地 checkout 使用 Python 入口升级时，source 为 null，表示此次安装没有由引导脚本提供 Git 来源，避免保留已不准确的远程来源。

安装器仅修改选定项目；下载 checkout 放在临时目录并在成功或失败后清理。普通信号中断会触发清理，SIGKILL 或掉电无法保证清理。下载失败、tag/源码版本不符或前置条件不满足时，目标项目不会被写入。脚本保留底层 Git/Python 的非零退出码，不能把网络失败当作成功。

## 维护者发布步骤

1. 保持 install.sh 的 DEFAULT_REPO 与公开仓库地址一致；fork 发布时改为自己的 OWNER/REPO，并更新 README 安装示例。
2. 更新 `harnesskit/__init__.py`、`pyproject.toml`、install.sh 的 INSTALLER_VERSION 与帮助文本、CHANGELOG.md 和安装文档。测试检查脚本版本与包版本一致。
3. 执行 `sh -n install.sh`、测试套件和 CI；shell 集成测试使用本地 Git 仓库，不会调用远程模型或依赖公开 GitHub 仓库。
4. 检查待发布文件；安装备份和运行日志已通过 .gitignore 排除，不将本机备份作为源码发布。
5. 按团队流程提交、推送，再创建并推送 `v0.3.0` tag。公开地址可访问后验证 raw 安装命令。
6. 发布后保留 tag，不静默重写相同版本。只调整分支开发版本不能替代正式版本发布。

分发使用 Git tag，不依赖 GitHub Release 资产。后续版本沿用上述发布流程；不要将尚未创建的版本 tag 当作可用版本。
