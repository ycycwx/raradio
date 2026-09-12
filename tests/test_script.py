"""Text ingestion must never silently lose or rewrite spoken source material."""

from pathlib import Path
import subprocess
import sys
import unittest

from raradio import script
from raradio.script import split_text


def split(text, max_chars=240):
    return split_text(text, max_chars=max_chars)


class SplitTextTests(unittest.TestCase):
    def assert_source_coverage(self, text, segments):
        cursor = 0
        for segment in segments:
            self.assertEqual(text[cursor:segment.start].strip(), "")
            self.assertEqual(segment.text, text[segment.start:segment.end])
            self.assertTrue(segment.text.strip())
            self.assertGreaterEqual(segment.start, cursor)
            cursor = segment.end
        self.assertEqual(text[cursor:].strip(), "")

    def test_splits_dialogue_without_rewriting_surrounding_narration(self):
        source = '  小雨说：“你好！”她又笑了。\n“明天见。”\n'
        segments = split(source)
        self.assertEqual([(s.text, s.kind) for s in segments], [
            ("小雨说：", "narration"), ("“你好！”", "dialogue"),
            ("她又笑了。", "narration"), ("“明天见。”", "dialogue"),
        ])
        self.assert_source_coverage(source, segments)
        self.assertEqual(segments, split(source))
        self.assertEqual(len({s.id for s in segments}), 4)

    def test_nested_and_multiline_quotes_remain_dialogue(self):
        source = '他说：「她说『别走。』\n所以我留下了。」\n雨停了。'
        segments = split(source)
        self.assertEqual([(s.text, s.kind) for s in segments], [
            ("他说：", "narration"),
            ("「她说『别走。』\n所以我留下了。」", "dialogue"),
            ("雨停了。", "narration"),
        ])
        self.assert_source_coverage(source, segments)

    def test_chinese_and_english_headings_start_chapters(self):
        source = '第一章 出发\n晨光。\n\nChapter 2: Arrival\n"Hello," she said.\n'
        segments = split(source)
        self.assertEqual([(s.chapter, s.chapter_title) for s in segments], [
            (1, "第一章 出发"), (1, "第一章 出发"),
            (2, "Chapter 2: Arrival"), (2, "Chapter 2: Arrival"),
            (2, "Chapter 2: Arrival"),
        ])
        self.assertEqual([s.kind for s in segments], ["narration", "narration", "narration", "dialogue", "narration"])
        self.assert_source_coverage(source, segments)

    def test_heading_inside_a_multiline_quote_does_not_start_a_chapter(self):
        source = '“书上写着：\n第二章 回来\n这不是我们的标题。”'
        segments = split(source)
        self.assertEqual([(s.chapter, s.kind, s.text) for s in segments], [(1, "dialogue", source)])

    def test_long_segments_have_bounded_length_and_complete_coverage(self):
        source = '开头。' + '很长的旁白还有一些空 格，' * 11 + '“' + '对话。' * 31 + '”'
        segments = split(source, max_chars=17)
        self.assertGreater(len(segments), 5)
        self.assertTrue(all(len(s.text) <= 17 for s in segments))
        self.assertEqual([s.index for s in segments], list(range(len(segments))))
        self.assert_source_coverage(source, segments)

    def test_unterminated_and_adjacent_quotes_do_not_drop_text(self):
        source = '“甲。”“乙。” 尾声“未完成\n仍在说'
        segments = split(source)
        self.assertEqual([s.kind for s in segments], ["dialogue", "dialogue", "narration", "narration"])
        self.assertTrue(segments[2].parse_issues)
        self.assertFalse(segments[3].parse_issues)
        self.assert_source_coverage(source, segments)

    def test_japanese_headings_keep_original_titles_and_create_chapters(self):
        source = '第１話　出会い\n雨。\n第二節：再会\n雪。\n第三巻 帰郷\n風。\n終章\n晴れ。'
        segments = split(source)
        self.assertEqual([(s.chapter, s.chapter_title) for s in segments], [
            (1, '第１話　出会い'), (1, '第１話　出会い'),
            (2, '第二節：再会'), (2, '第二節：再会'),
            (3, '第三巻 帰郷'), (3, '第三巻 帰郷'),
            (4, '終章'), (4, '終章'),
        ])
        self.assert_source_coverage(source, segments)

    def test_prose_starting_with_chapter_number_is_not_a_heading(self):
        source = '第一章を読み終えた。\n第二章にも猫が出てきた。'
        segments = split(source)
        self.assertEqual([(s.chapter, s.chapter_title) for s in segments], [
            (1, 'Main text'), (1, 'Main text'),
        ])

    def test_chapter_detection_can_be_disabled_without_rewriting_source(self):
        source = '第一章 出発\n雨。\nChapter 2: Arrival\n雪。'
        self.assertIn('chapter_mode', __import__('inspect').signature(split_text).parameters)
        segments = split_text(source, chapter_mode='none')
        self.assertEqual([(s.chapter, s.chapter_title) for s in segments], [(1, 'Main text')] * 4)
        self.assert_source_coverage(source, segments)
        with self.assertRaisesRegex(ValueError, 'chapter_mode'):
            split_text(source, chapter_mode='guess')

    def test_unclosed_quote_does_not_swallow_later_chapters_or_dialogue(self):
        source = '「閉じ忘れた。\n第二章　翌朝\n彼女は目を覚ました。\n「おはよう」'
        segments = split(source)
        self.assertEqual([(s.chapter, s.kind, s.text) for s in segments], [
            (1, 'narration', '「閉じ忘れた。'), (2, 'narration', '第二章　翌朝'),
            (2, 'narration', '彼女は目を覚ました。'), (2, 'dialogue', '「おはよう」'),
        ])
        self.assertTrue(segments[0].parse_issues)
        self.assert_source_coverage(source, segments)

    def test_mismatched_nested_quote_reports_issue_and_recovers_after_outer_close(self):
        source = '「本には『猫と書いてある。」\n彼女は本を閉じた。\n第二章　翌朝\n朝になった。'
        segments = split(source)
        self.assertEqual([(s.chapter, s.kind) for s in segments], [
            (1, 'dialogue'), (1, 'narration'), (2, 'narration'), (2, 'narration'),
        ])
        self.assertTrue(segments[0].parse_issues)
        self.assertTrue(all(not s.parse_issues for s in segments[1:]))
        self.assert_source_coverage(source, segments)

    def test_unexpected_closing_quote_is_preserved_and_reported(self):
        source = '閉じ括弧だけ。」\n次の行。'
        segments = split(source)
        self.assertTrue(hasattr(segments[0], 'parse_issues'))
        self.assertTrue(segments[0].parse_issues)
        self.assertFalse(segments[1].parse_issues)
        self.assert_source_coverage(source, segments)

    def test_chunk_boundary_keeps_combining_kana_and_emoji_sequences_together(self):
        for cluster in ['か\u3099', '葛\U000e0100', '👩\u200d💻']:
            source = 'あ' * 239 + cluster + '。'
            with self.subTest(cluster=cluster):
                segments = split(source)
                self.assertEqual([s.text for s in segments], ['あ' * 239, cluster + '。'])
                self.assert_source_coverage(source, segments)

    def test_cluster_larger_than_segment_limit_is_rejected(self):
        with self.assertRaisesRegex(ValueError, '(cluster|combining|Unicode)'):
            split('か\u3099', max_chars=1)

    def test_source_segment_preserves_exact_slice_and_identity_across_annotations(self):
        self.assertTrue(hasattr(script, 'source_segment'))
        segment = script.source_segment('甲「乙」丙', 1, 4, chapter=2,
                                        chapter_title='第二章', index=3, kind='narration',
                                        parse_issues=('Needs review',))
        self.assertEqual((segment.text, segment.start, segment.end), ('「乙」', 1, 4))
        self.assertEqual(segment.parse_issues, ('Needs review',))
        original = split('甲「乙」丙')[1]
        self.assertEqual(segment.id, 'seg-6f3356b13b6e0922')
        self.assertEqual(segment.id, original.id)

    def test_cr_and_crlf_line_endings_preserve_chapter_boundaries(self):
        for newline in ['\r', '\r\n']:
            source = newline.join(['第一章 出発', '雨。', '第二章 再会', '雪。'])
            with self.subTest(newline=newline):
                segments = split(source)
                self.assertEqual([(s.chapter, s.text) for s in segments], [
                    (1, '第一章 出発'), (1, '雨。'), (2, '第二章 再会'), (2, '雪。'),
                ])
                self.assert_source_coverage(source, segments)

    def test_source_segment_rejects_invalid_ranges(self):
        self.assertTrue(hasattr(script, 'source_segment'))
        for start, end in [(-1, 1), (0, 4), (1, 1), (True, 2)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                script.source_segment('甲乙丙', start, end, chapter=1,
                                      chapter_title='Main text', index=0, kind='narration')

    def test_source_segment_rejects_manual_cuts_inside_combining_kana(self):
        for start, end in [(0, 2), (2, 4)]:
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, 'Unicode'):
                script.source_segment('甲か\u3099乙', start, end, chapter=1,
                                      chapter_title='Main text', index=0, kind='narration')

    def test_many_unmatched_closers_do_not_repeatedly_scan_the_open_quote_stack(self):
        # This malformed 60,000-character input previously took quadratic time.
        program = (
            'from raradio.script import split_text\n'
            'source = "「" * 30000 + "』" * 30000\n'
            'segments = split_text(source)\n'
            'assert "".join(s.text for s in segments) == source\n'
            'assert sum(len(s.parse_issues) for s in segments) == 60000\n'
        )
        try:
            result = subprocess.run([sys.executable, '-c', program],
                                    cwd=Path(__file__).resolve().parents[1],
                                    capture_output=True, text=True, timeout=5)
        except subprocess.TimeoutExpired:
            self.fail('Malformed quotes must not make chapter ingestion take quadratic time')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_escaped_double_quotes_do_not_end_the_dialogue(self):
        source = 'He said, "Say \\"hello\\" now." Then he left.'
        segments = split(source)
        self.assertEqual([(s.text, s.kind) for s in segments], [
            ('He said,', "narration"), ('"Say \\"hello\\" now."', "dialogue"),
            ('Then he left.', "narration"),
        ])
        self.assert_source_coverage(source, segments)

    def test_apostrophe_in_curly_single_quoted_dialogue_is_not_a_closing_quote(self):
        source = '‘I don’t know.’ She smiled.'
        segments = split(source)
        self.assertEqual([(s.text, s.kind) for s in segments], [
            ('‘I don’t know.’', "dialogue"), ('She smiled.', "narration"),
        ])
        self.assert_source_coverage(source, segments)

    def test_blank_input_returns_no_segments(self):
        self.assertEqual(split(" \t\r\n"), [])

    def test_invalid_segment_limit_is_rejected(self):
        for limit in [0, -1, True, 1.5]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                split("内容", max_chars=limit)


if __name__ == "__main__":
    unittest.main()
