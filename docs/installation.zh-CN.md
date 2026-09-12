# 安装 raradio

[English](installation.md) | 简体中文

目前支持的安装方式是使用 GitHub 源码仓库。对大多数用户，最短路径是：准备语音环境，运行安装检查，再生成一个短的单人朗读样例。Ollama 是可选项，只有使用 raradio 内置的多角色自动分析时才需要。

## 开始前确认

真实语音目前要求 Apple Silicon Mac、macOS 14 或更高版本，并且可以使用 Metal。安装 Python 包和首次下载 TTS 模型时还需要网络。原生 Windows 和 Intel Mac 暂不支持语音生成。

先[安装 uv](https://docs.astral.sh/uv/getting-started/installation/)。uv 会准备所需的 Python 版本，并在源码仓库内建立独立的 `.venv`；它不是 raradio 运行时需要常驻的服务。

## 从 GitHub 安装

```sh
git clone https://github.com/ycycwx/raradio.git
cd raradio
sh setup.sh mlx
sh run.sh setup
```

`setup.sh mlx` 会把锁定的 Python 3.11 语音依赖安装进 `.venv`。`sh run.sh setup` 是只读的解释和验证步骤，不会自行安装软件或下载模型。在仓库根目录继续使用 `sh run.sh ...`；从其他目录调用时使用 `sh /path/to/raradio/run.sh ...`。

以后更新时，请保留工作目录和本地配置，更新源码仓库，再运行 `sh setup.sh mlx`。Alpha 阶段使用新版本处理已有书籍项目前，应先查看更新记录。

## 生成第一个单人朗读样例

先在仓库根目录运行自带短篇：

```sh
sh run.sh build examples/clone.txt --work work/single \
  --analyzer single-voice --cast examples/cast.single.json --limit 3
```

第一次合成会从 Hugging Face 下载所选模型，耗时可能更长；以后会复用缓存。有意限制生成数量时，只要仍有待办，命令会以状态码 `2` 退出。试听 `work/single/audio/` 中的 WAV；声音合适后再完成并导出：

```sh
sh run.sh run work/single
sh run.sh export work/single --output output/single
```

这条路径不会安装或连接 Ollama。请保留 `work/single/`，之后可以续跑、修正片段或换声音，不必从头开始。处理自己的书时，复制并修改 `examples/cast.single.json`，再替换命令中的示例文本和路径。

## 仅在需要时增加多角色自动分析

安装并启动 [Ollama](https://ollama.com/download)，再准备默认文本模型并检查两类依赖：

```sh
ollama pull qwen3:14b
sh run.sh setup --mode multi-voice --model qwen3:14b
```

Ollama 用于推测人物、说话者和情绪，不负责生成语音；人物表和不确定台词仍需复核。如果由你已有的终端 Agent 判断归属，可以让它读取 `sh run.sh agent-guide`，并跳过 Ollama。

## 每项下载分别做什么

| 项目 | 何时需要 | 如何获得 |
| --- | --- | --- |
| raradio 源码与 CLI | 始终需要 | 从 GitHub 克隆，通过 `sh run.sh` 调用 CLI |
| Python 与 MLX-Audio 运行库 | 生成真实语音 | 由 `sh setup.sh mlx` 安装进 `.venv` |
| TTS 模型权重 | 第一次生成真实语音 | 从 Hugging Face 下载，之后缓存 |
| Ollama 程序和文本模型 | 仅内置多角色自动分析 | 通过 Ollama 单独安装和下载 |

`sh run.sh setup` 只检查依赖，不会初始化 Metal、生成语音、判断听感，也不能证明模型权重已经缓存。完整制作流程与排障请继续阅读[使用手册](handbook.zh-CN.md)。
