# 同类项目与 raradio 的适用范围

[English](reference-projects.md) | 简体中文

核对日期：**2026-09-12**。依据为项目官方文档，以及部分实现与打包配置。本次是有针对性的比较，没有穷尽所有项目，也没有安装这些项目或进行性能测试。分支链接会随上游更新；下文“已记录的支持”来自上游说明，对 raradio 发展方向的判断则是我们的评估。

[Audiblez](https://github.com/santinic/audiblez#how-to-install-the-command-line-tool) 提供直接转换 EPUB 的 CLI，[ebook2audiobook](https://github.com/DrewThomasson/ebook2audiobook#basic-usage) 提供 headless 转换和会话恢复。raradio 面向喜欢终端和自动化的人，目标是做一个容易安装、便于修订的有声书制作工具。下面的比较用于判断不同工作流的适用范围。

## 实际可选的项目

| 项目 | 文档中的接口与范围 | 需要考虑的安装边界 |
| --- | --- | --- |
| [Audiblez](https://github.com/santinic/audiblez) | 直接使用 `audiblez book.epub`；GUI 可选；输出章节 WAV 和 M4B | Python 包与 `espeak-ng`，生成 M4B 需要 `ffmpeg`；文档提供 CPU 和 CUDA 路径。[打包配置](https://github.com/santinic/audiblez/blob/main/pyproject.toml) 将 Python 限定在 3.10–3.12。 |
| [ebook2audiobook](https://github.com/DrewThomasson/ebook2audiobook) | Web 界面之外提供 `--headless`、批量输入和 `--session` 恢复；覆盖多种电子书和音频格式，包括 EPUB 和 M4B | 平台启动脚本与 Docker 路径；依赖及硬件要求随引擎变化。自动安装也可能涉及系统包管理器。 |
| [Abogen](https://github.com/denizsafak/abogen#interfaces) | 桌面和 Web 界面；EPUB/PDF/文本与字幕工作流 | uv/pip 与分平台说明；需要 `espeak-ng`，GPU 配置有所区别。[基础包](https://github.com/denizsafak/abogen/blob/main/pyproject.toml) 包含 PyQt6 和 Flask。 |
| [Audiobook Creator](https://github.com/prakharsr/audiobook-creator) | Gradio 工作流；LLM 人物归属、多声音、Kokoro/Orpheus 及多种输出格式 | 配置好的 LLM 和 TTS 服务，加上 uv 或 Docker；格式转换需要 FFmpeg，文档中的更广泛电子书/M4B 路径还涉及 Calibre。 |
| [Piper](https://github.com/OHF-Voice/piper1-gpl) | 本地 TTS 引擎，提供 [CLI](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/CLI.md)、Python API 和服务；将文字或文件输入转换为音频 | 安装 `piper-tts` 并另行下载声音模型；内嵌音素处理。它属于语音组件，书籍组织与编辑状态需要外围工作流管理。 |

ebook2audiobook 也已经在做**多声音与恢复工作流**。其 [E2A-SML 组件](https://github.com/DrewThomasson/ebook2audiobook/tree/main/components/E2A-SML) 提供 BookNLP 对白归属、headless CLI、声音映射和既有分析结果复用。修改一句话、确认不确定的说话人、崩溃后恢复时的具体行为，仍需实际运行比较；有恢复参数也不代表恢复语义完全相同。

从终端启动一个命令，也可能只是启动 UI 服务。核对的 Abogen [入口配置](https://github.com/denizsafak/abogen/blob/main/pyproject.toml) 中，`abogen-cli` 与 `abogen-web` 都调用同一个 [Flask 服务入口](https://github.com/denizsafak/abogen/blob/main/abogen/webui/app.py)。因此，本次不会仅凭这个名称就将它视为批量转换 CLI；这也不排除通过其 API 或其他接口自动化的可能。

对 raradio 来说，完整的 headless 路径意味着生成、状态检查、人物确认、修正、重试和导出都能脱离浏览器或桌面控件完成。阅读 JSON 或人工确认人物符合这一目标，但仍然是应当尽量减少的使用成本。

## raradio 目前提供的价值

raradio 当前的能力组合，适合希望保留并持续修订本地有声书项目的程序员：

- **明确的制作状态。** 原文、标注、人物与声音配置、参考录音和片段结果保存在同一工作目录。有效音频可以复用；更换声音或纠正人物归属时重新生成受影响的片段。
- **贯穿全过程的命令接口。** 检查与编辑命令输出 JSON，进度写入 stderr；脚本与用户可以驱动同一套流程。退出码、路径语义与人物表替换行为见 [使用手册](handbook.zh-CN.md)。
- **保留原文的分析方式。** 分析器为固定原文片段添加标注，不返回改写后的全书。这保护文字来源的可追溯性，但不保证合成器逐字读对。
- **精简的核心。** 核心包没有第三方运行依赖，诊断流程无需模型；单人朗读也无需文本 LLM。真实语音仍然依赖所选运行库、模型权重和适合的硬件。
- **清楚的扩展边界。** 文本分析与语音合成分离。项目代码与示例使用 [MIT 许可证](../LICENSE)，依赖和模型保留各自的许可，详见 [第三方说明](../THIRD_PARTY.zh-CN.md)。

这些是值得保留的产品属性，不能据此断言 raradio 更快、更准、在所有机器上更容易安装，或比其他项目更可靠。这样的结论需要可比较的运行记录和用户测试。

## raradio 当前的不足

| 目标 | 当前限制 |
| --- | --- |
| 简单上手 | 真实语音目前走 Apple Silicon/Metal 路径。无模型诊断可以验证流程，但只会生成提示音，不能证明语音环境已准备好。 |
| 实用的书籍转换 | 输入为 TXT；输出为章节 WAV、片段级 SRT、播放列表和清单。EPUB/PDF 导入及 MP3/M4B 打包需要其他工具。 |
| 灵活编辑 | 用户仍需编辑完整人物 JSON、检查复核项；人物表导入是全量替换，原文分段在项目创建时固定。 |
| 开放集成 | 有 JSON 和内部 Python 接口，但项目仍处于 Alpha；没有稳定的第三方插件 SDK、自动插件发现或广泛的后端选择。 |
| 可靠朗读 | 波形检查不能识别错读或衡量声音身份。全书质量、中文对白归属与跨平台语音性能仍需继续评估。 |

如果只想直接把 EPUB 转成 M4B，Audiblez 或 ebook2audiobook 可能已经覆盖更多步骤；如果需要可视化整理文字和字幕，Abogen 值得参考；如果应用只缺少语音引擎，Piper 是有用的起点。raradio 更适合希望用命令检查和修订 TXT 到音频制作过程、并能接受当前 Apple Silicon 语音环境要求的用户。这是我们对适用范围的判断，不是性能排名。

## 对项目打磨的启发

1. **把最小可用路径写清楚。** 单人朗读与人物分析分别介绍；Python 包、外部服务、模型下载和硬件分开说明，包管理器无法消除这四类要求。提供一条经过验证的默认安装路径，将高级选择放到后面的文档。
2. **将 CLI 行为作为公开接口维护。** 保持路径、JSON 输出、退出码和错误信息可预测；这些约定的变化需要发布说明和兼容性决策。未来的 UI 客户端应当使用相同的底层工作流。
3. **让灵活性体现为独立选择。** Audiobook Creator 的 [服务配置](https://github.com/prakharsr/audiobook-creator/blob/main/.env_sample) 分别设置人物分析、情绪标注与 TTS 地址。raradio 可以借鉴这种分离，同时保持自己的标注契约。聊天 API 相似不代表 schema、思考参数和生命周期行为可以互换。
4. **让人工修正可追溯。** 人物表、声音映射与可复用的分析结果对不同后端都有价值。BookNLP 展示了专用 NLP 路线，并不能证明 Ollama 或 llama.cpp 哪一个最适合中文分析；面向英文的示例也不能证明中文归属质量。
5. **把安装与恢复当作产品行为验证。** 覆盖干净环境、短语音样本、中断恢复、一次换声和一次人物修正，记录准确版本与实际限制。在声称优势之前，同时比较安装步骤、人工复核量、音频质量与运行成本。

这些优先事项指导后续工作，不代表已经增加了后端或完成了基准测试。已实现接口与候选方案见 [后端选择与扩展路线](backend-strategy.zh-CN.md)，raradio 的执行证据见 [测试与验证](verification.zh-CN.md)。

## Agent 辅助制作

raradio 现随包提供制作 Skill，并通过 `raradio agent-guide` 暴露，让用户已有的终端 Agent 操作复核与修订流程，无需第二个文本分析模型。具体范围见 [Skill](../raradio/skills/raradio-audiobook/SKILL.md)。2026-09-12 检查的 Audiblez、ebook2audiobook、Abogen 官方 README 未介绍项目自带的 Agent Skill 或 MCP 指南；这一有限检查不排除其他仓库文件或第三方集成。值得表达的是已有文档支撑的完整制作流程，不是 Agent 兼容性的独占。
