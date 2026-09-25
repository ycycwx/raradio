# 第三方依赖与许可范围

[English](THIRD_PARTY.md) | 简体中文

核对日期：2026-09-12。raradio 自有代码、文档和仓库中的原创文本示例采用 [MIT](LICENSE)。这一声明不改变依赖库、模型权重、用户输入或参考录音的许可。

## 当前源码范围

核心没有第三方运行依赖。MLX 语音支持单独安装到源码环境，Ollama 是另行运行的外部服务，模型由使用者另行下载。raradio 仓库不内置第三方库源码、原生二进制、虚拟环境或模型权重。

因此，项目自身使用 MIT，同时保留各依赖原有许可；不把安装后的整个环境重新声明为 MIT。若以后复制第三方源码进入仓库，或分发含依赖、动态库、模型的一体安装包，应按实际包含的组件重新整理许可与分发要求。

## 直接使用的项目与示例模型

| 项目 | 用途 | 上游许可依据 |
| --- | --- | --- |
| MLX-Audio（版本固定在 `pyproject.toml` 中） | 可选 TTS Python 依赖 | [MIT](https://github.com/Blaizzy/mlx-audio/blob/main/LICENSE) |
| MLX / MLX Metal | Apple Silicon 推理运行库 | [MIT](https://github.com/ml-explore/mlx/blob/main/LICENSE) |
| Ollama | 外部文本推理服务 | [MIT](https://github.com/ollama/ollama/blob/main/LICENSE) |
| Qwen3-14B | 默认文本模型家族 | [Apache-2.0 模型卡](https://huggingface.co/Qwen/Qwen3-14B)；实际安装的 Ollama 标签仍应记录版本与许可 |
| Qwen3-TTS 1.7B Base 8bit | 参考音色克隆模型 | [Apache-2.0 模型卡](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit) |
| Qwen3-TTS 1.7B CustomVoice 8bit | 预设声音模型 | [Apache-2.0 模型卡](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit) |

模型 ID 只是下载配置，不代表 raradio 已获得重新许可模型的权利。更换模型后，应重新查看该具体仓库与版本的模型卡和许可证；不能把同一模型家族的许可一概外推。

llama.cpp 目前尚未接入，也不随 raradio 分发；其引擎为 [MIT](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE)，候选模型仍需分别核对。

## 间接依赖并非全部采用 MIT

核对锁文件和 Apple Silicon / Python 3.11 语音环境的安装元数据后，以下组件需要特别区分。该表用于说明许可边界，不是所有平台和所有二进制内嵌组件的完整清单。

| 组件 | 已核对版本与许可 | 分发时应区分 |
| --- | --- | --- |
| pycountry | 26.2.16，LGPL-2.1-only | 库及其数据保留原有许可；[上游项目](https://github.com/pycountry/pycountry) |
| Python-SoXR | 1.1.0，LGPL-2.1-or-later | Python 包及 libsoxr；[官方许可说明](https://python-soxr.readthedocs.io/en/latest/#credit-and-license) |
| SoundFile | 0.14.0，BSD-3-Clause | Python 包和某些 wheel 内的 LGPL libsndfile 是不同组件；[官方说明](https://python-soundfile.readthedocs.io/en/latest/) |
| certifi | 2026.7.22，MPL-2.0 | 包及证书数据按原有许可处理；[上游项目](https://github.com/certifi/python-certifi) |
| tqdm | 4.70.1，MPL-2.0 AND MIT | 各部分遵守相应条款；[上游许可](https://github.com/tqdm/tqdm/blob/master/LICENCE) |

其他已安装依赖还采用 Apache-2.0、BSD、ISC、PSF 等许可。NumPy、SciPy 等二进制包也可能附带其他组件的声明；再分发时应查看实际 wheel 内的许可证，不能只依据顶层项目标签。

LGPL 和 MPL 的存在不等于 raradio 的独立自有源码必须改成同一许可证。它们对相应库、受覆盖文件、修改及组合分发有各自要求。具体边界可参考 [LGPL 2.1 第 5–6 节](https://opensource.org/license/lgpl-2-1) 与 [Mozilla MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/)。

## 维护与再分发

升级依赖时同步核对 `uv.lock` 和目标平台实际安装的版本、许可文件与原生库；模型版本与 Python 依赖分开记录。安装元数据是核对入口，不能替代对应版本的完整许可文本。

raradio 仓库只对自有内容声明 MIT。未来若制作一体安装包或镜像，还需保留第三方版权、LICENSE、适用的 NOTICE，并按所包含版本履行相应源码提供、库替换和修改披露等义务；此文件本身不能替代那些文件或义务。

书籍、参考录音以及输出音频不因使用 raradio 就自动获得 MIT 许可。公开复现材料优先使用原创或明确授权的内容，并为第三方素材单独保留来源与授权说明。
