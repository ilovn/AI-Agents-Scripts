# Loop worker 协议与可运行示例

## worker 契约

- CLI 通过 JSON 数组传入 worker argv，使用 subprocess 直接执行，不进行隐式 shell 展开。
- 工作目录为目标项目根；stdin 是 UTF-8 提示词全文；argv 中 `{prompt}` 替换为该轮 prompt.md 的绝对路径，`{task}` 替换为任务 ID。
- worker 按提示完成一轮工作，正常退出且返回 0 后才运行质量门禁。失败必须保留真实非零退出码。
- worker stdout/stderr 合并到 worker.log。不要在日志中输出密钥。
- 可直接通过 worker argv 使用 Claude Code、Codex、OpenCode，具体命令见 README；也可桥接其他可脚本化工具。先用实际版本的官方帮助核对无头输入和权限行为。
- TRAE IDE 可使用手工 Observe/Plan/Act/Verify 流程：在 IDE 完成一轮，再执行 check，将日志反馈给下一轮；本工具不内置 TRAE 无头进程启动。

模型调用和自动批量操作可能产生费用，是否调用由项目传入的 worker 决定。本工具不自带供应商凭证或后台定时任务。

## 本地演示：无模型调用的 Bug 修复循环

该演示验证框架的真实执行链路；worker 是固定修复程序，不是 AI。建议在临时项目中操作。

```bash
python3 /path/to/ai-agents-scripts/harness.py --project /tmp/harness-demo init --tools codex
cd /tmp/harness-demo
python3 .harness/run.py task new bugfix "修复示例加法" --id addition --accept "add(1, 2) 等于 3"
```

创建 `calc.py`：

```python
def add(a, b):
    return a - b
```

将 `.harness/config.json` 的 gates 设为：

```json
{
  "schema_version": 1,
  "gates": [
    {"name": "regression", "argv": ["python3", "-B", "-c", "from calc import add; assert add(1, 2) == 3"], "timeout_seconds": 10}
  ],
  "loop": {"max_rounds": 3, "timeout_seconds": 10, "stagnation_rounds": 1}
}
```

创建 `repair.py`：

```python
from pathlib import Path
import sys

prompt = Path(sys.argv[1]).read_text(encoding="utf-8")
assert "addition" in prompt
Path("calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
```

运行失败基线、循环和业务验收：

```bash
python3 .harness/run.py check addition  # 预期返回 1
python3 .harness/run.py loop addition --worker '["python3", "repair.py", "{prompt}"]'
python3 .harness/run.py task finish addition --summary "已验证修复前失败、修复后通过；示例加法符合验收"
```

查看 `.harness/tasks/addition/runs/`：每轮含 prompt.md、worker.log、worker.json、gate-N.log、check.json。第一次 check 的失败证据保留，循环第一轮的 prompt 包含失败输出。检查通过时 Loop 返回 0，但只有 finish 后状态才是 done。

## 退出码与续接

| 退出码 | 含义 |
| --- | --- |
| 0 | 命令成功；Loop 仅表示门禁通过 |
| 1 | 门禁失败、Loop 未通过、受管内容 drift，或 scan 包含异常项目 |
| 2 | 参数之外的配置、状态、文件或冲突错误；argparse 参数错误也返回 2 |
| 130 | 用户中断 |

输出为 JSON，Loop 进度和错误写 stderr，适合被其他脚本调用。修复门禁、依赖或环境后，重新执行 check / loop；每次使用独立 run ID，不覆盖历史日志。task accept 修改验收会使既有通过记录失效。
