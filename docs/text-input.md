# Manuscript formats, Japanese input, and structure repair

English | [简体中文](text-input.zh-CN.md)

Novels do not always have conventional headings, quotation marks, or speaker labels. raradio can read TXT without these markers. Reading the text and correctly identifying chapters or speakers are separate capabilities.

| Input | Approach | Limit |
| --- | --- | --- |
| No chapter markers | Keep one chapter; use `--chapters none` to disable heading detection | Arbitrary short lines are not assumed to be headings |
| No quotation marks, one reading voice | Use `--analyzer single-voice` | Every segment uses narrator; no analysis model is needed |
| No quotation marks, multiple voices | Use `--analyzer ollama` and inspect its annotations | Semantic classification is supported, but implicit speaker attribution is not guaranteed |
| Several speakers in one segment | Adjust boundaries with `structure`, then analyze or `resolve` | Analysis cannot rewrite or automatically split source spans; mixed segments should be reviewed |
| Missing or mismatched quotes | Inspect `parse:` findings in `review` | Affected segments require review instead of silently absorbing the rest of the book as dialogue |
| Ruby, layout notes, navigation, or OCR artifacts | Prepare a separate clean reading manuscript before import | These annotations are not automatically removed |

## A single-voice fallback

The cast must contain a confirmed narrator mapped to an available voice. Replace the example paths with your files:

```sh
python3 -m raradio build novel.txt --work work/novel \
  --analyzer single-voice --cast configs/cast.json --chapters none
```

Neither headings nor dialogue quotes are required. Parse findings from malformed quotes still need inspection. If the affected span should simply be read by the narrator, use `resolve work/novel SEGMENT_ID --speaker narrator`. Repair unsuitable boundaries first.

To switch an existing project's automatic annotations:

```sh
python3 -m raradio analyze work/novel --analyzer single-voice --reanalyze
python3 -m raradio run work/novel
```

`--reanalyze` preserves all human `resolve` decisions. Previously assigned human speakers will therefore remain; explicitly resolve them to narrator if needed. Without this option, only pending analysis is processed. Failed reanalysis blocks the affected segments for review; old audio cannot bypass that failure at export.

## Headings and quotes are initial hints

Automatic detection recognizes a limited set of Chinese, Japanese and English headings, such as `第一章 出发`, `第１章　出発`, `第二話 再会`, `終章`, and `Chapter 2: Arrival`. A title following a chapter number needs whitespace, a colon, or a supported separator. Ordinary prose such as `第一章を読み終えた。` must not become a chapter. Arbitrary short lines, bare numbers, and decorative rules are not reliable chapter markers.

Paired quotes, including `「…」` and `『…』`, provide initial classification. Book titles and emphasized words can use the same punctuation. Ollama can reclassify quotations as narration or identify unquoted speech. The offline `rules` mode is a heuristic: text it does not recognize as dialogue goes to the narrator. It cannot reliably identify unmarked speech. Model confidence is a self-assessment, not measured accuracy.

## Edit chapters and spans without changing the source

Export the current structure:

```sh
python3 -m raradio structure work/novel > structure.json
```

Keep `source_sha256` and `revision` unchanged and edit only the `segments` array. Each entry has this shape:

```json
{"start": 0, "end": 3, "text": "朝だ。", "chapter": 1, "chapter_title": "Morning", "kind": "narration"}
```

- `start` is inclusive and `end` exclusive, measured in Python Unicode characters, not UTF-8 bytes or JavaScript UTF-16 indices.
- `text` must match the source slice exactly. Split or merge spans without losing, duplicating, or rewriting non-whitespace text. Each span must fit the saved `max_chars` limit.
- Chapters start at 1 and increase without gaps. Every segment in a chapter shares its title. You can assign chapters without inserting headings into the manuscript.
- `kind` is `narration` or `dialogue`, an initial classification that semantic analysis may refine.

Apply and analyze changed spans:

```sh
python3 -m raradio structure work/novel --file structure.json
python3 -m raradio analyze work/novel --analyzer ollama
python3 -m raradio review work/novel
```

Alternatively, use `rules` followed by explicit `resolve` commands for known speakers. Full coverage and revision validation happen before mutation; invalid files leave the project intact. Unchanged spans retain annotations and valid audio. Chapter/title-only edits also preserve human attributions and audio. Boundary or kind changes require analysis again, and unresolved parse findings still require explicit review. The command never edits `source.txt` and does not delete unused old audio files.

Heading mode and size limit are fixed on import. Resume uses saved settings; explicitly passing a different `--chapters` or `--max-chars` is rejected. To use a different automatic segmentation strategy, import into a new work directory or edit the structure. Upgrading does not automatically resegment existing projects.

## Japanese encoding and voice language

Default decoding accepts UTF-8, including BOM, and detects BOM-marked UTF-16/UTF-32. Specify legacy encodings explicitly:

```sh
python3 -m raradio init novel.txt --work work/novel --encoding cp932
```

The encoding is saved and reused by subsequent `build` commands. Legacy encodings are not guessed, and decoding errors never silently insert replacement characters.

New projects default omitted voice `language` to `auto`, saved when importing the cast. Legacy projects retain their original Chinese default so upgrades do not silently change rendering or cache behavior. For Japanese audiobooks, explicitly set `"language": "Japanese"` on each voice and choose a model that supports it. `auto` does not guarantee reliable detection for short or mixed-language text. The selected model validates supported language values.

Waveform QA does not establish Japanese pronunciation, speaker attribution, or translation accuracy. Listen to short representative samples. Diagnostic-tone workflow tests are not speech-quality evidence.

## Japanese to Chinese audiobooks

Translation is not implemented. A voice language setting does not create a translated manuscript. A practical initial workflow is to translate, standardize character names, proofread, and import the Chinese reading manuscript into a separate project. An integrated translation feature would need separate target text, source alignment, and versioning; speaker analysis must not rewrite source text.
