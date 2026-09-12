# 贡献指南

[English](CONTRIBUTING.md) | 简体中文

欢迎改进 raradio 的工作流、后端适配、文档和评测。项目处于 Alpha 阶段；涉及项目文件格式、状态机或公开接口的改动，请先说明使用场景及迁移影响。

## 开发环境

核心开发需要 Python 3.11+ 和提供 `fcntl` 的 POSIX 系统。获取源码后，在仓库根目录执行：

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

测试仅使用标准库，无需 Ollama、MLX 或模型权重。真实语音验证需要 Apple Silicon Mac；准备方式见 [使用手册](docs/handbook.zh-CN.md)。选择 `sh setup.sh core` 会将虚拟环境同步为核心依赖；需要保留语音环境时使用 `sh setup.sh mlx`。

## 修改原则

- 原文在导入后保持不变。人物、情绪、声音配置和人工复核结果应分别保存。
- 为行为变化补充能够暴露问题的测试；涉及模型时先验证适配契约，再用短样验证真实行为。
- 新后端应明确支持的参数和输出格式，拒绝不支持的能力，提供参与缓存的版本标识。
- 项目写入、有限重试和缓存规则由核心管理，避免每个后端复制整套工作流。
- 完整流程应能脱离 UI 和交互式提示使用。为调用方保留 JSON 输出、退出码和路径约定；简化常见任务时不隐藏配置，也不悄悄更换声音。
- 文档区分已实现、已实测和计划能力，不把短样成功表述为整本质量保证。

模块职责见 [架构](docs/architecture.zh-CN.md)，后端方向见 [后端策略](docs/backend-strategy.zh-CN.md)。目前没有稳定的第三方插件 SDK；新增后端需修改内部注册位置。

## 语言维护约定

英文是规范的公开入口。默认 Markdown 文件使用英文，对应的 `.zh-CN.md` 提供完整简体中文文档。改变行为、操作说明或示例时，同步维护两个版本，包括语言切换、相对链接和章节链接。

代码注释与文档字符串、CLI 帮助和消息、默认 issue 模板及 issue 交流语言使用英文。翻译文档时保留标识符、配置键、命令、模型 ID 和实际运行参数。

文档语言与语音合成语言相互独立。原文、对白示例和参考录音转录保留原有语言，不要为了配合文档语言而机械翻译。尤其是 `reference_text` 必须准确转录录音实际说出的内容，合成的 `language` 设置应对应预期输出语言。自带中文示例在中英文文档中都保留为中文。

## 报告问题

提供 raradio 版本或提交、系统/Python 版本、相关依赖和模型版本、复现命令、预期行为与实际结果。优先用 `examples/` 中的原创短文或新的最小短文复现，附相关片段的状态和错误信息。

分享日志前移除用户名路径、服务凭据和私有地址。不要上传整本书、完整工作目录、模型权重或未经授权的参考录音。`doctor` 输出可以帮助排查，但其中的工具路径和模型清单也应先检查。

## 提交前检查

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -v
sh -n setup.sh run.sh
git diff --check
git status --short
```

PR 说明应包括改变的行为、验证方式与尚未验证的平台或模型。修订文档时检查相对链接、JSON 示例和命令前置条件；所有例子应能从获取的源码和明确列出的输入复现。

`tests/test_examples.py` 实际运行公开的离线教学脚本；`tests/test_example_templates.py` 使用公开 TXT 和 cast 模板，验证导入、合成契约、章节导出与缓存。修改示例时保持“准备材料、人工步骤、实际命令、预期输出”四项完整，不能只验证 JSON 可以解析。克隆模板的参考录音在测试中临时生成，模型推理被替换；这不证明克隆质量。

GitHub Actions 在 macOS/Linux、Python 3.11–3.14 上检查锁定的核心源码环境。手动选择的 MLX 任务检查 Apple Silicon 上的可选依赖安装与一致性；不下载模型，也不验证语音质量。依赖更新、版本规则与源码更新检查见[维护指南](docs/maintenance.zh-CN.md)。

个人输入、参考录音和临时配置放在被忽略的 `work/`、`output/` 或 `configs/`。生成的媒体、模型文件和凭据默认不提交。确需加入公开测试素材时，先明确来源与许可，再有意调整忽略及打包规则。

## 许可

raradio 的自有代码、文档及原创示例采用 [MIT](LICENSE)。提交内容应有权按该许可分发；第三方材料应明确标识来源和原有许可，不得用 raradio 的许可证覆盖它们。

## 面向 Agent 的行为

制作 Skill 位于仓库的 `raradio/skills/raradio-audiobook/SKILL.md`。`sh run.sh agent-guide` 通过源码 CLI 输出它；修改 CLI 时同步命令示例和状态/复核规则。制作流程集中维护在这一份可移植的英文 Skill 中，两个 README 同步保留简短入口。不要在单独指南或仓库的各客户端目录中重复维护同一 Skill。根目录 `AGENTS.md` 用于仓库开发约定。

使用 `python3 -m unittest tests.test_agent_guide -v` 检查发现入口。重要流程变化也应由只阅读随包指南的 Agent 使用原创短文实际运行；诊断音验证应与真实语音或试听结果分别记录。
