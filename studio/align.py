"""Word timings for captions and anchors: force-aligns the EXACT script to the voice-over.

Script lines are plain text. When an on-screen word is spoken differently, write [shown|spoken]:
    "September [2026|do hazaar chhabbees] mein [₹10 lakh|das lakh] ka fine laga."
Uses the MMS CTC aligner (ctc-forced-aligner, ONNX, CPU). NOTE: the MMS alignment model is licensed
CC-BY-NC 4.0 (non-commercial); see CREDITS.md.  Output: work/words.json
"""
import re


def tokens(line):
    """On-screen words of a script line, each paired with the words actually spoken."""
    out = []
    for m in re.finditer(r"\[([^|\]]+)\|([^\]]+)\]|(\S+)", line):
        shown = m.group(1) or m.group(3)
        spoken = m.group(2) or re.sub(r"[^\w']", " ", m.group(3)).replace("'", " ")
        out.append((shown, " ".join(spoken.lower().split())))
    return out


def norm(s):
    return re.sub(r"[^\w₹+]", "", s).lower()


def run(project):
    import ctc_forced_aligner as cfa
    script = project.get("script", "lines")
    assert script, "project.json needs script.lines"
    language = project.get("script", "language", default="eng")
    keys = {k.lower() for k in project.get("script", "key_words", default=[])}

    display, spoken = [], []
    for li, line in enumerate(script):
        for shown, sp in tokens(line):
            d = len(display); display.append({"text": shown, "line": li})
            spoken += [(w, d) for w in sp.split()]
    model = cfa.AlignmentSingleton()
    audio = cfa.load_audio(project.voiceover)
    emissions, stride = cfa.generate_emissions(model.alignment_model, audio, batch_size=4)
    toks, text_starred = cfa.preprocess_text(" ".join(w for w, _ in spoken), romanize=True, language=language)
    segments, scores, blank = cfa.get_alignments(emissions, toks, model.alignment_tokenizer)
    stamps = cfa.postprocess_results(text_starred, cfa.get_spans(toks, segments, blank), stride, scores)
    assert len(stamps) == len(spoken), f"aligner returned {len(stamps)} words for {len(spoken)}"
    for (_, d), s in zip(spoken, stamps):
        it = display[d]
        it["start"] = min(it.get("start", 1e9), round(s["start"], 3)); it["end"] = max(it.get("end", 0), round(s["end"], 3))
    # key words (single words or two-word phrases such as "case closed")
    for i, it in enumerate(display):
        bare = re.sub(r"[^\w₹+ ]", "", it["text"]).strip().lower()
        pair_next = f"{bare} {norm(display[i + 1]['text'])}" if i + 1 < len(display) else ""
        pair_prev = f"{norm(display[i - 1]['text'])} {bare}" if i else ""
        it["key"] = bare in keys or pair_next in keys or pair_prev in keys
    project.save("words.json", display)
    print(f"aligned {len(display)} on-screen words -> {project.w('words.json')}")
    return display
