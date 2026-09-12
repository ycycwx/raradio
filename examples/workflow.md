# Review, resume, and change voices

English | [简体中文](workflow.zh-CN.md)

This page walks through operations you may need during production. It requires Python 3.11+; run the commands from the source root. Every command here uses diagnostic tones. To see the complete workflow in one run, execute `python3 examples/offline_workflow.py`; it shows the commands and keeps a separate results directory.

Documentation language does not change the language of the source or synthesis. The dialogue below remains in Chinese so you can match it to the supplied sample exactly.

## See what needs manual confirmation

`work/manual-story` should be a new directory:

```sh
python3 -m raradio init examples/story.txt --work work/manual-story
python3 -m raradio analyze work/manual-story --analyzer rules
python3 -m raradio cast work/manual-story
python3 -m raradio review work/manual-story
```

At this point the narrator is not yet confirmed, and the rules analyzer does not know who speaks the two lines of dialogue. `NEEDS_REVIEW` indicates pending work. The characters in the diagnostic text are known, so you can import the complete cast instead of filling it in manually for the first time:

```sh
python3 -m raradio cast work/manual-story --file examples/cast.tone.multi.json
python3 -m raradio review work/manual-story
```

Narration is now ready for generation; the two dialogue lines still await speaker confirmation. For your own book, edit the cast actually exported from that book instead of replacing it with this fixed list.

## Assign characters to the two dialogue lines

Look at `text` and `id` in the `review` output. Copy the ID for “我们回家吧。” into `XIAOYU_SEGMENT_ID` below, and the ID for “好，明天再来。” into `LINZHOU_SEGMENT_ID`. These uppercase names are placeholders; do not run them literally.

```sh
python3 -m raradio resolve work/manual-story XIAOYU_SEGMENT_ID --speaker xiaoyu
python3 -m raradio resolve work/manual-story LINZHOU_SEGMENT_ID --speaker linzhou
python3 -m raradio review work/manual-story
```

Once both assignments are confirmed, the review list should be empty. `status` will still show segments awaiting generation; having no unresolved questions does not mean generation is complete.

## Generate part of the book, then continue

```sh
python3 -m raradio run work/manual-story --limit 2
python3 -m raradio status work/manual-story
python3 -m raradio run work/manual-story
python3 -m raradio segments work/manual-story
python3 -m raradio export work/manual-story --output output/manual-story
```

A limited run returning `2` with normal JSON output means work remains. Eventually `remaining` should be `0`, with the exported files in `output/manual-story/`. Running `run` again should reuse valid per-segment WAV files. To pause a real long-running job, press Ctrl+C, wait for the process to exit, and then repeat the same `run` command. Failed segments that have exhausted their retries still need their cause addressed and their state reset.

## Regenerate just one unsatisfactory line

Copy the target ID from `segments` and replace `SEGMENT_ID`:

```sh
python3 -m raradio retry work/manual-story SEGMENT_ID
python3 -m raradio run work/manual-story
python3 -m raradio export work/manual-story --output output/manual-story
```

`retry` clears the segment's current generation state and resets its attempt budget; it does not analyze its speaker again. If the seed is unchanged, deterministic diagnostic tones may sound exactly the same as before. Check generation records and files to confirm regeneration.

If waveform checks block real speech output, listen to it first. Use `accept-audio` only after deciding to keep the current file; it cannot bypass missing audio, unconfirmed characters, or configuration errors. The demonstration script does not accept warnings for you.

## Change one voice and keep everyone else's results

Export the current complete configuration into the book's working directory:

```sh
python3 -m raradio cast work/manual-story > work/manual-story/cast.edit.json
```

For this diagnostic example, change `voices.xiaoyu.speed` from `1.0` to `1.25`, then import it:

```sh
python3 -m raradio cast work/manual-story --file work/manual-story/cast.edit.json
python3 -m raradio status work/manual-story
python3 -m raradio run work/manual-story
python3 -m raradio export work/manual-story --output output/manual-story
```

Only segments using 小雨's voice configuration should regenerate; all other valid audio should be reused. The speed change is specific to this `tone` example. **Current MLX / Qwen3-TTS support requires `speed: 1.0`.** To change a real voice, change a supported `speaker`, or replace the reference recording and corresponding clone configuration. If several characters share one voice configuration, changing it affects every character using it.

Import replaces the entire table, so retain all other characters and voices. Keep the edited file inside the book's working directory so the exported `voices/…` relative paths continue to work.

## When to use a new directory

| Change | Working directory |
| --- | --- |
| Resume, correct characters, change voices, or export again | Existing directory |
| Change the source text or initial segment length, or compare complete results from another analyzer or model | New directory |
| Continue on another machine | Stop production and copy the entire project; prepare the runtime environment and models separately |

Replacing model files at the same path does not necessarily change the cache identifier. To compare models, use model paths or IDs that distinguish their versions. See the [complete handbook](../docs/handbook.md) for migration and other errors.
