# 版本管理、发布和回滚

## 四个版本概念

1. CLI `--version`：当前运行的脚本版本。
2. manifest `kit_version`：此项目最后安装/升级的版本。
3. manifest/config/task `schema_version`：机器可读文件格式；当前为 1。
4. task `kit_version`：任务创建时应用的工程协议版本，便于追溯。

SemVer：修复兼容问题升 patch，新增兼容能力升 minor，破坏行为或格式变化升 major；0.x 阶段可能仍有接口调整，发布记录必须明确。禁止通过重新发布相同版本静默更换内容。install.sh 可从公开 Git 仓库获取固定版本并自动判断 init/upgrade；也支持下载/检出某版本工具之后显式 upgrade。

`harnesskit/__init__.py`、`pyproject.toml` 和 install.sh 的 INSTALLER_VERSION 必须一致，测试校验这一要求。升级只接受 x.y.z 正式版本，不接受 prerelease 格式。未知 schema 不猜测迁移，明确报错；未来格式变更应增加独立、可测试的迁移步骤。

## 发布流程

1. 更新包与安装脚本的版本字段、帮助文本及 CHANGELOG.md，说明兼容性、迁移和适配变化。
2. 执行测试矩阵和包安装检查；在临时存量项目安装旧版本，使用新版本预览、升级、检查并恢复。
3. 审查 diff，通过团队既有流程提交到 Git。
4. 创建对应 `vX.Y.Z` tag，按团队渠道分发该 tag 的源码或构建产物。
5. 在业务项目用新发布的安装器执行 upgrade；提交业务项目 manifest 和 runtime 的改动，使工程能力版本随业务代码一起可追溯。

源码仓库为 [ilovn/AI-Agents-Scripts](https://github.com/ilovn/AI-Agents-Scripts)，通过 Git tag 与 install.sh 分发，尚未上传 PyPI。当前版本是 0.3.1，初始版本为 0.1.0。

## 升级与回滚边界

受管普通文件按完整字节计算哈希；入口按 ai-harness 标记区块计算哈希，外部内容可自由维护。已删掉的受管文件也视为本地变更。显式 --replace-modified 会覆盖受管内容并先备份，配置、上下文和任务继续保留。

备份包含每个改动文件的旧内容和预期新内容哈希。restore 在全部路径确认后再恢复；若文件已经被后续修改则拒绝整个操作。恢复会生成反向备份，可以撤销恢复。若恢复的是初次安装，run.py 可能被删除；再次操作请使用外部 checkout 的 harness.py。

备份不是 Git 提交，也不是签名或灾备。多文件操作被强杀时可能部分写入；restore 可处理仍为旧内容或已变为本次新内容的文件，但遇到第三种内容会停止。操作锁残留需要确认进程退出后人工清理。

升级暂时只增加/保留适配器，不支持移除某一种工具；不要通过手改 manifest 伪装升级成功。模板本地定制会触发 drift；优先把长期定制放在项目自有上下文和角色文件中。

所有时间戳以 UTC ISO-8601 保存，便于跨时区排序；发布记录中的日期按项目维护者所在时区填写。

通过 install.sh 安装时，manifest.source 记录 repository/ref/commit，并参与备份恢复；本地 Python 安装 source 为 null。完整说明见 [一键安装](installation.md)。
