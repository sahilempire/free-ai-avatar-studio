"""Unit tests for the timing logic (no media, no GPU): anchors, overlap checks, kit chunking, caption grouping."""
import pytest
from studio.timeline import make_resolver, check, AnchorError
from studio.kit import cut_points
from studio.captions import group
from studio.align import tokens

WORDS = [{"text": t, "start": s, "end": s + 0.3} for t, s in
         [("Hello,", 0.0), ("world.", 0.5), ("Hello", 2.0), ("again", 2.4), ("friends!", 2.8), ("Bye", 5.0)]]


def test_word_anchor_nth_edge_offset():
    r = make_resolver(WORDS, vo_end=5.3)
    assert r({"word": "hello"}) == 0.0                      # case and punctuation ignored
    assert r({"word": "Hello", "nth": 2}) == 2.0
    assert r({"word": "again", "edge": "end", "offset": 0.1}) == 2.8
    assert r(1.5) == 1.5 and r("vo_end") == 5.3


def test_unknown_word_explains_itself():
    r = make_resolver(WORDS, vo_end=5.3)
    with pytest.raises(AnchorError, match="not in the script"):
        r({"word": "Hello", "nth": 3})


def test_scene_and_event_anchors():
    scenes = [{"id": "a", "start": 0.0, "end": 2.0}, {"id": "b", "start": 2.0, "end": 5.3}]
    pieces = {"P": {"events": {"pop": 3.1}}}
    r = make_resolver(WORDS, 5.3, scenes, pieces)
    assert r({"scene": "b"}) == 2.0 and r({"scene": "a", "edge": "end"}) == 2.0
    assert r({"event": "P.pop", "offset": 0.5}) == 3.6


def test_overlapping_broll_is_rejected():
    tl = {"duration": 10, "broll": [{"id": "x", "start": 1, "end": 3}, {"id": "y", "start": 2.9, "end": 4}], "punch_ins": []}
    with pytest.raises(ValueError, match="overlap"):
        check(tl)
    tl["broll"][1]["start"] = 3.0                           # touching is fine
    check(tl)


def test_kit_chunks_respect_limit_and_cut_at_pauses():
    words = [{"text": f"w{i}", "start": i * 0.4, "end": i * 0.4 + 0.3} for i in range(30)]
    words[12]["start"] += 0.5; words[12]["end"] += 0.5     # a long pause before word 12
    pieces = cut_points(words, 0.0, 12.5)
    assert all(b - a <= 4.2 + 1e-9 for a, b in pieces)
    assert all(a[1] == b[0] for a, b in zip(pieces, pieces[1:])) and pieces[0][0] == 0.0 and pieces[-1][1] == 12.5
    assert any(abs(b - 4.75) < 0.3 for _, b in pieces[:-1])  # the pause was used as a cut


def test_captions_two_to_four_words_and_no_lone_word():
    ws = [{"text": t} for t in "ya nahi? Toh shayad aap cab ke liye extra pay kar rahe ho.".split()]
    caps = group(ws)
    assert [len(c) for c in caps] == [2, 4, 4, 3]           # 11 words after "ya nahi?" -> 4+4+3, never 4+4+2+1
    assert all(2 <= len(c) <= 4 for c in caps)


def test_script_tokens_shown_vs_spoken():
    assert tokens("Rapido par [₹10 lakh|das lakh] ka fine.") == [
        ("Rapido", "rapido"), ("par", "par"), ("₹10 lakh", "das lakh"), ("ka", "ka"), ("fine.", "fine")]
