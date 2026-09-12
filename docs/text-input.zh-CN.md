# 小说格式、日文输入与结构修正

[English](text-input.md) | 简体中文

小说不一定有固定的章节标题、引号或人物标签。raradio 可以处理没有这些标记的 TXT，但“能读出文字”和“能自动识别章节及说话人”是不同能力。

| 输入情况 | 建议做法 | 自动处理的边界 |
| --- | --- | --- |
| 没有章节标记 | 默认作为一章；用 `--chapters none` 明确关闭标题猜测 | 不会猜测任意短行都是标题 |
| 没有对白引号，只需要听书 | 使用 `--analyzer single-voice` | 全文由 narrator 朗读，不需要人物模型 |
| 没有对白引号，需要多角色 | 使用 `--analyzer ollama`，检查角色分析结果 | 模型可以修正旁白/对白分类，但不能保证根据隐含上下文认对人物 |
| 一个片段混有多个说话人 | 用 `structure` 调整边界，再分析或用 `resolve` 指定角色 | 分析器不能改写或自动重划原文；混合片段应进入复核 |
| 缺失或错配引号 | 查看 `review` 中的 `parse:` 问题，检查结构 | 不再把后续整篇自动归为同一对白；人工确认后才能生成受影响片段 |
| 注音、排版注记、网页导航或 OCR 杂质 | 先准备独立的干净朗读稿，再导入新项目 | 当前不会自动去除注音或非朗读标记 |

## 先用单人朗读跑通

配置文件中的 narrator 必须已确认并指向一个可用声音。以下路径都是占位符：

```sh
python3 -m raradio build novel.txt --work work/novel \
  --analyzer single-voice --cast configs/cast.json --chapters none
```

没有章节或引号都不妨碍单人朗读。缺失引号产生的解析问题仍需检查；确认整段由旁白读取时，可运行 `resolve work/novel SEGMENT_ID --speaker narrator`。如果一段的边界不合理，先按下节修正。

已经运行过其他分析器的项目，使用显式重分析：

```sh
python3 -m raradio analyze work/novel --analyzer single-voice --reanalyze
python3 -m raradio run work/novel
```

`--reanalyze` 重新处理自动标注，保留人工 `resolve` 过的片段。因此，之前人工指定的角色不会自动换成旁白；需要时逐段重新 `resolve --speaker narrator`。不加该选项只处理尚未分析的片段。重新分析失败的片段会留在复核队列，旧音频不能绕过失败直接导出。

## 章节与对白只是一种初始判断

默认识别有限的中文、日文和英文标题，例如 `第一章 出发`、`第１章　出発`、`第二話 再会`、`終章`、`Chapter 2: Arrival`。编号后有标题时需要空白、冒号或受支持的分隔符。`第一章を読み終えた。` 这样的正文不应成为标题。仅有任意短行、数字或装饰线并不足以可靠识别章节。

`「…」`、`『…』` 等成对符号只提供初始分类，书名或强调词也可能使用它们。Ollama 可根据上下文把引用改回旁白，也可以把没有引号的文字标成对白。`rules` 是离线启发式模式，会把未识别为对白的文字交给旁白，不能用于可靠识别无标记对白。置信度是模型自评，不代表测得的正确率。

## 不改原文，手工调整章节和片段

先导出当前结构：

```sh
python3 -m raradio structure work/novel > structure.json
```

文件包含 `source_sha256`、`revision` 和 `segments`。保留前两个字段，只编辑片段数组。每个片段包含：

```json
{"start": 0, "end": 3, "text": "朝だ。", "chapter": 1, "chapter_title": "朝", "kind": "narration"}
```

- `start` 包含起点，`end` 不包含终点；位置按 Python Unicode 字符计数，不是 UTF-8 字节数，也不是 JavaScript UTF-16 下标。
- `text` 必须与该原文范围完全一致。可以拆分、合并片段，但不能丢失、重复或修改任何非空白字符，每段须符合项目保存的 `max_chars`。
- `chapter` 从 1 开始连续递增；同一章的 `chapter_title` 必须一致。可以给没有标题标记的原文指定章节，无需向正文插入标题。
- `kind` 为 `narration` 或 `dialogue`。它是初始分类，后续语义分析仍可修正。

应用后查看并分析新增或变化的片段：

```sh
python3 -m raradio structure work/novel --file structure.json
python3 -m raradio analyze work/novel --analyzer ollama
python3 -m raradio review work/novel
```

也可以使用 `rules`，再 `resolve` 指定已知角色。系统在写入前校验完整覆盖和版本，错误文件不会改动项目。未改变的片段保留标注与有效音频；仅调整章节归属或名称也保留人物确认和音频。边界或分类改变的片段需要重新分析，原有未处理的解析问题仍需明确复核。这个入口不修改 `source.txt`，也不会清理已不使用的旧音频文件。

章节模式和长度上限在导入时固定。续跑会复用保存的设置，显式传入不同的 `--chapters` 或 `--max-chars` 会报错。需要新的自动切分策略时导入新工作目录，或使用结构编辑。旧项目不会因为升级而自动重切分。

## 日文编码与声音语言

默认解码 UTF-8（含 BOM），也识别带 BOM 的 UTF-16/UTF-32。旧日文 TXT 可显式指定编码，例如：

```sh
python3 -m raradio init novel.txt --work work/novel --encoding cp932
```

编码会保存在项目里，后续 `build` 续跑可省略。程序不会自动猜测旧编码，也不会用替换字符静默吞掉解码错误。

新项目省略声音 `language` 时使用 `auto` 并在导入声音配置时保存。旧项目保留原来的中文默认值，避免升级时悄悄改变配音或缓存。制作日语有声书时，建议在每个声音配置中明确填写 `"language": "Japanese"`，并选择确实支持它的模型；`auto` 不保证正确识别短句或混合语言。实际语言支持由所选模型检查。

波形 QA 不能证明日文读音、人物归属或译文正确。仍需用短样本试听；离线诊断音测试不能作为日语语音质量证据。

## 日文转中文有声书

当前没有内置翻译流程。改变声音语言不会生成中文译文。最小可行路径是先翻译、统一人物译名并校对，保存独立中文朗读稿，再导入新项目。未来增加翻译功能时，需要单独保存译文、原文关联与版本，不能让人物分析器改写原文。
