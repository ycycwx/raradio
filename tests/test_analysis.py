"""Exercise annotation preservation and trust checks at the analyzer interface."""

import io
import json
import unittest
from dataclasses import replace
from http.client import BadStatusLine, HTTPResponse, IncompleteRead
from unittest.mock import patch
from urllib.error import URLError

from raradio import analysis
from raradio.models import Character, Segment


def analyzer(name, **kwargs):
    return getattr(analysis, name)(**kwargs)


def segment(identifier, text="“你好。”", kind="dialogue"):
    return Segment(identifier, 1, "第一章", 0, 0, len(text), text, kind)


def annotation(identifier, speaker="xiaoyu", confidence=0.96, kind="dialogue"):
    return {"id": identifier, "kind": kind, "speaker_id": speaker, "confidence": confidence,
            "emotion": "neutral", "reason": "小雨的发言"}


def response(annotations, characters=None):
    return {"annotations": annotations, "characters": characters or []}


XIAOYU = {"id": "xiaoyu", "name": "小雨", "aliases": ["雨"]}


class OllamaHTTP:
    """Only replace the external HTTP transport; real request/validation runs."""
    def __init__(self, *replies):
        self.replies = iter(replies)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(json.dumps({
            "model": "qwen3:14b", "created_at": "2026-09-12T00:00:00Z",
            "message": {"role": "assistant", "content": json.dumps(reply),
                        "thinking": "This should not be parsed as annotations."},
            "done": True, "done_reason": "stop", "total_duration": 12,
        }).encode())


class RulesAnalyzerTests(unittest.TestCase):
    def test_rules_use_initial_narration_and_leave_dialogue_for_review(self):
        source = [segment("n", "天亮了。", "narration"), segment("d")]
        result = analyzer("RulesAnalyzer").analyze(source)
        self.assertEqual([(s.speaker_id, s.confidence) for s in result.segments], [("narrator", 1.0), (None, 0.0)])
        self.assertTrue(result.segments[1].reason)
        self.assertIn("narrator", [c.id for c in result.characters])
        self.assertEqual(source[0].speaker_id, None)

    def test_preserves_input_cast_without_inventing_dialogue_speakers(self):
        cast = [Character("xiaoyu", "小雨", ("雨",))]
        result = analyzer("RulesAnalyzer").analyze([segment("d")], cast)
        self.assertIn(cast[0], result.characters)
        self.assertIsNone(result.segments[0].speaker_id)


class SingleVoiceAnalyzerTests(unittest.TestCase):
    def test_reads_narration_and_dialogue_as_narrator_without_rewriting_source(self):
        source = [
            Segment("n", 2, "第二章 雨夜", 7, 42, 46, "天亮了。", "narration"),
            Segment("d", 2, "第二章 雨夜", 8, 48, 53, "“你好。”", "dialogue",
                    speaker_id="xiaoyu", confidence=0.9, emotion="happy"),
        ]
        result = analyzer("SingleVoiceAnalyzer").analyze(source)
        self.assertEqual(
            [(s.id, s.chapter, s.chapter_title, s.index, s.start, s.end, s.text, s.kind)
             for s in result.segments],
            [("n", 2, "第二章 雨夜", 7, 42, 46, "天亮了。", "narration"),
             ("d", 2, "第二章 雨夜", 8, 48, 53, "“你好。”", "dialogue")],
        )
        self.assertEqual([(s.speaker_id, s.confidence, s.emotion) for s in result.segments],
                         [("narrator", 1.0, "neutral"), ("narrator", 1.0, "neutral")])
        self.assertTrue(all(s.reason for s in result.segments))
        self.assertEqual(result.characters, [Character("narrator", "Narrator")])
        self.assertEqual((source[1].speaker_id, source[1].emotion), ("xiaoyu", "happy"))

    def test_preserves_known_cast_including_custom_narrator(self):
        cast = [Character("narrator", "朗读者", ("讲述者",)), Character("xiaoyu", "小雨", ("雨",))]
        result = analyzer("SingleVoiceAnalyzer").analyze([], cast)
        self.assertEqual(result.segments, [])
        self.assertEqual(result.characters, cast)


class AnnotationPreservationTests(unittest.TestCase):
    def test_semantic_or_single_voice_analysis_cannot_clear_parse_issues(self):
        # Rebuilding a Segment with defaults would lose structural review gates.
        source = replace(segment("q", "「おはよう"), parse_issues=("unclosed_quote",))
        for name in ("RulesAnalyzer", "SingleVoiceAnalyzer", "OllamaAnalyzer"):
            reply = response([annotation("q", "narrator", 0.9, "narration")])
            with self.subTest(analyzer=name), patch("raradio.analysis.urlopen", OllamaHTTP(reply)):
                result = analyzer(name).analyze([source]).segments[0]
            self.assertEqual(result.parse_issues, ("unclosed_quote",))
            self.assertEqual((result.id, result.start, result.end, result.text), ("q", 0, 5, "「おはよう"))
        self.assertEqual((source.kind, source.speaker_id, source.parse_issues),
                         ("dialogue", None, ("unclosed_quote",)))


class OllamaAnalyzerTests(unittest.TestCase):
    def test_annotations_preserve_source_and_narration_identity(self):
        service = analyzer("OllamaAnalyzer")
        source = [segment("n", "天亮了。", "narration"), segment("d")]
        http = OllamaHTTP(response([annotation("d"), annotation("n", "narrator", 1.0, "narration")], [XIAOYU]))
        with patch("raradio.analysis.urlopen", http):
            result = service.analyze(source)
        self.assertEqual([s.id for s in result.segments], ["n", "d"])
        self.assertEqual([(s.speaker_id, s.confidence) for s in result.segments], [("narrator", 1.0), ("xiaoyu", 0.96)])
        self.assertEqual([(s.text, s.start, s.end, s.kind) for s in result.segments], [("天亮了。", 0, 4, "narration"), ("“你好。”", 0, 5, "dialogue")])
        self.assertIn(Character("xiaoyu", "小雨", ("雨",)), result.characters)
        self.assertIsNone(source[1].speaker_id)

    def test_unquoted_japanese_dialogue_can_correct_initial_narration(self):
        # A parser-kind override would silently discard this speaker attribution.
        source = Segment("t", 3, "第三話", 7, 40, 45, "おはよう。", "narration")
        taro = Character("taro", "太郎", ("太郎さん",))
        http = OllamaHTTP(response([annotation("t", "taro", 0.93)]))
        with patch("raradio.analysis.urlopen", http):
            result = analyzer("OllamaAnalyzer").analyze([source], [taro]).segments[0]
        self.assertEqual((result.kind, result.speaker_id, result.confidence), ("dialogue", "taro", 0.93))
        self.assertEqual(
            (result.id, result.chapter, result.chapter_title, result.index, result.start, result.end, result.text),
            ("t", 3, "第三話", 7, 40, 45, "おはよう。"),
        )
        self.assertEqual((source.kind, source.speaker_id), ("narration", None))

    def test_quoted_book_title_can_be_reclassified_as_narration(self):
        source = segment("t", "『吾輩は猫である』")
        http = OllamaHTTP(response([annotation("t", "narrator", 0.87, "narration")]))
        with patch("raradio.analysis.urlopen", http):
            result = analyzer("OllamaAnalyzer").analyze([source]).segments[0]
        self.assertEqual((result.text, result.kind, result.speaker_id, result.confidence),
                         ("『吾輩は猫である』", "narration", "narrator", 0.87))

    def test_mixed_unquoted_segment_can_request_manual_split_without_source_rewrite(self):
        source = segment("m", "太郎：行こう。花子：待って。", "narration")
        row = dict(annotation("m", None, 0), reason="複数の話者。話者ごとに手動で分割してください。")
        with patch("raradio.analysis.urlopen", OllamaHTTP(response([row]))):
            result = analyzer("OllamaAnalyzer").analyze([source]).segments[0]
        self.assertEqual((result.kind, result.speaker_id, result.confidence), ("dialogue", None, 0.0))
        self.assertEqual(result.reason, "複数の話者。話者ごとに手動で分割してください。")
        self.assertEqual(result.text, "太郎：行こう。花子：待って。")

    def test_low_confidence_narration_is_not_promoted_to_certainty(self):
        row = dict(annotation("n", "narrator", 0.3, "narration"), reason="旁白与无标记对白难以区分")
        with patch("raradio.analysis.urlopen", OllamaHTTP(response([row]))):
            result = analyzer("OllamaAnalyzer").analyze([segment("n", "行こう。", "narration")]).segments[0]
        self.assertEqual((result.confidence, result.reason), (0.3, "旁白与无标记对白难以区分"))

    def test_dialogue_may_use_the_narrator_for_a_first_person_monologue(self):
        with patch("raradio.analysis.urlopen", OllamaHTTP(response([annotation("d", "narrator", 0.91)]))):
            result = analyzer("OllamaAnalyzer").analyze([segment("d", "「私はそう思う」")]).segments[0]
        self.assertEqual((result.kind, result.speaker_id, result.confidence), ("dialogue", "narrator", 0.91))

    def test_invalid_semantic_kinds_and_narration_speakers_are_rejected(self):
        rows = [
            annotation("d", kind="other"), annotation("d", kind=None), annotation("d", kind=[]),
            annotation("d", kind="narration"), annotation("d", None, 0, "narration"),
        ]
        for row in rows:
            with self.subTest(row=row), patch("raradio.analysis.urlopen", OllamaHTTP(response([row], [XIAOYU]))):
                with self.assertRaisesRegex(ValueError, "kind|narration"):
                    analyzer("OllamaAnalyzer").analyze([segment("d")])

    def test_unknown_speakers_require_zero_confidence_and_a_review_reason(self):
        rows = [annotation("d", None, 0.9), dict(annotation("d", None, 0), reason=" ")]
        for row in rows:
            with self.subTest(row=row), patch("raradio.analysis.urlopen", OllamaHTTP(response([row]))):
                with self.assertRaisesRegex(ValueError, "confidence|reason"):
                    analyzer("OllamaAnalyzer").analyze([segment("d")])

    def test_sends_schema_and_controls_thinking_at_the_http_seam(self):
        service = analyzer("OllamaAnalyzer", model="gpt-oss:20b", base_url="http://localhost:9123/", think="low", timeout=7)
        http = OllamaHTTP(response([annotation("d", None, 0.0)]))
        with patch("raradio.analysis.urlopen", http):
            result = service.analyze([segment("d")])
        self.assertIsNone(result.segments[0].speaker_id)
        request, timeout = http.requests[0]
        payload = json.loads(request.data)
        self.assertEqual((request.full_url, timeout), ("http://localhost:9123/api/chat", 7))
        self.assertEqual((payload["model"], payload["stream"], payload["think"]), ("gpt-oss:20b", False, "low"))
        self.assertEqual(payload["format"]["properties"]["annotations"]["items"]["properties"]["id"]["enum"], ["d"])
        annotation_schema = payload["format"]["properties"]["annotations"]["items"]
        self.assertIn("kind", annotation_schema["required"])
        self.assertEqual(annotation_schema["properties"]["kind"]["enum"], ["narration", "dialogue"])
        self.assertEqual(payload["options"]["temperature"], 0)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(json.loads(payload["messages"][1]["content"])["segments"][0]["text"], "“你好。”")

    def test_unload_releases_the_configured_model_without_generating_text(self):
        service = analyzer("OllamaAnalyzer", model="qwen3:14b", timeout=9)
        received = []
        def transport(request, timeout):
            received.append((request, timeout))
            return io.BytesIO(b'{"model":"qwen3:14b","done":true,"done_reason":"unload","message":{"role":"assistant","content":""}}')
        with patch("raradio.analysis.urlopen", transport):
            service.unload()
        request, timeout = received[0]
        self.assertEqual(json.loads(request.data), {"model": "qwen3:14b", "keep_alive": 0, "stream": False})
        self.assertEqual((request.full_url, timeout), ("http://localhost:11434/api/chat", 9))

    def test_unload_failure_is_explicit_so_cli_can_warn_without_losing_analysis(self):
        service = analyzer("OllamaAnalyzer")
        with patch("raradio.analysis.urlopen", OllamaHTTP(URLError("connection refused"))), self.assertRaisesRegex(RuntimeError, "Ollama"):
            service.unload()

    def test_batches_keep_context_and_accumulate_cast(self):
        service = analyzer("OllamaAnalyzer", batch_size=1, think=None)
        source = [segment("a"), replace(segment("b", "“再见。”"), index=1, start=6, end=11)]
        http = OllamaHTTP(response([annotation("a")], [XIAOYU]), response([annotation("b")]))
        with patch("raradio.analysis.urlopen", http):
            result = service.analyze(source)
        self.assertEqual([s.speaker_id for s in result.segments], ["xiaoyu", "xiaoyu"])
        first = json.loads(http.requests[0][0].data)
        second = json.loads(http.requests[1][0].data)
        data = json.loads(second["messages"][1]["content"])
        self.assertNotIn("think", first)
        self.assertIn(XIAOYU, data["characters"])
        self.assertEqual(data["context_before"][0]["id"], "a")
        self.assertEqual(data["context_before"][0]["speaker_id"], "xiaoyu")
        self.assertEqual(json.loads(first["messages"][1]["content"])["context_after"][0]["id"], "b")

    def test_rejects_missing_duplicate_and_unknown_segment_annotations(self):
        service = analyzer("OllamaAnalyzer")
        for rows in [[], [annotation("d"), annotation("d")], [annotation("other")]]:
            with self.subTest(rows=rows), patch("raradio.analysis.urlopen", OllamaHTTP(response(rows, [XIAOYU]))), self.assertRaises(ValueError):
                service.analyze([segment("d")])

    def test_rejects_invalid_confidence(self):
        service = analyzer("OllamaAnalyzer")
        for confidence in [-0.1, 1.1, float("nan"), float("inf"), True, "0.9", None, 10 ** 400]:
            with self.subTest(confidence=confidence), patch("raradio.analysis.urlopen", OllamaHTTP(response([annotation("d", confidence=confidence)], [XIAOYU]))), self.assertRaises(ValueError):
                service.analyze([segment("d")])

    def test_rejects_unknown_speakers_and_conflicting_cast(self):
        service = analyzer("OllamaAnalyzer")
        cases = [response([annotation("d")]),
                 response([annotation("d")], [XIAOYU, XIAOYU]),
                 response([annotation("d")], [dict(XIAOYU, name="另一个人")])]
        for index, reply in enumerate(cases):
            cast = [Character("xiaoyu", "小雨")] if index == 2 else []
            with self.subTest(index=index), patch("raradio.analysis.urlopen", OllamaHTTP(reply)), self.assertRaises(ValueError):
                service.analyze([segment("d")], cast)

    def test_rejects_text_rewrites_and_invalid_model_metadata(self):
        service = analyzer("OllamaAnalyzer")
        for row in [dict(annotation("d"), text="改写"), dict(annotation("d"), emotion=["angry"]), dict(annotation("d"), reason=None)]:
            with self.subTest(row=row), patch("raradio.analysis.urlopen", OllamaHTTP(response([row], [XIAOYU]))), self.assertRaises(ValueError):
                service.analyze([segment("d")])

    def test_connection_failure_is_actionable_and_has_no_partial_result(self):
        service = analyzer("OllamaAnalyzer", batch_size=1)
        http = OllamaHTTP(response([annotation("a")], [XIAOYU]), URLError("connection refused"))
        with patch("raradio.analysis.urlopen", http), self.assertRaisesRegex(RuntimeError, "Ollama"):
            service.analyze([segment("a"), segment("b")])

    def test_truncated_http_response_is_an_actionable_transport_failure(self):
        class Socket:
            def makefile(self, mode):
                return io.BytesIO(b'HTTP/1.1 200 OK\r\nContent-Length: 100\r\n\r\n{"done":')

        service = analyzer("OllamaAnalyzer")
        for operation in (lambda: service.analyze([segment("d")]), service.unload):
            with self.subTest(operation=operation), HTTPResponse(Socket()) as reply:
                reply.begin()
                with patch("raradio.analysis.urlopen", return_value=reply), self.assertRaises(Exception) as caught:
                    operation()
                self.assertIsInstance(caught.exception, RuntimeError)
                self.assertIsInstance(caught.exception.__cause__, IncompleteRead)
                self.assertIn("Ollama request failed", str(caught.exception))

    def test_malformed_http_status_is_an_actionable_transport_failure(self):
        with patch("raradio.analysis.urlopen", OllamaHTTP(BadStatusLine("invalid status"))), self.assertRaises(Exception) as caught:
            analyzer("OllamaAnalyzer").analyze([segment("d")])
        self.assertIsInstance(caught.exception, RuntimeError)
        self.assertIsInstance(caught.exception.__cause__, BadStatusLine)

    def test_empty_input_does_not_contact_ollama(self):
        service = analyzer("OllamaAnalyzer")
        with patch("raradio.analysis.urlopen", OllamaHTTP()):
            self.assertEqual(service.analyze([]).segments, [])

    def test_duplicate_source_ids_and_unknown_kinds_are_rejected(self):
        service = analyzer("OllamaAnalyzer", batch_size=1)
        for source in [[segment("d"), segment("d")], [segment("d", kind="other")]]:
            http = OllamaHTTP(response([annotation("d")], [XIAOYU]), response([annotation("d")]))
            with self.subTest(source=source), patch("raradio.analysis.urlopen", http), self.assertRaises(ValueError):
                service.analyze(source)

    def test_incomplete_and_error_envelopes_are_explicit_failures(self):
        service = analyzer("OllamaAnalyzer")
        for envelope in [
            {"error": "model not found"},
            {"done": False, "message": {"content": json.dumps(response([annotation("d")], [XIAOYU]))}},
        ]:
            with self.subTest(envelope=envelope), patch("raradio.analysis.urlopen", return_value=io.BytesIO(json.dumps(envelope).encode())), self.assertRaises(RuntimeError):
                service.analyze([segment("d")])

    def test_duplicate_json_object_keys_cannot_hide_an_invalid_annotation(self):
        service = analyzer("OllamaAnalyzer")
        content = '{"characters": [], "annotations": [{"id": "other", "id": "d", "speaker_id": null, "confidence": 0, "emotion": "neutral", "reason": "uncertain"}]}'
        envelope = {"done": True, "message": {"content": content}}
        with patch("raradio.analysis.urlopen", return_value=io.BytesIO(json.dumps(envelope).encode())), self.assertRaises(ValueError):
            service.analyze([segment("d")])

    def test_invalid_configuration_is_rejected_before_work(self):
        for config in [{"batch_size": 0}, {"batch_size": True}, {"timeout": -1}, {"timeout": float("nan")}, {"model": ""}, {"base_url": "file:///tmp/a"}, {"think": "invalid"}]:
            with self.subTest(config=config), self.assertRaises(ValueError):
                analyzer("OllamaAnalyzer", **config)

    def test_invalid_ollama_host_or_port_is_rejected_before_transport(self):
        for url in ["http://localhost:bogus", "http://localhost:65536", "http://:11434",
                    "http://local host:11434", "http://localhost:\n11434"]:
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, "Ollama base_url"):
                analyzer("OllamaAnalyzer", base_url=url)


if __name__ == "__main__":
    unittest.main()
