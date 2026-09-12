# Third-party dependencies and license scope

English | [简体中文](THIRD_PARTY.zh-CN.md)

Last checked: 2026-09-12. raradio's own code, documentation, and original text examples in this repository use [MIT](LICENSE). This statement does not change the licenses of dependencies, model weights, user inputs, or reference recordings.

## Current source scope

The core has no third-party runtime dependencies. MLX speech support is installed separately into the checkout environment, Ollama runs as a separate external service, and users download models separately. The raradio repository does not vendor third-party library source, native binaries, virtual environments, or model weights.

The project itself therefore uses MIT while preserving the original licenses of its dependencies; it does not relicense the entire installed environment as MIT. If third-party source is later copied into the repository, or an all-in-one installer includes dependencies, dynamic libraries, or models, the licensing and distribution requirements must be reassessed for the components actually included.

## Directly used projects and example models

| Project | Purpose | Upstream license source |
| --- | --- | --- |
| MLX-Audio 0.5.3 | Optional TTS Python dependency | [MIT](https://github.com/Blaizzy/mlx-audio/blob/main/LICENSE) |
| MLX / MLX Metal | Apple Silicon inference runtime | [MIT](https://github.com/ml-explore/mlx/blob/main/LICENSE) |
| Ollama | External text inference service | [MIT](https://github.com/ollama/ollama/blob/main/LICENSE) |
| Qwen3-14B | Default text model family | [Apache-2.0 model card](https://huggingface.co/Qwen/Qwen3-14B); still record the version and license of the actual Ollama tag installed |
| Qwen3-TTS 1.7B Base 8bit | Reference voice cloning model | [Apache-2.0 model card](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit) |
| Qwen3-TTS 1.7B CustomVoice 8bit | Preset voice model | [Apache-2.0 model card](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit) |

A model ID is only download configuration; it does not mean raradio has acquired the right to relicense the model. After changing models, review the model card and license for that specific repository and version. Do not assume every model in a family has the same license.

llama.cpp is not currently integrated or distributed with raradio. Its engine uses [MIT](https://github.com/ggml-org/llama.cpp/blob/master/LICENSE); candidate models still need to be checked individually.

## Transitive dependencies are not all MIT

The following components need to be distinguished based on the lockfile and installed metadata checked in the Apple Silicon / Python 3.11 speech environment. This table explains license boundaries; it is not a complete inventory for every platform or every component embedded in binaries.

| Component | Checked version and license | Distinctions when redistributing |
| --- | --- | --- |
| pycountry | 26.2.16, LGPL-2.1-only | The library and its data retain their original licenses; [upstream project](https://github.com/pycountry/pycountry) |
| Python-SoXR | 1.1.0, LGPL-2.1-or-later | The Python package and libsoxr; [official licensing notes](https://python-soxr.readthedocs.io/en/latest/#credit-and-license) |
| SoundFile | 0.14.0, BSD-3-Clause | The Python package and LGPL-licensed libsndfile in some wheels are separate components; [official documentation](https://python-soundfile.readthedocs.io/en/latest/) |
| certifi | 2026.7.22, MPL-2.0 | Handle the package and certificate data under their original licenses; [upstream project](https://github.com/certifi/python-certifi) |
| tqdm | 4.70.1, MPL-2.0 AND MIT | Follow the applicable terms for each part; [upstream license](https://github.com/tqdm/tqdm/blob/master/LICENCE) |

Other installed dependencies also use licenses including Apache-2.0, BSD, ISC, and PSF. Binary packages such as NumPy and SciPy may include notices for additional components. When redistributing, inspect the licenses inside the actual wheel instead of relying only on the top-level project's license label.

The presence of LGPL and MPL does not by itself require raradio's independent, original source code to adopt the same license. These licenses have their own requirements for the respective libraries, covered files, modifications, and combined distributions. See [LGPL 2.1 sections 5–6](https://opensource.org/license/lgpl-2-1) and the [Mozilla MPL FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/) for those boundaries.

## Maintenance and redistribution

When upgrading dependencies, check `uv.lock` alongside the versions, license files, and native libraries actually installed on the target platform. Record model versions separately from Python dependencies. Installation metadata is a starting point for review, not a substitute for the full license text for the relevant version.

The raradio repository declares MIT only for raradio's own content. A future all-in-one installer or image must also retain third-party copyright notices, LICENSE files, and applicable NOTICE files, and meet the relevant obligations for the included versions, such as source provision, library replacement, and disclosure of modifications. This file cannot replace those files or obligations.

Books, reference recordings, and output audio do not automatically acquire an MIT license through the use of raradio. Prefer original or explicitly authorized content for public reproduction materials, and retain separate provenance and authorization notices for third-party assets.
