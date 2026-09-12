# 依赖、版本与源码更新

[English](maintenance.md) | 简体中文

raradio 目前通过 GitHub 源码仓库分发，包含一个精简的标准库核心和可选语音栈。用户支持路径见[安装指南](installation.zh-CN.md)。

## 给熟悉 JavaScript 的开发者

| 文件或工具 | 在 raradio 中的作用 | 大致对应 JavaScript |
| --- | --- | --- |
| `pyproject.toml` | 项目元数据、Python 版本、直接依赖、CLI 入口和本地构建配置 | `package.json` |
| `uv.lock` | 精确解析的 Python 包、平台条件与产物哈希 | `pnpm-lock.yaml` |
| `.python-version` | 源码仓库默认 Python 小版本：3.11 | `.nvmrc` |
| `uv sync --locked` | 按锁文件创建或更新 `.venv`，锁文件需要变化时失败 | 冻结锁文件安装 |
| `.venv` | 独立的 Python 与依赖环境，永不提交 | 项目级运行环境 |
| `uv` | 源码仓库使用的项目、Python、环境和依赖管理器 | pnpm 加 Python/版本管理器 |

只从源码使用时，`pyproject.toml` 仍然需要保留：uv 通过它安装当前项目、在 `.venv` 中提供 `raradio` 命令，并选择可选的 `mlx` 依赖。uv 会从公共包索引下载 Python 依赖，但 raradio 本身来自 GitHub。

## 安装约定

- 核心没有第三方 Python 运行依赖，需要 Python 3.11+ 与 POSIX 文件锁（`fcntl`）；原生 Windows 暂不支持。
- 真实语音在原生 Apple Silicon macOS 上使用 `mlx-audio[tts]==0.5.3`。锁定环境要求 macOS 14 或更高，推荐 Python 3.11。
- `sh setup.sh mlx` 会先检查平台，再解析包并安装锁定环境；`sh setup.sh core` 只准备无模型流程。
- 模型权重单独下载，不存入仓库或锁文件。依赖安装后仍需可用的 GPU/Metal 与足够内存。
- Ollama 只有选择其分析器时才需要。当前 PCM16 单声道 WAV 流程不强制依赖 FFmpeg。

锁文件包含公开依赖地址与可选依赖解析。不要提交个人软件源、凭据、本机路径或整台机器的 `pip freeze`。书籍项目（`work/`）应与 `.venv` 分离；重建环境不能重建书籍。

## 更新依赖

尽量每次只更新一个直接依赖：

```sh
uv lock --upgrade-package PACKAGE --index-url https://pypi.org/simple
uv lock --check
sh setup.sh core
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests -v
```

修改锁定的 `mlx-audio` 版本时，先更新 `pyproject.toml`，再重新生成锁文件，并复核适配器、上游兼容性和许可证。涉及语音的改动还需运行 `sh setup.sh mlx`、`uv pip check`，并按[测试与验证](verification.zh-CN.md)完成真实短样。

Dependabot 每月提出 GitHub Actions 与 uv 生态更新，不会自动合并或发布任何内容。

## 版本与项目格式规则

`raradio/__init__.py::__version__` 是唯一手写的应用版本，CLI 会报告它，uv 缓存键也包含该文件。Alpha 阶段使用 `0.MINOR.PATCH`：兼容修复增加 patch；有意破坏 CLI、JSON、cast 或项目格式时增加 minor，并明确记录。

书籍项目另有 `schema_version`。raradio 会拒绝不支持的 schema，目前没有自动迁移。修改 schema 前应提供明确迁移方式，或说明用户需要新建工作目录。使用更新的 Alpha 版本处理已有项目前先备份。

## 源码更新检查清单

1. 行为、schema、依赖、模型或平台变化同步写入两份更新记录。
2. 运行 `uv lock --check`、全部无模型测试、Shell 语法检查和 `git diff --check`。
3. 在干净源码仓库运行公开无模型示例；语音代码有变化时，另在受支持硬件上验证真实短样。
4. 检查跟踪文件，不得包含凭据、个人路径、书籍、录音、模型权重、生成音频、数据库或环境目录。
5. 只有目标提交通过所需检查后才创建 Git 标签或 GitHub Release；该流程不包含向包仓库发布。

当前更新记录仍为 **Unreleased**。计划中的 CI 覆盖与实际记录的本地或托管验证应分别说明。
