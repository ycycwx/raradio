# 从示例开始

[English](README.md) | 简体中文

先选场景，按“准备 → 运行 → 检查结果”完成短样，再换成自己的书。完整参数与排错见 [使用手册](../docs/handbook.zh-CN.md)。

克隆或下载仓库后，在包含 `pyproject.toml` 的根目录运行命令。核心流程需要 Python 3.11+ 和 POSIX 系统，Windows 原生环境暂不支持。真实人声需要 Apple Silicon Mac 与 Metal GPU。

文档语言与合成语言相互独立。这些示例在中英文文档中都保留原有中文文本、人物名称、参考转录和合成语言设置。

## 选择场景

| 场景 | 入口 | 额外准备 | 人工与自动的分工 |
| --- | --- | --- | --- |
| 1. 双章节、限量生成与续跑 | [双章节诊断](#1-双章节诊断) | 无模型、无 uv | 全自动，输出诊断音 |
| 2. 人物复核、单段重做与换声音 | [离线完整演示](#2-离线完整演示) | 无模型、无 uv | 脚本用样例已知答案代演人工操作 |
| 3. 一个声音读全文 | [单人预设](#3-单人预设) | MLX、CustomVoice 模型 | 选声音、试听；无需 Ollama |
| 4. 不同人物用不同预设声音 | [多角色预设](#4-多角色预设) | 另需 Ollama 文本模型 | 模型提议归属，用户复核疑难项 |
| 5. 用录音克隆音色 | [xvector 克隆](#5-xvector-克隆) | Base 模型、参考录音 | 选录音、试听；无需转录和 Ollama |
| 6. 用录音与准确文字克隆 | [ICL 克隆](#6-icl-克隆) | Base 编码器、录音、转录 | 用户核对转录；尚未完成真模型评测 |
| 7. 只克隆其中一个人物 | [混合配音](#7-混合配音) | 两种 TTS 模型、录音、Ollama | 确认角色与声音，再处理例外 |
| 8. 换成自己的小说 | [自己的书](#8-自己的书) | TXT、MLX、Ollama 文本模型 | 先发现角色，再确认完整人物表 |

本目录中文 TXT 为项目原创，随 [MIT 许可](../LICENSE) 分发。人物、别名和声音用于演示，不是任意小说的推荐名单。参考录音、模型和生成结果不随源码分发。

## 先了解结果与路径

- `work/…` 保存可恢复的制作项目，`output/…` 保存成品。场景之间用不同目录，同一项目续跑用相同目录。
- `build` / `run` 返回有效 JSON 时，`remaining: 0` 表示完成。达到 `--limit` 后仍有片段时，正常返回退出码 `2`。参数错误也可能返回 `2`，但没有 JSON 结果，应阅读 stderr。
- `build --output` 仅在全部完成时导出。没有成品时先 `status` / `review`，按 [复核流程](workflow.zh-CN.md) 处理，再 `run` 和 `export`。`review` 为空也可能只是还有待生成片段。
- `segments` 中 `audio_path` 相对于书籍工作目录。例如 `work/single` 的 `audio/abc.wav` 位于 `work/single/audio/abc.wav`。Mac 上可用 Finder 打开，或执行 `open` 加实际 WAV 路径。
- 比较不同文本分析器、模型或原文时用新工作目录；已有成功标注不会因更换 `--analyzer` 或 `--model` 自动重做。

场景 1、2 直接使用 Python，无需安装依赖。场景 3–8 中的 MLX 人声路线先准备 [uv](https://docs.astral.sh/uv/getting-started/installation/)，执行一次：

```sh
sh setup.sh mlx
```

它安装 Python 依赖；TTS 权重在首次合成时另行下载。`sh setup.sh core` 会将环境同步为仅核心依赖，需要保留人声环境时使用 `mlx`。

## 1. 双章节诊断

准备：Python 3.11+。**本例生成正弦波诊断音，不是人声。**

```sh
python3 -m raradio build examples/chapters.txt --work work/chapters-diagnostic \
  --analyzer single-voice --cast examples/cast.tone.json --limit 2
python3 -m raradio status work/chapters-diagnostic
python3 -m raradio run work/chapters-diagnostic
python3 -m raradio export work/chapters-diagnostic --output output/chapters-diagnostic
```

第一条命令会正常返回 `2`，因为只处理两段；后续 `run` 完成剩余片段。标题也会被朗读。应得到：

```text
output/chapters-diagnostic/
├── chapter-0001.wav
├── chapter-0001.srt
├── chapter-0002.wav
├── chapter-0002.srt
├── manifest.json
└── playlist.m3u
```

再次执行 `python3 -m raradio run work/chapters-diagnostic` 应复用有效音频。全文归 narrator，不分析人物。最短纯旁白示例使用 `demo.txt + cast.tone.json + --analyzer rules`，见仓库 [快速开始](../README.zh-CN.md#快速开始验证制作流程)。

## 2. 离线完整演示

准备：Python 3.11+，无需任何模型。

```sh
python3 examples/offline_workflow.py
```

每次运行在 `work/` 中创建新目录，打印实际位置和每一步 CLI 命令，保留结果。它演示人物确认、对白复核、限量生成、续跑、单段重做、只改小雨的声音和双章节导出。

脚本用 `chapters.txt` 的**预先已知答案代演人工操作**，不会识别任意小说，也不会自动接受音频警告。双章素材含四句实际对白和引号中的绰号“雨雨”；规则分析将这些引号片段留待确认，绰号应由旁白朗读。人物配置还演示“雨雨／小雨”“阿舟／林舟”的别名。

结果中 `book/` 可继续用 CLI 检查，`export/` 包含两章诊断音与字幕，`verification.json` 保存各阶段检查记录。想亲自操作，阅读 [复核、续跑与换声音](workflow.zh-CN.md)。

## 3. 单人预设

准备：MLX、CustomVoice 模型，无需录音或 Ollama。

```sh
sh run.sh build examples/clone.txt --work work/single \
  --analyzer single-voice --cast examples/cast.single.json --limit 2
sh run.sh segments work/single
```

先试听已生成的逐段 WAV；旁白和对白均使用 Serena。满意后继续：

```sh
sh run.sh run work/single
sh run.sh export work/single --output output/single
```

应得到 `output/single/chapter-0001.wav`、字幕、清单和播放列表。换声音时复制并编辑完整配置，按 [修改流程](workflow.zh-CN.md#换一个声音保留其他人的结果) 导入。

## 4. 多角色预设

准备：MLX，并安装、启动 [Ollama](https://ollama.com/)，准备文本模型：

```sh
ollama pull qwen3:14b
sh run.sh build examples/story.txt --work work/preset-story \
  --analyzer ollama --cast examples/cast.mlx.json --limit 3
sh run.sh segments work/preset-story
sh run.sh review work/preset-story
```

模板为旁白、小雨、林舟预先配置 Serena、Vivian、Ryan。Ollama 提议归属，结果可能仍需复核，不保证每次一致。试听并处理例外后：

```sh
sh run.sh run work/preset-story
sh run.sh export work/preset-story --output output/preset-story
```

应得到一个章节的三个角色配音。想试别名与跨章内容，可用 `chapters.txt` 和新工作目录分析；这份练习素材不是人物识别准确率基准。

## 克隆前先准备参考录音

使用自己的清晰单人录音，避免伴奏与多人同时说话。下面是占位路径，执行前换成真实文件：

```sh
mkdir -p work/voice-config
cp "/path/to/your-reference.wav" work/voice-config/reference.wav
```

没有录音、只想学习流程时，可先用预设声音朗读公开的 `reference.txt`：

```sh
sh run.sh build examples/reference.txt --work work/reference-demo \
  --analyzer single-voice --cast examples/cast.single.json \
  --output output/reference-demo
mkdir -p work/voice-config
cp output/reference-demo/chapter-0001.wav work/voice-config/reference.wav
```

只有全部完成并导出后才能复制。此时参考来自合成声音，仅演示克隆流程，不能评估真人音色相似度；ICL 使用前仍要试听、核对转录，不能假定合成器一定逐字读对。

`reference_audio: "reference.wav"` 相对于 **JSON 所在目录**；也可用真实绝对路径。JSON 中 `~` 和 `$HOME` 不会展开。导入后 raradio 复制录音到该书的 `voices/`。参考录音与待朗读正文不同：下面的目标正文是 `clone.txt`。

## 5. xvector 克隆

准备：MLX、Base 模型，并按 [参考录音准备](#克隆前先准备参考录音) 创建 `work/voice-config/reference.wav`。无需转录和 Ollama。

```sh
cp examples/cast.clone.xvector.json work/voice-config/cast.xvector.json
sh run.sh build examples/clone.txt --work work/clone-xvector \
  --analyzer single-voice --cast work/voice-config/cast.xvector.json --limit 2
sh run.sh segments work/clone-xvector
sh run.sh review work/clone-xvector
```

试听后继续并导出：

```sh
sh run.sh run work/clone-xvector
sh run.sh export work/clone-xvector --output output/clone-xvector
```

应得到一个章节，全部片段使用参考音色路线。不要添加 `reference_text`、预设 `speaker` 或 `instruct`。已有真模型短样运行记录，尚无克隆相似度评测。

## 6. ICL 克隆

准备：MLX、具有所需编码器的 Base 模型、录音及**它实际说出的准确文字**。先按 [参考录音准备](#克隆前先准备参考录音) 创建 `work/voice-config/reference.wav`。此路径已做适配契约测试，尚未完成真模型质量评测。

```sh
cp examples/cast.clone.icl.json work/voice-config/cast.icl.json
```

打开复制的 JSON，把 `reference_text` 中的提示句换成录音实际说出的全部文字，再运行下一组命令。日语录音填日语原句，不填中文译文；`language: "Chinese"` 是目标朗读语言。不要填写待朗读的 `clone.txt` 正文。

```sh
sh run.sh build examples/clone.txt --work work/clone-icl \
  --analyzer single-voice --cast work/voice-config/cast.icl.json --limit 2
sh run.sh segments work/clone-icl
sh run.sh review work/clone-icl
```

试听并处理问题后：

```sh
sh run.sh run work/clone-icl
sh run.sh export work/clone-icl --output output/clone-icl
```

比较两种模式时保留各自目录。缺少编码器需要兼容模型；改用 xvector 时同时删除转录。Base 克隆不支持通用情绪指令。模板的 `emotion_mode: reference` 允许保留分析情绪而不向 Base 发送控制指令，不保证参考韵律或标注情绪被准确实现。

## 7. 混合配音

准备：MLX、CustomVoice 与 Base 模型、运行中的 Ollama 和 `qwen3:14b`。先按 [参考录音准备](#克隆前先准备参考录音) 创建 `work/voice-config/reference.wav`；Ollama 准备见 [场景 4](#4-多角色预设)。

```sh
cp examples/cast.mixed.json work/voice-config/cast.mixed.json
sh run.sh build examples/story.txt --work work/mixed \
  --analyzer ollama --cast work/voice-config/cast.mixed.json --limit 3
sh run.sh segments work/mixed
sh run.sh review work/mixed
```

模板让小雨用 xvector 克隆、旁白用 Serena、林舟用 Ryan。试听并处理待办后：

```sh
sh run.sh run work/mixed
sh run.sh export work/mixed --output output/mixed
```

应得到一个混合声音章节。当前 MLX 后端只保留一个加载的模型，交替使用两种模型可能反复加载。Base 与 CustomVoice 的专用字段不能混填，两条路线均要求 `speed: 1.0`。

## 8. 自己的书

准备：MLX 与所选 TTS 模型，并完成 [场景 4](#4-多角色预设) 的 Ollama 准备，启动服务、执行 `ollama pull qwen3:14b`。这里的 `analyze` 默认需要 Ollama；只做单人朗读可使用 [场景 3](#3-单人预设)。输入为 UTF-8 TXT 或带 BOM 的 UTF-16 TXT。将下方路径换成真实文件，`work/my-book` 必须是新目录：

```sh
sh run.sh init "/path/to/book.txt" --work work/my-book
sh run.sh analyze work/my-book
sh run.sh cast work/my-book > work/my-book/cast.edit.json
```

下一步由你编辑：保留实际人物 ID，添加声音并确认。完整 JSON、共享与独立声音的例子见 [编辑全部人物与声音](../docs/handbook.zh-CN.md#2-编辑全部人物与声音)。导入会**替换整张人物表和声音表**，不能只提交改动的几行，也不要直接套用示例人物名单。

```sh
sh run.sh cast work/my-book --file work/my-book/cast.edit.json
sh run.sh run work/my-book --limit 5
sh run.sh segments work/my-book
sh run.sh review work/my-book
```

先试听、处理例外，再继续 `run` 并 `export`。无需逐段确认所有正常片段。日常修改见 [复核与换声音](workflow.zh-CN.md)。

## 示例如何保持可用

维护者修改示例后运行：

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

回归检查实际读取公开文本和配置，运行 CLI、参考文件导入、导出及缓存流程。契约测试替换模型加载与推理，因此通过不代表真实人声质量通过；新语音模型仍需按 [验证说明](../docs/verification.zh-CN.md) 做短样并记录版本。
