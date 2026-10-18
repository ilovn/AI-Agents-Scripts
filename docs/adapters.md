# 工具适配依据

核对日期：2026-10-18。适配只依赖项目级指令入口，不固定模型，也不修改账号或全局权限。

| 工具 | 官方依据 | 本项目策略 |
| --- | --- | --- |
| Codex | [工程工作流与 AGENTS.md](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex) | 用 AGENTS.md 导航到通用 Harness，角色按运行环境能力交接 |
| Claude Code | [项目记忆 CLAUDE.md](https://code.claude.com/docs/en/memory)、[自定义 subagents](https://code.claude.com/docs/en/sub-agents) | CLAUDE.md 入口 + .claude/agents/ 下含 name/description 的 Markdown |
| OpenCode | [Rules](https://opencode.ai/docs/rules/)、[Agents](https://opencode.ai/docs/agents/) | AGENTS.md 入口 + .opencode/agents/ 下 mode: subagent 的 Markdown |
| TRAE | [官方文档入口](https://docs.trae.ai/) | 本次未能取得可验证的规则路径说明，采用 IDE 显式导入；不保证特定隐藏目录自动加载 |

工具是否已安装由 doctor 检查 PATH；它不会登录、调用模型或证明当前工具版本完整支持某项功能。原生适配文件遵循所列文档格式，尚未对每个工具和 IDE 版本做端到端模型调用测试。

安装后可让工具说明其读取的工程契约与当前任务路径，以验证上下文接入。Claude Code / OpenCode 的自定义 Agent 权限继承所在工具配置；需要只读隔离的角色，应通过工具自身权限配置进一步约束。

## 可选的无头执行

Loop 原生接受 argv 和 stdin，因此无需另外安装本工具的厂商 SDK：

- [Codex 非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)：`codex exec --sandbox workspace-write -`，完整提示从 stdin 进入。
- [Claude Code 程序调用](https://code.claude.com/docs/en/headless)：`claude -p`，非交互模式接受 stdin。
- [OpenCode CLI](https://opencode.ai/docs/cli/)：`opencode run <message>`，消息中引用 `{prompt}` 对应的提示词文件。

这些模式使用各工具自己的账号、模型、仓库信任和权限配置。默认不跳过工具检查，未通过授权时需要按工具自身流程处理。没有已验证的 TRAE 无头命令适配。

## 安装任务命令与技能（0.2.0 起）

- Claude Code：`.claude/commands/harness-<类型>.md`，通过 `/harness-<类型> 任务描述` 调用；使用 `$ARGUMENTS` 接收描述。官方 [Skills / 自定义命令](https://code.claude.com/docs/en/slash-commands) 说明 commands 文件仍受支持。
- OpenCode：`.opencode/commands/harness-<类型>.md`，同样以 `/harness-<类型> 任务描述` 调用，使用 `$ARGUMENTS`；依据 [Commands](https://opencode.ai/docs/commands/)。
- Codex：`.agents/skills/harness-<类型>/SKILL.md`，按 [Build skills](https://learn.chatgpt.com/docs/build-skills) 的项目级发现规则安装，以 `$harness-<类型> 任务描述` 或技能选择器调用。需求直接来自用户消息，不依赖 `$ARGUMENTS` 替换。
- Codex 的 [Custom Prompts](https://learn.chatgpt.com/docs/custom-prompts) 已弃用，且使用用户级 `~/.codex/prompts`，不能把 `.codex/prompts` 当作项目级发现路径。init 不写用户主目录。
- TRAE：当前未验证项目级命令的注册协议，继续使用显式规则和任务消息，不将 Claude/OpenCode 的路径套用到 TRAE。

类型为 quick、complex、bugfix、research。重启 CLI 会话后检查命令/技能选择器；如果找不到，再用 doctor 检查对应文件是否安装且未损坏。工具菜单发现和真实模型执行仍需用户在自身 CLI 环境验证；单元测试不调用模型。

这些入口在当前 Agent 会话创建/续接任务并执行工作流，包含基于检查结果的修复指导；没有自动启动额外模型进程。强制轮数、超时和进程回收仍由独立的 harness loop 命令提供。
