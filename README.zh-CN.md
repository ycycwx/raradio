# raradio

[English](https://github.com/ycycwx/raradio/blob/main/README.md) | 简体中文

**一个将 TXT 制作为可修订、可续跑有声书的 headless CLI。** 选择单人朗读或人工确认的多角色配音，逐段生成，导出章节 WAV 与 SRT。命令和 JSON 文件是项目的主要交互方式。

**Alpha · 真实语音目前需要 Apple Silicon Mac。** 无模型工作流无需语音依赖；长篇质量与更多语音后端仍在评估中。

raradio 的目标是：**面向喜欢终端和自动化的人，做一个容易安装、便于修订的有声书制作工具。**

- **简单上手**：无需模型就能验证完整流程；单人朗读不需要文本分析服务。
- **行为可预期**：保留原文、逐段保存进度、复用有效音频，集中处理异常。
- **灵活组合**：导入、分析、角色配置、生成和导出可以独立执行；JSON 结果与明确退出码便于接入脚本。
- **结合已有 Agent**：让你已有的终端 Agent 配置声音、确认明确归属并落实反馈；通过 [随包 Skill](https://github.com/ycycwx/raradio/blob/main/raradio/skills/raradio-audiobook/SKILL.md) 了解制作流程。
- **开放扩展**：分析与语音适配器独立于制作状态。目前仍是内部接口，稳定的插件 SDK 尚待实现。

未来的 UI 可以使用相同的制作流程，但构建或依赖 UI 不是本项目的主要目标。headless 表示无需图形界面或交互式提示，不表示可以省去声音选择和人工试听。

[安装指南](https://github.com/ycycwx/raradio/blob/main/docs/installation.zh-CN.md) · [使用手册](https://github.com/ycycwx/raradio/blob/main/docs/handbook.zh-CN.md) · [小说格式与结构修正](https://github.com/ycycwx/raradio/blob/main/docs/text-input.zh-CN.md) · [示例](https://github.com/ycycwx/raradio/blob/main/examples/README.zh-CN.md) · [同类项目](https://github.com/ycycwx/raradio/blob/main/docs/reference-projects.zh-CN.md) · [维护](https://github.com/ycycwx/raradio/blob/main/docs/maintenance.zh-CN.md) · [贡献指南](https://github.com/ycycwx/raradio/blob/main/CONTRIBUTING.zh-CN.md)

英文是默认文档语言；每页均有简体中文版本。文档语言与语音语言相互独立，自带中文样例仍保持中文。

## 安装并开始使用

真实语音目前要求 Apple Silicon Mac、macOS 14 或更高版本，并且可以使用 Metal。先[安装 uv](https://docs.astral.sh/uv/getting-started/installation/)，克隆仓库并运行：

```sh
git clone https://github.com/ycycwx/raradio.git
cd raradio
sh setup.sh mlx
sh run.sh setup
```

建议先选择 `single-voice`：旁白和对白都由一个声音朗读，**不需要 Ollama**。TTS 模型会在第一次生成语音时从 Hugging Face 下载，之后复用缓存。只有想使用 raradio 内置的多角色自动分析时，才需要增加 Ollama：

```sh
sh run.sh setup --mode multi-voice
```

`sh run.sh setup` 只检查并解释前置条件，不会自行安装软件或下载模型。目前唯一支持的分发和安装方式是使用仓库源码。

完整的首个单人样例、下载内容、更新和 Ollama 准备方式见[安装指南](https://github.com/ycycwx/raradio/blob/main/docs/installation.zh-CN.md)。如果只想在不下载语音模型的情况下验证完整流程，请运行[无模型示例](https://github.com/ycycwx/raradio/blob/main/examples/README.zh-CN.md#demo无需模型的端到端冒烟测试)。

## 配合你已有的 Agent

随包的 [raradio-audiobook Skill](https://github.com/ycycwx/raradio/blob/main/raradio/skills/raradio-audiobook/SKILL.md) 让能使用终端的 Agent 了解如何准备、生成和修订有声书。Agent 负责归属判断时可以跳过 Ollama，真实语音仍需 TTS 环境。例如，可以告诉 Agent：

> 先阅读 `sh run.sh agent-guide`，再帮我把 `book.txt` 制作为有声书。配置人物声音，先生成短样。明确的归属你可以决定，有歧义的留给我确认。

源码 CLI 可以直接输出完整 Skill：

```sh
sh run.sh agent-guide
```

需要客户端发现 Skill 时，将命令输出保存到它规定的技能目录，例如 `.agents/skills/raradio-audiobook/SKILL.md`。替换前检查已有的自定义版本，更新 raradio 后同步刷新。准备源码环境不会自动向 Agent 注册 Skill。

## 使用克隆音色或多角色配音

| 场景 | 配置模板 | 需要准备 |
| --- | --- | --- |
| 单人预设朗读 | [cast.single.json](https://github.com/ycycwx/raradio/blob/main/examples/cast.single.json) | CustomVoice 模型 |
| 仅参考录音克隆 | [cast.clone.xvector.json](https://github.com/ycycwx/raradio/blob/main/examples/cast.clone.xvector.json) | Base 模型、清晰的单人录音 |
| 录音与转录克隆 | [cast.clone.icl.json](https://github.com/ycycwx/raradio/blob/main/examples/cast.clone.icl.json) | Base 模型、录音、准确转录及兼容编码器 |
| 多个预设声音 | [cast.mlx.json](https://github.com/ycycwx/raradio/blob/main/examples/cast.mlx.json) | Ollama、CustomVoice 模型 |
| 克隆与预设混合 | [cast.mixed.json](https://github.com/ycycwx/raradio/blob/main/examples/cast.mixed.json) | Ollama、两类 TTS 模型与参考录音 |

复制模板并按 [示例说明](https://github.com/ycycwx/raradio/blob/main/examples/README.zh-CN.md) 准备输入。模板中的 `reference.wav` 需要自行提供，ICL 的转录提示也必须替换。参考音频的相对路径按 JSON 所在目录解析；导入后会复制进书籍项目。

多角色短篇示例：

```sh
ollama pull qwen3:14b
sh run.sh doctor --profile ollama --model qwen3:14b
sh run.sh build examples/story.txt --work work/story \
  --cast examples/cast.mlx.json --output output/story
```

运行前需要已安装并启动 Ollama，且已执行 `sh setup.sh mlx`。示例人物仅对应自带短篇；自己的小说应先分析，再编辑发现的完整角色表。具体步骤与人工/自动分工见 [使用手册](https://github.com/ycycwx/raradio/blob/main/docs/handbook.zh-CN.md)。

## 工作目录与日常操作

`work/书名/` 保存原文、角色配置、参考音频、SQLite 状态与逐段 WAV；`output/书名/` 是导出的成品。保留完整工作目录，才能继续制作或换声音。

```sh
sh run.sh status work/story
sh run.sh review work/story
sh run.sh run work/story
sh run.sh export work/story --output output/story
```

角色配置通过 `cast --file` **整表替换**，编辑时应保留其他人物。换分析器或文本模型不会自动重做已成功的标注；比较分析方案时使用新工作目录。更改声音配置会使受影响的音频重新生成。

工作流的 JSON 结果写入 stdout，进度与错误写入 stderr。帮助、版本、`setup` 和 `agent-guide` 输出文本；后两者也支持 `--format json`。`build` / `run` 返回有效 JSON 时，退出码 `0` 表示全部完成，`2` 表示仍有待办，也可能只是达到 `--limit`。参数解析错误也可能返回 `2`，但没有 JSON 结果。执行阶段捕获的错误为 `1`，中断为 `130`。

`raradio`、`python -m raradio` 和 `sh /path/to/run.sh` 均按当前目录解释命令中的相对路径。cast JSON 内的参考录音仍按 JSON 所在目录解释。本页示例假设当前目录为仓库根目录。

## 能力范围

当前支持 TXT、章节 WAV、片段级 SRT、波形检查与人工复核。尚未实现 EPUB、MP3/M4B、ASR 回读、音色相似度检查或第三方插件自动发现。目前也不是通用的 CPU/CUDA/Linux 语音工具或成熟的一键电子书转换器。自动人物分析仍需确认角色表，不确定的片段需要人工复核；音频检查通过不能判断错读或音色不一致。

llama.cpp 属于候选后端，当前未接入。后端接口、已实现能力和接入顺序见 [后端策略](https://github.com/ycycwx/raradio/blob/main/docs/backend-strategy.zh-CN.md)。运行证据与复现方法见 [测试与验证](https://github.com/ycycwx/raradio/blob/main/docs/verification.zh-CN.md)。

## 参与开发与许可

测试不需要下载模型：

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

版本调整、依赖更新、项目格式兼容性和源码更新检查见 [维护指南](https://github.com/ycycwx/raradio/blob/main/docs/maintenance.zh-CN.md) 与 [更新记录](https://github.com/ycycwx/raradio/blob/main/CHANGELOG.zh-CN.md)。[开源审查](https://github.com/ycycwx/raradio/blob/main/docs/open-source-review.zh-CN.md) 记录当前不足和后续优先级。

提交问题或改动前请阅读 [贡献指南](https://github.com/ycycwx/raradio/blob/main/CONTRIBUTING.zh-CN.md)。复现材料使用原创短文和可公开的配置，避免附带个人书籍、录音或凭据。

raradio 自有代码、文档与原创示例采用 [MIT 许可证](https://github.com/ycycwx/raradio/blob/main/LICENSE)。依赖、模型权重和用户输入保留各自许可；具体范围及需要单独处理的组件见 [第三方依赖说明](https://github.com/ycycwx/raradio/blob/main/THIRD_PARTY.zh-CN.md)。
