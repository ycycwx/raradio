# raradio 使用手册

[English](handbook.md) | 简体中文

raradio 把一份 TXT 做成可继续加工的有声书项目：先切分原文，再确定每段由谁读、用什么声音，逐段生成并检查，最后导出章节音频。你可以先处理一个短样本，听过后继续整本；中途停止、换角色声音或修正一句对白，都不用从头生成。

最短安装与首个样例请先看[安装 raradio](installation.zh-CN.md)。

没有章节或对白标记、导入日文旧编码、切换分析方式，以及手工修正片段边界，见 [小说格式与结构修正](text-input.zh-CN.md)。

先分清三个东西：**TXT 是输入，`work/书名/` 是可以恢复的制作项目，`output/书名/` 是交付给播放器的成品**。模型、Python 环境不在书籍项目里。保留工作目录，才能以后改声音、补做或迁移。

第一次使用，建议依次读“准备环境”“诊断演示”“预设声音”。已经有自己的声音样本，直接接着读克隆场景；处理新书时，使用“自己的多角色小说”流程。

## 目录

- [哪些工作自动完成，哪些需要你决定](#哪些工作自动完成哪些需要你决定)
- [准备环境、文件与路径](#准备环境文件与路径)
- [场景一：不下载模型，检查流程](#场景一不下载模型检查流程)
- [场景二：用预设声音读短篇](#场景二用预设声音读短篇)
- [场景三：整篇只用一个声音，包含对白](#场景三整篇只用一个声音包含对白)
- [场景四：有参考音频，没有转录，使用 xvector 克隆](#场景四有参考音频没有转录使用-xvector-克隆)
- [场景五：有参考音频及准确转录，使用 ICL 克隆](#场景五有参考音频及准确转录使用-icl-克隆)
- [场景六：旁白、预设角色与克隆角色混用](#场景六旁白预设角色与克隆角色混用)
- [场景七：给自己的多角色小说制作有声书](#场景七给自己的多角色小说制作有声书)
- [听样本、看状态与理解退出码](#听样本看状态与理解退出码)
- [归属、音频与配置出错时怎么修](#归属音频与配置出错时怎么修)
- [整本运行、停止、续跑与重复制作](#整本运行停止续跑与重复制作)
- [复制到另一台机器继续](#复制到另一台机器继续)
- [更换文本模型、TTS 模型与运行后端](#更换文本模型tts-模型与运行后端)
- [验证范围与复现](#验证范围与复现)
- [当前扩展方式与以后可能的插件](#当前扩展方式与以后可能的插件)

## 哪些工作自动完成，哪些需要你决定

| 环节 | raradio 当前自动做什么 | 你需要做什么 |
| --- | --- | --- |
| 导入 | 读取 TXT，保存固定原文，按章节标题、引号及长度切成片段，保留原文位置 | 提供可读取的 TXT；需要修订正文时先修订输入文件，再建新项目 |
| 单人朗读 | `single-voice` 把旁白和对白全部交给 `narrator`，情绪设为 neutral | 选定一个声音 |
| 多角色分析 | Ollama 根据上下文提出人物、别名、对白归属和情绪；保守规则模式只确定旁白 | 确认人物表、声音和别名；处理归属不确定的段落 |
| 声音配置 | 保存人物到声音的映射，把参考音频复制进工作目录 | 选预设声音，或准备克隆参考音频；ICL 还要准备准确转录 |
| 生成 | 按段调用声音模型，保留完成结果，默认每段最多尝试 3 次 | 先试听少量代表片段，再决定是否批量生成 |
| 检查 | 检查 WAV 文件、空音频、静音、削波和明显异常时长，记录警告 | 判断错读、漏读、重读、人物是否读对、音色和情绪是否合适 |
| 修复 | 配置或归属改变后，让相关片段重新生成；保留其他有效片段 | 修正问题原因，必要时指定单段重做；试听后才接受音频警告 |
| 导出 | 所有片段完成后，拼接章节 WAV，生成 SRT、播放列表和来源清单 | 在播放器中收听成品，保留工作目录供以后修改 |

模型给出的 `confidence` 是它对人物标注的自评数值，**不是已经测得的正确率**。当前低于 0.8 的归属会进入复核；超过阈值也可能认错人物。新发现的人物不会自动替你选声音并确认。

目前没有参考音频自动转录，也没有生成后的 ASR 回读校对、音色身份检查或整本听感评分。字幕使用原文片段与实际音频时长，是片段级字幕，不是语音识别结果。raradio 不改写原文；这也不能保证合成器一定逐字读对。

## 准备环境、文件与路径

### 在哪里运行命令

本手册的命令都从 raradio 源码根目录执行，也就是包含 `setup.sh`、`run.sh`、`examples/` 的目录。先进入自己的源码目录，将下面的 `/path/to/raradio` 替换为实际位置：

```sh
cd /path/to/raradio
```

后面的 `work/my-book`、`configs/`、`output/` 都是相对这个根目录的路径。示例中的 `/path/to/`、`SEGMENT_ID` 和“实际文件名”均为占位符，需要替换后再执行。

`sh /path/to/run.sh`、已安装的 `raradio` 和 `python3 -m raradio` 均按当前目录解释命令行相对路径。脚本会找到仓库的环境，但不会改变书籍路径的基准目录。路径含空格时加双引号，例如 `"/path/to/Books/My Book.txt"`。下文示例仍从仓库根目录执行，因为自带的 `examples/` 位于那里。

声音配置的参考文件另有一条规则：`reference_audio` 相对于传给 `cast --file` 或 `build --cast` 的 **JSON 文件所在目录**。例如 `configs/cast.clone.json` 里写 `"reference_audio": "voices/reader.wav"`，实际查找的是 `configs/voices/reader.wav`。写成绝对路径也可以。JSON 中的路径不会展开 `~` 或 `$HOME`，应填写实际绝对路径或相对路径。配置导入成功后，raradio 会复制参考文件到该书的 `voices/`，后续不再依赖原文件位置。

### 只检查流程：核心环境

需要 Python 3.11 或更新版本，以及提供 `fcntl` 文件锁的 POSIX 系统；Windows 原生环境暂不支持。核心功能只使用 Python 标准库，从源码运行 `python3 -m raradio` 不需要安装声音模型。若要统一使用本手册的 `sh run.sh`，先准备 `uv`，再安装核心环境：

```sh
sh setup.sh core
sh run.sh doctor
```

没有 `uv` 时，安装脚本会给出提示；使用 Homebrew 的 Mac 可以先运行 `brew install uv`。`setup.sh core` 只准备核心 CLI，不能生成真人语音；它会把环境同步为核心依赖并移除已安装的可选语音依赖，需要保留语音环境时使用 `sh setup.sh mlx`。

### 要生成语音：MLX 环境

当前人声后端面向 macOS 14+ 的 Apple Silicon Mac，需要可以访问 Metal GPU。源码安装通过 `.python-version` 选择 Python 3.11，缺少时由 uv 下载。核心支持更新的 Python 版本，不代表所有可选语音依赖均已兼容。安装项目固定的 Python 依赖：

```sh
sh setup.sh mlx
sh run.sh setup
```

脚本依据 `uv.lock` 安装，当前 MLX-Audio 固定为 0.5.3。安装 `mlx` 依赖和下载 TTS 模型是两件事：示例中的 Hugging Face 模型通常在第一次合成时才下载，已有缓存会复用。首次运行比后续慢，不能只用第一次的总耗时估计整本速度。

### 要自动区分小说角色：再准备 Ollama

只有选择 `--analyzer ollama` 时才需要 Ollama。预设声音、声音克隆本身不要求 Ollama；整篇单人朗读可以完全跳过它。

安装并启动 Ollama 后，准备默认的文本模型：

```sh
ollama pull qwen3:14b
sh run.sh doctor --profile ollama --model qwen3:14b
```

默认连接 `http://localhost:11434`。`setup` 默认检查单人朗读路径，不会连接 Ollama；`setup --mode multi-voice` 同时检查语音与 Ollama 条件。它默认输出易读文本，也支持 `--format json`。`doctor` 保留为较底层的单项检查：核心 profile 不发网络请求，`--profile ollama` 会查询指定服务上是否存在 `--model`。所选检查通过时退出码为 `0`，缺少必要条件时为 `1`。这些检查不会自行安装、初始化 Metal、下载或加载 TTS 权重、执行人物分析，也不验证听感。当前 WAV 导出不需要 FFmpeg。`sh run.sh --version` 用于报告 raradio 版本。

### 联网准备与离线使用

Python 依赖、Ollama 文本模型、Hugging Face TTS 模型分别准备。`setup.sh` 不会替你拉取 Ollama 模型，raradio 分析也不会自动安装缺失的文本模型。先在联网环境完成所选路径的一次短样本，确认模型及其配套文件都已缓存，再在离线环境运行相同配置。只有依赖已安装，不足以保证离线合成成功。

本地 Ollama 加本地 MLX 的流程不需要持续调用付费 API。缓存位置由相应运行环境管理，不属于 `work/书名/`；备份和迁移时需要分别考虑。也可以把 `voices` 中的 `model` 配置为已准备好的本地模型绝对路径。

### 需要准备哪些文件

| 你想做的事 | 准备内容 |
| --- | --- |
| 流程诊断 | 仓库自带 TXT 与 `cast.tone.json` |
| 单人预设朗读 | TXT、一份只映射旁白的声音 JSON；无需参考音频 |
| 多个预设声音 | TXT、Ollama 模型、确认后的全部人物与声音映射 |
| xvector 克隆 | TXT、Base 模型、一段清晰的单人参考音频；省略转录 |
| ICL 克隆 | 上述文件，加上参考音频真正说出的准确文字及支持所需编码器的模型 |
| 多角色中只克隆一个人 | 全部人物表、该角色的参考音频、其他人物的预设声音配置 |

输入使用 UTF-8 TXT，或带 BOM 的 UTF-16/UTF-32 TXT。其他文本编码可以用 `--encoding` 显式指定，例如 `--encoding cp932`；参见[原稿格式](text-input.zh-CN.md)。EPUB、PDF 需要先在外部转换成 TXT。建议用只有目标说话者、背景干扰较少的短录音开始验证克隆；当前程序不会替你去除伴奏、分离多个人声或寻找最佳参考片段。

## 场景一：不下载模型，检查流程

这个场景用于确认导入、生成状态、续跑、字幕和导出都能工作，输出是正弦波诊断音。

已经安装核心环境时：

```sh
sh run.sh build examples/demo.txt --work work/diagnostic \
  --analyzer rules --cast examples/cast.tone.json --output output/diagnostic
```

还没安装环境时，也能直接从源码运行：

```sh
python3 -m raradio build examples/demo.txt --work work/diagnostic \
  --analyzer rules --cast examples/cast.tone.json --output output/diagnostic
```

两种命令二选一即可。完成后，`output/diagnostic/` 里有 `chapter-0001.wav`、同名 `.srt`、`playlist.m3u` 和 `manifest.json`。再次运行同一命令，有效的已完成音频会复用。

这个示例没有需要识别人物的对白。`rules` 不会自动识别对白的说话者：把含对白的小说换进来，通常会看到对白等待人工确认。需要“一人读所有内容”时，使用下文 `single-voice`。

## 场景二：用预设声音读短篇

你需要 MLX 环境、Ollama 和 `qwen3:14b`，不用准备参考录音。

```sh
sh run.sh build examples/story.txt --work work/preset-story \
  --cast examples/cast.mlx.json --output output/preset-story
```

`examples/story.txt` 是原创短对话。示例 JSON 已确认旁白 `narrator`、小雨 `xiaoyu`、林舟 `linzhou`，分别选用 CustomVoice 的 Serena、Vivian、Ryan。Ollama 负责把对白归到这些人物；若有不确定标注，命令会留下待办，可以用 `review` 查看。

完成后试听 `output/preset-story/chapter-0001.wav`。该例的目的是确认三个声音和生产流程能连接起来，不能代替长篇评估。换成自己的小说时，不要继续把这三个人物的示例配置当作全书人物表；使用“自己的多角色小说”流程发现并确认真实角色。

## 场景三：整篇只用一个声音，包含对白

如果你想让同一个旁白读完全文，无需先识别人物。`--analyzer single-voice` 会把引号内外的内容都交给 `narrator`，情绪统一为 `neutral`；它保留原来的文本、对白切分和章节。

复制单人模板到自己的配置目录；需要换声音时编辑复制的文件：

```sh
mkdir -p configs
cp examples/cast.single.json configs/cast.single.json
```

```json
{
  "characters": {
    "narrator": {
      "name": "旁白",
      "aliases": [],
      "voice": "narrator",
      "confirmed": true
    }
  },
  "voices": {
    "narrator": {
      "backend": "mlx",
      "model": "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
      "speaker": "Serena",
      "instruct": "自然朗读，声音清晰，语气平稳。",
      "language": "Chinese",
      "speed": 1.0,
      "seed": 42
    }
  }
}
```

上面展示完整配置结构；也可以直接保留模板。`characters.narrator.voice` 和 `voices` 中的键需要对应。JSON 的 `true`、数字 `1.0` 和 `42` 不加引号，字符串用双引号，不添加注释或多余逗号。

用带对白的短示例检查：

```sh
sh run.sh build examples/story.txt --work work/single-story \
  --analyzer single-voice --cast configs/cast.single.json \
  --output output/single-story
```

需要处理自己的长篇时，把输入路径换成你的 TXT，使用新的 `--work`，并先加 `--limit 5`。这个数量按本次实际处理的片段计算，不保证包含各种句型。听完后执行 `sh run.sh run work/你的书名` 继续。

如果以后想把同一本书改成多人配音，应新建工作目录重新分析。已成功标注的项目不会因为换一个 `--analyzer` 参数而自动全面重标注。

## 场景四：有参考音频，没有转录，使用 xvector 克隆

使用 Base 模型，通过参考音频提取声音特征。这个模式不使用参考转录，也不会自动替你生成转录。先从“一个克隆声音读全篇”开始，便于单独判断音色效果，不需要 Ollama。

复制模板：

```sh
mkdir -p configs
cp examples/cast.clone.xvector.json configs/cast.clone.xvector.json
```

打开 `configs/cast.clone.xvector.json`，把 `reference_audio` 改成你已有录音的绝对路径。相关声音字段应为：

```json
{
  "backend": "mlx",
  "model": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit",
  "reference_audio": "/path/to/recordings/reader.wav",
  "clone_mode": "xvector",
  "emotion_mode": "reference",
  "language": "Chinese",
  "speed": 1.0,
  "seed": 42
}
```

上面是 `voices` 中单个声音的内容，完整的 `characters` 和 `voices` 结构已在模板里。`/path/to/recordings/reader.wav` 是示意路径，必须换成存在的文件。不要添加 `reference_text`、预设 `speaker` 或 `instruct`。

```sh
sh run.sh build examples/clone.txt --work work/clone-xvector \
  --analyzer single-voice --cast configs/cast.clone.xvector.json \
  --limit 3
sh run.sh segments work/clone-xvector
```

按下文的路径说明听已生成的片段。认可后继续并导出：

```sh
sh run.sh run work/clone-xvector
sh run.sh review work/clone-xvector
sh run.sh export work/clone-xvector --output output/clone-xvector
```

Base 的 `emotion_mode: reference` 表示允许这条克隆路线处理带有情绪标注的段落，而不会把标注拼成不受支持的情绪指令。**它不保证参考录音的情绪、节奏或韵律会被准确迁移**，也不保证自动实现小说里分析出的 happy、sad 等情绪。真实结果需要试听。

Base 默认的 `emotion_mode: strict` 只接受 neutral 情绪。单人模式的标注本来就是 neutral，strict 也能使用；多角色配置中选择 reference，是一次性决定不把分析情绪当成 Base 的控制能力。

## 场景五：有参考音频及准确转录，使用 ICL 克隆

ICL 需要音频和文字对应，而且所选 Base 模型必须有说话人编码器及语音 tokenizer 编码器。模板不会替你准备这些文件。

```sh
mkdir -p configs
cp examples/cast.clone.icl.json configs/cast.clone.icl.json
```

编辑复制的模板：

- `reference_audio` 填真实文件路径，建议第一次用绝对路径。
- `reference_text` 填这段音频实际说出的文字，逐句对照录音确认。
- 保持 `clone_mode: "icl"`；TTS 模型使用 Base。
- 不填写预设 `speaker` 或 `instruct`；`speed` 保持 `1.0`。

例如，录音中确实说的是“雨停了，我们回家吧。”，对应的两个字段才应写成：

```json
{
  "reference_audio": "/path/to/recordings/reader.wav",
  "reference_text": "雨停了，我们回家吧。"
}
```

这个小对象展示需要编辑的字段，不能单独替代整份配置。音频若是日语，转录就应是实际日语内容，不能填中文译文。`language: "Chinese"` 指希望生成的语言，不会替你翻译参考音频，也不能证明跨语言克隆效果。

```sh
sh run.sh build examples/clone.txt --work work/clone-icl \
  --analyzer single-voice --cast configs/cast.clone.icl.json --limit 3
sh run.sh segments work/clone-icl
```

试听通过后，再 `run` 剩余内容并 `export`。如果报缺少编码器，准确转录本身不能解决模型能力缺失；需要准备兼容的 Base 模型，或明确改用 xvector 并删除 `reference_text`。

ICL 的自动化测试使用替代模型检查参数与适配契约，不能证明真实语音效果。项目尚未完成 ICL 的真实推理与试听评测。需要比较 ICL 与 xvector 时，用同一录音分别创建两个短项目，保留各自配置和试听结论。

## 场景六：旁白、预设角色与克隆角色混用

人物身份和声音配置是分开的。`characters` 里的每个人通过 `voice` 指向 `voices` 中的一份配置；多个人也可以指向同一个声音。一个项目可以同时用 CustomVoice 预设声音和 Base 克隆，但不能在同一份声音配置里混填两类模型的专用参数。

```sh
mkdir -p configs
cp examples/cast.mixed.json configs/cast.mixed.json
```

模板让旁白用 Serena、林舟用 Ryan，小雨用 Base xvector 克隆。把小雨的声音配置中的 `reference_audio` 改成实际录音路径即可。人物对应的是 `examples/story.txt`，可以在这个短篇里同时听到预设与克隆声音。

```sh
sh run.sh build examples/story.txt --work work/mixed-story \
  --cast configs/cast.mixed.json --limit 5
sh run.sh segments work/mixed-story
sh run.sh review work/mixed-story
```

这里需要 Ollama 来分析对白归属。单个声音的 `backend` 都可以是 `mlx`，`model` 分别选 Base 或 CustomVoice。CustomVoice 用 `speaker` 和可选 `instruct`；Base 用 `reference_audio` 与对应克隆模式。分析到情绪不代表两类模型具有相同的情绪控制能力。

混用不同模型时，当前 MLX 后端只保留一个已加载模型，按片段顺序需要时切换。先听一小段并观察耗时，再决定是否用在整本书。对自己的小说使用该配置思路即可，不要用模板覆盖已经发现的真实人物表。

## 场景七：给自己的多角色小说制作有声书

这个流程把发现角色、人工确认和正式生成分开，适合人物未知的新书。先准备好 Ollama 与所选声音环境；输入文件示例 `/path/to/book.txt` 要替换成真实路径。

### 1. 导入并发现角色

```sh
sh run.sh init /path/to/book.txt --work work/my-book
sh run.sh analyze work/my-book
sh run.sh status work/my-book
sh run.sh cast work/my-book > work/my-book/cast.edit.json
```

`init` 要求工作目录还不存在，并固定保存原文。默认最长片段约 240 个字符；希望用更短片段时，在首次导入加 `--max-chars 160`。切分包括章节标题和正文，标题也会被朗读。修改切分长度需要用原始 TXT 建新项目。

`analyze` 默认使用 Ollama，按章保存结果，模型按批次接收附近上下文与已有角色。人物出现后通常仍是 `confirmed: false`，这是让你先选声音，不是分析失败。

### 2. 编辑全部人物与声音

打开 `work/my-book/cast.edit.json`，保留已经发现的全部人物 ID，并逐个处理：核对 `name`、整理明确别名 `aliases`、指定 `voice`，确认后设置 `confirmed: true`。旁白固定用 `narrator`。人物 ID 是后续归属和声音映射的连接点，不能只凭名字相似就随意更换。

比如人物已经以 `xiaoyu` 被发现，保留这个 ID；可以把“雨雨”作为已确认的别名。不要把“他”“她”“那个人”等泛指代词永久绑定到一个人物。模型仍需要根据上下文判断它们。

在同一个 JSON 的 `voices` 中添加声音，字段参考上面几种场景。预设声音无需参考音频；克隆参考文件按这份 JSON 所在目录解析。本手册把编辑文件放在 `work/my-book/` 内，是为了让已保存的 `voices/内容哈希.wav` 引用保持有效。

例如，**实际导出的人物 ID 恰好是下面三个时**，可以整理为这份完整配置。旁白和小雨共用 `shared`，林舟使用独立声音。你自己的导出若有不同 ID 或更多人物，应保留它们，在原表上修改 `voice`、`confirmed` 并添加对应声音，不要直接覆盖为示例名单。

```json
{
  "characters": {
    "narrator": {"name": "旁白", "aliases": [], "voice": "shared", "confirmed": true},
    "xiaoyu": {"name": "小雨", "aliases": ["雨雨"], "voice": "shared", "confirmed": true},
    "linzhou": {"name": "林舟", "aliases": ["阿舟"], "voice": "linzhou", "confirmed": true}
  },
  "voices": {
    "shared": {
      "backend": "mlx",
      "model": "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
      "speaker": "Serena",
      "language": "Chinese",
      "instruct": "自然朗读，清晰、平稳。",
      "seed": 42
    },
    "linzhou": {
      "backend": "mlx",
      "model": "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit",
      "speaker": "Ryan",
      "language": "Chinese",
      "instruct": "自然地说话，温和、放松。",
      "seed": 43
    }
  }
}
```

`characters` 表示“书里有谁”，`voices` 表示“有哪些声音配置”，通过 `voice` 的值关联。想让小雨独立配音，就在 `voices` 新增一份声音并修改她的 `voice`。修改 `shared` 会影响所有指向它的人物。无需模型的完整练习见 [复核与换声音示例](../examples/workflow.zh-CN.md)。

**导入声音配置是替换整张人物表和声音表，不是合并补丁。** 即使只想更换一个人的声音，也要以当前完整导出为起点，保留所有发现的人物及其他声音配置。否则被遗漏人物对应的片段会失去确认或声音。

```sh
sh run.sh cast work/my-book --file work/my-book/cast.edit.json
sh run.sh review work/my-book
```

人物确认后，归属足够明确的片段会自动进入 `READY`。仍然待复核的段落，按 `issue` 处理；不用逐段确认所有正常片段。

### 3. 先生成少量内容

```sh
sh run.sh run work/my-book --limit 5
sh run.sh segments work/my-book
```

先听这批音频，再决定是否继续。`--limit 5` 只限制本次处理片段数，某一段的内部重试仍可能发生；它不会替你挑齐每个人物、各种情绪或专名。如果开头全是旁白，可以再运行一小批，或另做一个有代表句的短 TXT 样本项目。

选择试听材料时，覆盖你实际关心的声音、普通对白、较长句、情绪变化和人名。声音不满意时先改配置并重新导入，听新样本后再继续，这比全书生成完再统一换声音容易判断。

### 4. 继续、处理例外、导出

```sh
sh run.sh run work/my-book
sh run.sh review work/my-book
sh run.sh status work/my-book
```

有异常时按后面的修复流程处理，再继续 `run`。`status` 中 `remaining` 为 `0` 才能导出：

```sh
sh run.sh export work/my-book --output output/my-book
```

导出目录包含章节 WAV、片段级 SRT、播放列表和记录原文片段与检查结果的 `manifest.json`。目前没有直接导出 MP3/M4B。想调整片段之间的停顿，可重新导出，例如 `--pause-ms 250`，这不会重新合成每段声音。试听笔记和其他个人文件放在导出目录以外；再次导出会检查目录归属，拒绝覆盖夹杂其他文件的目录。

## 听样本、看状态与理解退出码

三个查看命令各有用途：

```sh
sh run.sh status work/my-book
sh run.sh segments work/my-book
sh run.sh review work/my-book
```

`status` 汇总数量；`segments` 展示全部片段的原文、人物、情绪、状态、音频路径与 QA；`review` 只列 `NEEDS_REVIEW` 和 `FAILED`。因此 `review` 为空不代表整本完成，还可能有未分析、待生成或中断中的片段，应同时看 `status.remaining`。

| 状态 | 含义 | 下一步 |
| --- | --- | --- |
| `PENDING_PARSE` | 尚未完成文本分析 | 执行 `analyze` |
| `READY` | 标注与声音映射可用 | 执行 `run` |
| `GENERATING` | 上一次生成正在进行，或曾在该处中断 | 确认旧进程停止后，再执行 `run` |
| `DONE` | 音频检查通过，或该段当前音频已由你接受 | 有效缓存可以复用 |
| `NEEDS_REVIEW` | 人物、标注、参考文件或音频警告等待处理 | 阅读该段 `issue` |
| `FAILED` | 多次尝试仍生成失败 | 修复原因后 `retry`，再 `run` |

`segments` 返回的 `audio_path` **相对于书籍工作目录**。例如 `work/my-book` 的某段返回 `audio/abc.wav`，实际文件是 `work/my-book/audio/abc.wav`。在 Mac 上可用 Finder 打开，或把实际路径放进：

```sh
open work/my-book/audio/实际文件名.wav
```

没有 `audio_path` 的片段尚无可用音频，不能直接试听。整章完成并导出后，打开 `output/my-book/chapter-0001.wav` 即可。

工作流命令把 JSON 结果写到 stdout，把合成进度和模型日志写到 stderr。`--help`、`--version`、`setup`、`agent-guide` 输出文本；后两者支持 `--format json`。需要保存状态时可以重定向 JSON，例如 `sh run.sh status work/my-book > work/my-book/status.snapshot.json`。

`build` 与 `run` 的退出码有特定含义：

| 退出码 | 含义 |
| --- | --- |
| `0` | 所有片段已完成 |
| `2` | 有有效 JSON 结果时，表示还有工作未完成，可能只是 `--limit` 到达，也可能有待确认或失败的段落；命令参数解析错误也使用此码，但没有 JSON 结果 |
| `1` | 执行阶段捕获的配置、路径或运行错误；阅读 stderr |
| `130` | 被 Ctrl+C 中断；进度已经保存，可以续跑 |

因此 `--limit 5` 正常生成了五段后返回 `2`，不等于运行崩溃。手册把命令分行列出，方便继续查看结果；写自动化 shell 脚本时，要结合 stdout 是否有有效 JSON 结果和 stderr 处理 `2`，不要直接用 `set -e` 或 `&&` 把它当成必须立即终止的错误，也不要把缺少参数或拼错选项当成正常续跑。`analyze` 的退出码也不能替代状态检查：分析服务失败可能被记入片段的 `issue`，应读取输出和 `review`。

## 归属、音频与配置出错时怎么修

先看 `review` 中的 `issue`，把原因和需要的操作对应起来。下列 `SEGMENT_ID` 要替换为 `review` 或 `segments` 返回的真实 ID，人物 ID 要取自当前 `cast`。

### 某句话归错了人，或者归属不确定

先确认目标人物存在、已经 `confirmed: true` 且有声音。然后修正该段：

```sh
sh run.sh resolve work/my-book SEGMENT_ID --speaker xiaoyu --emotion happy
sh run.sh run work/my-book
```

不需要改情绪就省略 `--emotion`。`resolve` 会保存人工归属、让受影响片段重新生成；通常不用紧接着再 `retry`。人工修正会在后续分析失败后的恢复中保留。

如果只是人物还没确认或缺少声音，应编辑完整 cast 并导入，而不是对每一句都调用 `resolve`。要把某段交给旁白，使用 `--speaker narrator`。

### Ollama 无法连接、模型未准备或返回非法标注

检查 Ollama 是否启动、`doctor --profile ollama --model YOUR_MODEL` 是否列出所选文本模型、配置的 URL 是否正确。修复服务后：

```sh
sh run.sh analyze work/my-book
sh run.sh review work/my-book
```

已经成功保存的分析不会全部重跑，人工修正也不会丢失。长段或慢模型超时时，可以针对未完成分析增加 `--timeout 300` 或减少 `--batch-size 12`。`--timeout` 是每批请求的限制，不是整本处理时限。

### 音频有警告：`audio: silence`、`clipping`、`too_short` 等

这类段落已有一个可试听的当前文件。先听它：不满意就单段重做，认可当前音频才接受警告。

```sh
sh run.sh retry work/my-book SEGMENT_ID
sh run.sh run work/my-book
```

如果试听后决定保留当前音频，使用下面这条替代重做：

```sh
sh run.sh accept-audio work/my-book SEGMENT_ID
```

`accept-audio` 仅接受当前音频的波形 QA 警告，不是“无条件通过所有问题”。它不能确认人物，也不能接受缺失、被修改或已不匹配当前配置的音频。即使音频状态已是 `DONE`，如果你听到错读或不满意，也可以 `retry` 重做。

### `generation:` 报不支持的参数

同样的配置错误不会靠换随机种子变好。先修正完整声音配置并重新导入：

| 常见情况 | 修正方法 |
| --- | --- |
| Base 里填写了 `instruct` 或预设 `speaker` | 删除这些字段；Base 使用参考音频 |
| Base strict 遇到非 neutral 情绪 | 若该句应平静，修正为 neutral；若决定不要求显式情绪控制，给该声音设置 `emotion_mode: "reference"`；需要指令控制时验证 CustomVoice |
| xvector 同时填了 `reference_text` | 删除转录字段 |
| ICL 没有准确转录或模型没有所需编码器 | 补齐真实转录与兼容模型，或明确切换 xvector 并删除转录 |
| CustomVoice 填了参考音频、`emotion_mode: "reference"` 或 xvector 模式 | 删除参考音频和转录；使用 strict，省略 `clone_mode` |
| `speaker` 名称或 `language` 不被模型支持 | 按该模型实际支持的值修改；speaker 错误会列出可用声音 |
| Qwen3-TTS 的 `speed` 不是 `1.0` | 改回 `1.0`；当前适配器没有变速能力 |
| 模型不是 Qwen3-TTS Base 或 CustomVoice | 更换受支持模型；不能仅靠改模型名接入任意 TTS |

配置实际改变后，相关片段通常自动回到待生成状态。再运行并检查 `review`；仍处于 `FAILED` 的段落需要 `retry` 重置尝试预算。

### 参考音频丢失，或者生成的 WAV 被删除、修改

这两种文件用途不同。`voices/` 中的参考音频是后续克隆的输入；`audio/` 中的 WAV 是生成结果。

参考文件缺失时，重新准备录音，在完整 cast 的对应声音里填写存在的文件路径，然后重新导入。raradio 会复制它并重新检查受影响片段。不要只改数据库中的路径，或直接用另一个文件覆盖按哈希命名的参考文件。

已完成的生成 WAV 丢失或内容改变时，正常 `run` 会检查缓存哈希并重做有效性不满足的片段。若该段原本已在复核队列，显式 `retry` 后再 `run`。`status` 是保存的状态汇总，不会单靠查询就修复磁盘文件；导出也会重新校验，拒绝把缺失音频拼成成品。

### MLX、模型加载或项目锁问题

如果提示未安装 MLX-Audio，运行 `sh setup.sh mlx`；如果已经安装却不能初始化，检查当前是否为 Apple Silicon、进程能否访问 Metal GPU。修正运行环境后重新启动命令，再对失败片段执行 `retry`。同一个进程保存过初始化失败，不适合留在原进程里反复尝试。

若模型仓库或本地路径不存在，修正 `model`，或在联网环境准备完整模型文件。离线时重复生成不会补出缺失的缓存。

如果提示另一个进程正在修改项目，先找到并结束该项目的旧生成命令，再运行新的命令。同一本书同时只允许一个写入者；不要删除 `.write.lock` 文件来绕过仍在运行的进程。

### 多次失败后怎样重新开始一段

每段默认最多尝试 3 次，重试时使用 `seed`、`seed + 1`、`seed + 2` 并记录实际种子。普通 `run` 不会无限重试 `FAILED` 或 `NEEDS_REVIEW`。

修好原因后，`retry` 会清除这段的当前生成状态并重置尝试次数，下一次 `run` 才实际合成。它不会重新分析已经成功标注的文本，也不会随机挑新的人物。如果希望另一组随机尝试，可在完整声音配置里改 `seed`；这也会影响使用该声音的其他片段。

## 整本运行、停止、续跑与重复制作

短样本确认后，执行：

```sh
sh run.sh run work/my-book
```

需要暂停时，在运行的终端按 Ctrl+C，等命令结束。下一次执行相同 `run` 继续：有效的已完成音频会跳过，未完成的生成会恢复调度；自动重试耗尽的片段仍需要处理原因后 `retry`。一次停止不要求重新 `init`、重新分析全书或重新导入角色。

`build` 是导入、可选配置、分析、生成和可选导出的组合命令，适合已明确配置的短示例。已有工作目录时，它会检查传入 TXT 与保存的原文是否相同。只是续跑正式书籍，直接用 `run` 更清楚；不要改过外部 cast 后又不经意用旧 `build --cast` 覆盖项目的新配置。

根据需要选择继续处理同一本书的方式：

| 需求 | 做法 |
| --- | --- |
| 补齐当前版本、重新导出 | 保留工作目录，继续 `run`，完成后 `export` |
| 换一个角色的声音 | 导出当前完整 cast 到工作目录内的编辑文件，改对应 `voices`，重新导入，再 `run`；受影响片段重做，其他有效音频保留 |
| 修正片段边界或章节归属 | 导出并审阅 `structure`，再导入编辑文件；未受影响的原文范围保留标注和音频。参见[结构修复](text-input.zh-CN.md) |
| 更新自动标注 | 使用 `analyze --reanalyze`；明确的人工归属保持不变 |
| 修改原文或比较独立分析 | 以 TXT 或新设置创建另一个 `--work` 目录；保留原项目供比较 |

原文导入后固定保存在 `source.txt`，打开项目会核对其哈希。需要纠正输入文本时，在项目外修改一份 TXT，再导入新项目；直接修改 `work/my-book/source.txt` 会破坏项目一致性。

“下一本书也用这套声音”可以复用 `voices` 的配置思路和参考录音，但新书仍要发现、确认自己的角色。先导出新书发现的人物，再把想复用的声音配置放进这份完整表中，重新映射各个人物。raradio 目前没有跨书角色库或自动判断“这是上一本书的同一个人”的功能。

音频缓存属于单个工作目录，不保证在不同书籍或新项目间复用。修改声音配置、参考音频、人物归属或情绪，都会改变受影响片段的生成输入；后端版本变化也会触发重新验证和生成。反过来，在同一个模型 ID 或绝对路径下原地替换权重，名称没有变化，程序不能仅凭这个名称识别权重已经换了。比较模型时应使用能区分版本的模型标识或目录，并保留配置记录。

## 复制到另一台机器继续

先正常停止生成，再复制整本书的工作目录。不要在数据库和音频仍然写入时分开抓取文件。

```text
work/my-book/
├── source.txt
├── project.json
├── cast.json
├── state.sqlite3
├── voices/
├── audio/
└── .write.lock
```

可以直接复制整个 `work/my-book/`，包括你放在其中的编辑配置或笔记。仅复制 `output/my-book/` 能继续收听，但不能恢复逐段状态、改人物或接着克隆。

在另一台机器上：

1. 准备同一版本的 raradio 源码，并在其根目录安装对应依赖；生成人声仍需要受支持的 Apple Silicon / Metal 环境。
2. 准备原来使用的模型。工作目录不包含 `.venv`、Ollama 模型或 Hugging Face 缓存；它们需要重新准备或按各自工具的方式迁移。
3. 把书籍工作目录放到方便的位置，例如新安装目录中的 `work/my-book/`。
4. 检查 `cast.json` 的 `model`。仓库 ID 可以继续使用；旧机器的模型绝对路径需要在新机器上改成存在的路径，通过完整 cast 导入。项目内的参考音频使用相对路径，正常随书迁移。
5. 查看状态，先做少量生成验证，再继续其余内容。

```sh
sh run.sh doctor --profile mlx
sh run.sh status work/my-book
sh run.sh run work/my-book --limit 3
sh run.sh review work/my-book
```

保持相同依赖、配置与模型有利于复用已有音频。改模型路径也属于配置变化，可能使相关片段重新生成；后端版本变化同样如此。复制成功不等于已验证新环境的合成结果，继续制作前抽听新生成的样本。

## 更换文本模型、TTS 模型与运行后端

这三件事控制不同阶段，改错位置不会得到期望效果：

| 想改变什么 | 修改位置 | 对已有项目的影响 |
| --- | --- | --- |
| 人物识别、对白归属、情绪标注 | `analyze` / `build` 的 `--model`、`--think` 等文本分析参数 | 用于尚未成功分析的片段；不会自动覆盖全部旧标注 |
| 声音质量、预设音色、克隆路线 | cast 的 `voices.<声音ID>.model` 及该模型支持的声音参数 | 使用这份声音的片段需重新生成 |
| 使用 MLX、另一套本地运行库或远程合成服务 | 当前为 cast 的 `backend`，新增类型还需要代码适配 | 取决于后端实现与版本；不是任意填写名称就能运行 |

### 更换 Ollama 文本模型

先用 Ollama 准备实际要用的模型，再在命令里选相应标签。例如已准备 `qwen3:8b` 时：

```sh
ollama pull qwen3:8b
sh run.sh analyze work/my-book --model qwen3:8b --think false \
  --timeout 300 --batch-size 12
```

这里给出的是参数使用方式，不是该模型的角色识别质量结论。模型必须能按 raradio 提供的 JSON schema 返回完整标注；能在聊天窗口回答问题，不代表这个契约已经验证通过。某个模型不接受 `think` 参数时，可用 `--think omit`；支持分级思考的模型可按其实际能力选择 `low`、`medium` 或 `high`。

换服务地址用 `--ollama-url http://实际主机:11434`；这只改变分析服务的位置，TTS 仍按 cast 的后端运行。使用别的主机意味着文本被提交给那个服务。默认本机地址则在本机分析。

默认情况下，`analyze` 只处理未成功分析的段落，`retry` 只重置生成。添加 `--reanalyze` 可更新当前项目中的自动标注，同时保留明确的人工归属。继续合成前应审阅变化；重分析失败或中断时，旧音频会被阻止导出。若要排除已有人工决定，独立比较两个文本模型对同一文本的标注，应从同一输入各建一个新工作目录。参见[分析与审阅](text-input.zh-CN.md)。

### 更换 TTS 模型

导出当前完整人物配置，改声音的 `model`，核对配套字段，导入后先少量生成：

```sh
sh run.sh cast work/my-book > work/my-book/cast.edit.json
```

编辑 `work/my-book/cast.edit.json` 后：

```sh
sh run.sh cast work/my-book --file work/my-book/cast.edit.json
sh run.sh run work/my-book --limit 3
sh run.sh segments work/my-book
```

当前 `mlx` 适配器只支持 Qwen3-TTS 的 Base 与 CustomVoice，要求模型输出 24 kHz 音频。即使同属 Qwen3-TTS，也不能假设其他模型类型已经接入。更换模型大小或量化版本时，仍应确认真实配置类型、支持语言、预设声音或编码器能力。

把 Base 换成 CustomVoice 时，要一并删除 `reference_audio`、`reference_text` 和 `clone_mode`，设置受支持的 `speaker`，使用 strict；反向切换则准备参考音频，明确选择 `clone_mode` 为 `icl` 或 `xvector`，并删除预设 `speaker` 与 `instruct`。ICL 还要填写准确转录，xvector 省略转录。两条路线的 `speed` 都保持 `1.0`。raradio 会拒绝不支持的能力，不会把无效字段默默当作已经生效。

### 更换运行后端或定制代码

目前可填写的后端只有 `tone` 和 `mlx`。`tone` 用于诊断；`mlx` 负责当前真实人声。接入另一套库、服务或非 Qwen TTS，需要实现和注册后端，不能只把 JSON 中的 `backend` 改成一个新名字。

例如 llama.cpp 已有 Qwen3-TTS Base 的 GGUF 路线，但其 TTS 工具仍属于实验实现，也没有接入当前 raradio。想了解独立验证方式以及它和 Ollama、MLX 的关系，见 [后端策略](backend-strategy.zh-CN.md)；当前手册里的生产命令仍使用已经接入的后端。

开发入口是 [后端实现](../raradio/backends.py)、[数据契约](../raradio/models.py) 和 [架构说明](architecture.zh-CN.md)。后端接收原文、声音配置、情绪和目标文件路径，输出可以检查的 PCM16 WAV，并提供版本标识。定制时应让不支持的能力明确报错、保持原文不变，并让版本变化能够使旧缓存失效。更详细的模型与后端选择见 [后端策略](backend-strategy.zh-CN.md)。

## 验证范围与复现

仓库提供短篇 TXT、声音配置模板和自动化测试，不分发预生成试听音频或克隆参考录音。按场景一可在不下载模型的情况下检查制作流程；按场景二可生成预设声音样本；按场景四准备自己的参考音频后可检查 xvector 克隆。生成结果保存在各命令指定的工作目录和导出目录中。

从源码根目录运行自动化测试：

```sh
python3 -W error::ResourceWarning -m unittest discover -s tests -q
```

测试覆盖文本切分、分析结果校验、人物确认、配置导入、缓存失效、重试和导出等行为；MLX 适配测试使用替代模型检查调用参数与音频处理，不衡量真实语音质量。ICL 尚未完成真实推理与试听评测，不能把契约测试通过当作音色效果验证。

项目记录的 CustomVoice 与 Base xvector 短样本运行仅用于检查模型接口与流程。短样本和波形检查均不能证明整本稳定性、人物识别准确率、逐字读音、克隆相似度或情绪表达效果。使用新的模型、录音或运行环境时，仍需生成代表性样本并试听。

ASR 回读、音色检查、EPUB 导入、MP3/M4B 导出和完整图形复核界面尚未实现。测试范围与复现方式见 [验证说明](verification.zh-CN.md)，实施方向见 [计划](plan.zh-CN.md)。

## 当前扩展方式与以后可能的插件

模型运行库可能有自己的模型类型、加载器或插件机制；这些能力不自动等于 raradio 已接入相应工作流。当前 raradio 通过代码中的分析器和后端适配器扩展，还没有可安装、自动发现和注册第三方后端的 raradio 插件市场或插件注册系统。

选择兼容模型通常先改配置；跨运行库或模型家族则需要适配代码和真实样本验证。未来若增加插件注册，也必须明确描述支持的克隆方式、参考转录、情绪、语言和输出格式。当前可用能力与后续方案的区分见 [后端策略](backend-strategy.zh-CN.md)。
