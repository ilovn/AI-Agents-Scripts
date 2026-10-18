# AI Harness Kit

面向 Claude Code、Codex、OpenCode、TRAE 的项目研发工程工具。通过一套轻量 Harness（上下文、规则、角色、工作流、验收门禁）和有界 Loop（执行、验证、反馈、再执行），让新项目和存量项目获得可续接、可审查的交付流程。

当前版本 **0.3.0**，Python **3.10+**，运行时只使用标准库，无需 API Key 或安装第三方 Python 依赖。AI 模型与 CLI 由项目自行配置。

## 1. 给存量项目快速建立能力

在业务项目目录中，一键安装 [ilovn/AI-Agents-Scripts](https://github.com/ilovn/AI-Agents-Scripts) 的固定版本：

```bash
curl -fsSL https://raw.githubusercontent.com/ilovn/AI-Agents-Scripts/v0.3.0/install.sh | sh
```

脚本默认获取固定版本，自动执行 init 或 upgrade，安装项目规则、四类命令/技能和独立运行时；无需 sudo 或 pip。需要 Python 3.10+ 和 Git。安装源已预设为公开仓库，也可通过 `--repo` 显式选择其他 Git 仓库。

支持 `--version 0.3.0`、`--ref <commit>`、`--project DIR`、`--tools codex,claude` 与 `--dry-run`；项目 status 可查看来源仓库、ref 和实际 commit。完整参数及发布步骤见 [一键安装说明](docs/installation.md)。

已下载源码时，在本仓库执行，目标可以是已有 Git 项目，也可以是普通目录：

```bash
# 先查看将写入哪些文件，不修改项目
python3 harness.py --project /path/to/project init --dry-run

# 一次接入全部工具；也可 --tools codex claude 按需选择
python3 harness.py --project /path/to/project init
```

安装只新增 `.harness/` 和选定工具的入口。已有 `AGENTS.md`、`CLAUDE.md` 保留原有文本，追加受管标记区块；同名角色文件或受管区块存在冲突时，整个操作会在写入前停止。不会自动安装 AI CLI、猜测项目测试命令或修改工具权限。

init 完成后，进入目标项目重新启动 CLI 会话，即可用安装的入口开始任务：

| 任务 | Claude Code / OpenCode | Codex |
| --- | --- | --- |
| 快速研发 | `/harness-quick 给列表增加搜索` | `$harness-quick 给列表增加搜索` |
| 复杂场景 | `/harness-complex 重构订单状态机` | `$harness-complex 重构订单状态机` |
| Bug 修复 | `/harness-bugfix 修复重复扣款` | `$harness-bugfix 修复重复扣款` |
| 产品调研 | `/harness-research 调研知识库产品` | `$harness-research 调研知识库产品` |

这些指令输入到 **Agent 会话**，不是系统 shell。Agent 会创建任务并立即执行工作流，无需提前手工 task new；用户没有提供任务目标时会先询问目标。已有任务可在描述中明确“继续任务 ID”。命令是指令模板，执行仍遵循当前工具授权；检查通过后由负责人确认业务验收。

Claude Code 使用 `.claude/commands/harness-*.md`，OpenCode 使用 `.opencode/commands/harness-*.md`。Codex 使用 `.agents/skills/harness-*/SKILL.md`，以 `$技能名` 或技能选择器调用，不承诺 `/harness-*` 语法；已弃用的用户级 `/prompts:*` 不在 init 范围。TRAE 保持显式 Rules 接入，不生成未经验证的命令注册文件。

已初始化的 0.1.0 项目执行新版 `harness.py --project /path/to/project upgrade` 即可补装入口；不要用项目中的旧 runtime 期待获取新版本。`doctor` 的 task_entrypoints 会列出具体命令与安装状态。入口文件与角色文件一样受哈希检测、冲突保护和备份恢复管理。

也可以用脚本显式创建任务。在**目标项目**中运行：

```bash
python3 .harness/run.py status
python3 .harness/run.py doctor
python3 .harness/run.py task new quick "为列表增加筛选" --id filter \
  --accept "筛选结果符合输入条件，清空后恢复全部结果"
```

把这段话交给当前 coding agent：

> 读取 `.harness/CONTRACT.md`、`.harness/project.md` 和 `.harness/tasks/filter/brief.md`，调查项目现状，完成任务并验证。按需使用角色协助，将发现和续接信息写入 context.md。交付前运行质量门禁并核验验收标准。

首次接入请填写 `.harness/project.md`，在 `.harness/config.json` 配置项目真实的测试、lint、构建命令。缺少门禁时，工具会拒绝将检查判为通过。

也支持安装为命令：`python3 -m pip install /path/to/ai-agents-scripts`，随后使用 `ai-harness --project /path/to/project status`。无需 pip 时，始终可用 `python3 /path/to/ai-agents-scripts/harness.py ...`。

## 2. 工具适配与角色协作

| 工具 | 安装的入口 | 子 Agent 使用方式 |
| --- | --- | --- |
| Claude Code | `CLAUDE.md`、`.claude/commands/harness-*.md`、`.claude/agents/harness-*.md` | 工具加载项目级自定义 subagent，主会话按交接文件分派 |
| Codex | `AGENTS.md`、`.agents/skills/harness-*/SKILL.md` | 通用角色 + handoff；当前运行环境支持并获授权时可由主 Agent 原生分派，否则独立会话或串行执行 |
| OpenCode | `AGENTS.md`、`.opencode/commands/harness-*.md`、`.opencode/agents/harness-*.md` | 项目级 `mode: subagent`；例如 `@harness-qa` |
| TRAE | `.harness/adapters/trae.md` | 在 IDE 项目 Rules 显式加入规则；自定义 Agent、独立会话或串行执行 |

九种角色：研发负责人、产品经理、调研、架构、前端、后端、测试、代码审查、交付运维。

本工具建立角色契约和交接记录；`delegate` **只生成交接，不启动 Agent 进程**。原生子 Agent 的可用性、权限、模型和并行能力由具体工具版本及会话环境决定。TRAE 的规则路径没有在本工具中做自动加载保证。

```bash
python3 .harness/run.py task delegate filter frontend "实现筛选交互" --scope "src/components/Filter.tsx"
# 输出子任务 ID，例如 frontend-a1b2c3d4
python3 .harness/run.py task delegate filter qa "验证筛选" \
  --scope "tests/filter，其他目录只读" --depends-on frontend-a1b2c3d4
```

将生成的 `subtasks/<id>/handoff.md` 交给对应 Agent。主 Agent 检查非空 `result.md` 后执行：

```bash
python3 .harness/run.py task collect filter frontend-a1b2c3d4
```

先收集依赖，再收集后续任务。实现角色在不同 worktree 或不重叠目录中工作，主 Agent 负责合并、审查和最终交付。范围与只读约束是协作约定，不能代替工具自身的权限隔离。

## 3. 四种任务入口

| 类型 | 场景 | 工作流重点 |
| --- | --- | --- |
| `quick` | 小功能、快速启动 | 最小目标 → 实现 → 相关检查 → 交付 |
| `complex` | 跨模块、长周期、复杂场景 | 需求 → 架构/计划 → 依赖拆解 → 阶段集成 → 审查/回滚 |
| `bugfix` | Bug 修复、回归处理 | 复现 → 根因 → 最小修复 → 回归验证 |
| `research` | 产品、竞品、技术调研 | 决策问题 → 一手来源 → 事实/推断 → 对比与建议 |

```bash
python3 .harness/run.py task new complex "重构订单状态机" --id orders --accept "历史订单保持兼容"
python3 .harness/run.py task new bugfix "修复重复扣款" --id payment --accept "重复请求只扣款一次"
python3 .harness/run.py task new research "调研知识库产品" --id kb --accept "提供带日期与来源的比较和建议"
python3 .harness/run.py task list
python3 .harness/run.py task show orders
```

每个任务持久化 `brief.md`、`plan.md`、`context.md`、`task.json`、子任务结果和运行日志。换工具或会话后读取同一目录即可继续。调研任务也需要为交付物配置可执行检查；来源真实性、建议质量仍由负责人核验。

## 4. 质量门禁与 Loop

编辑目标项目 `.harness/config.json`，每条命令使用 **argv 数组**，工作目录固定为项目根目录：

```json
{
  "schema_version": 1,
  "gates": [
    {"name": "test", "argv": ["npm", "test", "--", "--run"], "timeout_seconds": 180},
    {"name": "build", "argv": ["npm", "run", "build"], "timeout_seconds": 180}
  ],
  "loop": {"max_rounds": 5, "timeout_seconds": 300, "stagnation_rounds": 2}
}
```

以上 npm 命令只是格式示例，必须替换为项目已验证的命令。Windows 上按实际执行文件使用 `npm.cmd` 或 `python`；需要 shell 内建命令时必须显式指定 shell argv，自行承担其命令解释行为。

手动验证与交付：

```bash
python3 .harness/run.py check filter
# 人工核验业务验收、交付物及子任务结果后：
python3 .harness/run.py task finish filter --summary "筛选交互已完成；相关测试和构建通过，已核验清空及空结果行为"
```

循环模式接受任意兼容 worker，提示词通过 stdin 传入，同时支持 `{prompt}` 绝对文件路径和 `{task}` ID 占位符：

```bash
python3 .harness/run.py loop filter \
  --worker '["python3", "scripts/agent_worker.py", "{prompt}"]' \
  --rounds 5 --timeout 300
```

如果工具已安装、登录并配置好权限，可以直接传入它的命令，无需桥接脚本：

```bash
# Codex：显式使用 workspace-write；不关闭沙箱或绕过权限规则
python3 .harness/run.py loop filter --worker '["codex", "exec", "--sandbox", "workspace-write", "-"]'
# Claude Code：读取 stdin；沿用当前工具的授权策略
python3 .harness/run.py loop filter --worker '["claude", "-p"]'
# OpenCode：指示它读取本轮提示词文件
python3 .harness/run.py loop filter --worker '["opencode", "run", "读取 {prompt}，按其中工程任务完成一轮工作"]'
```

命令格式依据 [Codex 非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)、[Claude Code 非交互模式](https://code.claude.com/docs/en/headless) 和 [OpenCode CLI](https://opencode.ai/docs/cli/)。请用已安装版本的帮助核对支持情况；本仓库测试不实际调用付费模型。需要定制模型、远程执行或结果转换时，才使用项目自己的 `agent_worker.py` 桥接脚本。工具未获得所需权限时应先按工具流程配置授权，本工具不添加跳过审批参数。接口和不调用模型的可运行示例见 [Loop 使用说明](docs/loop.md)。

每轮执行 `worker → 全部门禁 → 记录证据 → 反馈下轮`。检查通过后状态为 `checks_passed`，仍需 `task finish` 确认业务验收。失败会按 worker 失败/超时、停滞或轮数耗尽停止，状态为 `blocked`；修复条件后可再次运行。

## 5. 版本识别、升级与恢复

```bash
# 已安装到目标项目的版本与受管文件状态
python3 .harness/run.py status

# 使用新版本工具升级；项目中的旧 runtime 不会自行下载新版本
python3 /path/to/new-kit/harness.py --project /path/to/project upgrade --dry-run
python3 /path/to/new-kit/harness.py --project /path/to/project upgrade

# 一次识别多个指定项目
python3 harness.py scan /path/to/project-a /path/to/project-b

# 如确实需要覆盖本地受管内容，显式选择，并记录输出 backup_id
python3 harness.py --project /path/to/project upgrade --replace-modified
python3 .harness/run.py restore BACKUP_ID
```

- `.harness/manifest.json` 记录 `kit_version`、`schema_version`、工具列表及每个受管内容的 SHA-256；一键安装额外记录 source.repository/ref/commit。
- `status` 同时展示运行 CLI 的版本和项目应用版本；缺失/修改文件会报告 drift，并返回非零退出码。
- `task.json` 记录创建时的 kit 版本，任务升级后仍保留来源版本。
- 原有规则标记以外的改动、`project.md`、`config.json`、任务和证据由项目维护，升级保留。
- 受管内容发生本地修改时默认拒绝升级；自定义角色建议放在团队自有文件中再从上下文引用。
- 安装和升级先保存 `.harness/backups/<id>.json`，恢复前检查文件是否有后续变化；恢复本身也创建可撤销备份。
- 禁止降级；未知 schema 直接拒绝。当前只支持 schema 1，不声称支持尚未定义的迁移。
- 同版本升级幂等；不自动移除已安装的适配器。详见 [版本与发布规范](docs/versioning.md)。

## 项目内结构

```text
AGENTS.md / CLAUDE.md             按需追加的工具入口
.claude/agents/harness-*.md       Claude 角色适配（按需）
.opencode/agents/harness-*.md     OpenCode 角色适配（按需）
.claude/commands/harness-*.md     Claude Code 斜杠命令（按需）
.opencode/commands/harness-*.md   OpenCode 斜杠命令（按需）
.agents/skills/harness-*/SKILL.md Codex 项目级技能（按需）
.harness/
  manifest.json                  项目应用版本及受管哈希
  run.py + runtime/              随项目携带的独立运行时
  CONTRACT.md                    通用工程契约
  project.md + config.json       团队维护的上下文与门禁
  roles/ + workflows/            角色与场景协议
  adapters/trae.md               TRAE 显式接入说明（按需）
  tasks/<id>/                    任务、上下文、交接、证据和交付
  backups/                       安装/升级变更前快照
```

建议把入口、manifest、runtime、角色、工作流和团队配置提交到业务项目 Git。任务与运行日志按团队敏感信息政策管理；备份含原文件内容，不应无审查公开发布。检查 SHA-256 是完整性/修改检测，不是供应链签名或对抗恶意 Agent 的安全边界。

## 本仓库验证

```bash
sh -n install.sh
python3 -m unittest discover -s tests -v
python3 harness.py --help
```

CI 配置了 Linux、macOS、Windows × Python 3.10/3.12/3.13 的矩阵；本地验证结果不能替代尚未运行的 CI。实现架构和边界见 [工程设计](docs/design.md)，适配依据见 [官方资料](docs/adapters.md)。
