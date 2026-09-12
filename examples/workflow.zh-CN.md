# 复核、续跑与换声音

[English](workflow.md) | 简体中文

本页演示制作过程中会遇到的操作。需要 Python 3.11+，从源码根目录运行。全部命令使用诊断音；希望一次观看完整流程，可执行 `python3 examples/offline_workflow.py`，它会展示命令并保留独立结果目录。

文档语言不会改变原文或合成语言。下文对白保留中文，以便与自带样例准确对应。

## 先看到需要人工确认的状态

`work/manual-story` 应是新目录：

```sh
python3 -m raradio init examples/story.txt --work work/manual-story
python3 -m raradio analyze work/manual-story --analyzer rules
python3 -m raradio cast work/manual-story
python3 -m raradio review work/manual-story
```

此时旁白尚未确认，规则分析也不知道两句对白是谁说的，`NEEDS_REVIEW` 表示待办。诊断文本中的人物已明确，可以导入完整名单，代替第一次手工填写：

```sh
python3 -m raradio cast work/manual-story --file examples/cast.tone.multi.json
python3 -m raradio review work/manual-story
```

现在旁白可以生成，两句对白仍等待归属确认。对自己的书应编辑实际导出的 cast，不能用这份固定名单覆盖它。

## 给两句对白指定人物

查看 `review` 的 `text` 和 `id`。把“我们回家吧。”对应的 ID 复制到下面的 `XIAOYU_SEGMENT_ID`；把“好，明天再来。”对应的 ID 复制到 `LINZHOU_SEGMENT_ID`。这两个大写名字是占位符，不能原样执行。

```sh
python3 -m raradio resolve work/manual-story XIAOYU_SEGMENT_ID --speaker xiaoyu
python3 -m raradio resolve work/manual-story LINZHOU_SEGMENT_ID --speaker linzhou
python3 -m raradio review work/manual-story
```

两段归属确认后，复核列表应为空。`status` 仍会看到待生成片段；没有疑问不等于已经生成完成。

## 先生成一部分，再继续

```sh
python3 -m raradio run work/manual-story --limit 2
python3 -m raradio status work/manual-story
python3 -m raradio run work/manual-story
python3 -m raradio segments work/manual-story
python3 -m raradio export work/manual-story --output output/manual-story
```

限量运行返回 `2` 且有正常 JSON 时，表示仍有待办。最终 `remaining` 应为 `0`，成品在 `output/manual-story/`。再次 `run` 应复用有效的逐段 WAV。真正暂停长任务时按 Ctrl+C，等进程退出后再运行相同 `run`；耗尽重试的失败段仍需处理原因后重置。

## 听到某一句不满意，只重做这一句

从 `segments` 复制目标 ID，替换 `SEGMENT_ID`：

```sh
python3 -m raradio retry work/manual-story SEGMENT_ID
python3 -m raradio run work/manual-story
python3 -m raradio export work/manual-story --output output/manual-story
```

`retry` 清除这段当前生成状态并重置尝试预算，不重新分析人物。未改种子时，确定性诊断音可能与之前完全相同；应看生成记录与文件来判断是否重做。

真实语音若被波形检查拦下，先试听。确认保留当前文件后才用 `accept-audio`；缺失音频、人物未确认或配置错误不能靠它通过。演示脚本不会替你接受警告。

## 换一个声音，保留其他人的结果

导出当前完整配置到书籍工作目录内：

```sh
python3 -m raradio cast work/manual-story > work/manual-story/cast.edit.json
```

在本诊断例子中，把 `voices.xiaoyu.speed` 从 `1.0` 改成 `1.25`，再导入：

```sh
python3 -m raradio cast work/manual-story --file work/manual-story/cast.edit.json
python3 -m raradio status work/manual-story
python3 -m raradio run work/manual-story
python3 -m raradio export work/manual-story --output output/manual-story
```

只有使用小雨这份声音配置的片段应重新生成，其余有效音频继续复用。变速仅用于 `tone` 示例，**当前 MLX / Qwen3-TTS 必须用 `speed: 1.0`**。换真实声音时改受支持的 `speaker`，或更换参考录音和对应克隆配置。多人共享一份声音配置时，修改它会影响所有使用者。

导入是整表替换，需保留其他人物和声音。编辑文件放在书籍工作目录内，已导出的 `voices/…` 相对路径才能继续使用。

## 什么时候需要新目录

| 改动 | 工作目录 |
| --- | --- |
| 续跑、修正人物、换声音、重导出 | 原目录 |
| 改原文、改首次切分长度、比较其他分析器或模型的全量结果 | 新目录 |
| 换机器继续 | 停止后复制整个项目；另外准备运行环境和模型 |

同一路径下替换模型文件不一定改变缓存标识，比较模型时应使用可区分版本的模型路径或 ID。迁移与其他错误见 [完整手册](../docs/handbook.zh-CN.md)。
