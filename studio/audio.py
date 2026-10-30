"""Sound: voice-over + music (synthesised 92 BPM lo-fi/trap bed, or your own file) + SFX + ambience, sidechain-style
ducking under the voice, an optional music drop, mastered to -14 LUFS / -1.5 dBTP.  The VO is resampled only, never
re-timed.  Output: work/audio/mix_master.wav (+ stems)
"""
import json, subprocess
import numpy as np


def run(project):
    import soundfile as sf, librosa, pyloudnorm as pyln
    from scipy import signal
    tl = project.load("timeline.json")
    SR = 48000; DUR = tl["duration"]; N = int(round(DUR * SR)); rng = np.random.default_rng(7); meter = pyln.Meter(SR)
    t_axis = lambda sec: np.arange(int(sec * SR)) / SR
    filt = lambda x, kind, f, order=4: signal.sosfilt(signal.butter(order, f, btype=kind, fs=SR, output="sos"), x)
    def place(buf, x, t, gain=1.0):
        i = int(round(t * SR))
        if 0 <= i < len(buf): x = x[: len(buf) - i]; buf[i: i + len(x)] += gain * x
    def to_lufs(x, target):
        l = meter.integrated_loudness(x); return x * 10 ** ((target - l) / 20) if np.isfinite(l) else x

    vo, vsr = sf.read(project.voiceover); vo = vo if vo.ndim == 1 else vo.mean(1)
    vo = librosa.resample(vo.astype(np.float64), orig_sr=vsr, target_sr=SR, res_type="soxr_vhq")
    voice = np.zeros(N); voice[: min(N, len(vo))] = vo[:N]; voice = to_lufs(voice, -16.0)

    m = tl["music"]
    if m.get("file"):                                                  # your own track, looped to length
        y, msr = librosa.load(m["file"], sr=SR, mono=False); y = y if y.ndim == 2 else np.stack([y, y])
        reps = int(np.ceil(N / y.shape[1])); music = np.tile(y, reps)[:, :N].T
    else:
        music = synth_music(m["bpm"], N, SR, DUR, m.get("harder_from"), rng, t_axis, filt, place)
    music = to_lufs(music, -20.0)
    g = np.ones(N)
    if m.get("drop"):
        a, b = int(m["drop"][0] * SR), int(m["drop"][1] * SR); fade = int(0.03 * SR)
        g[max(0, a - fade): a] = np.linspace(1, 0, a - max(0, a - fade)); g[a: b] = 0
        g[b: int((m["drop"][1] + 4 * 60 / m["bpm"] * 2) * SR)] *= 10 ** (2 / 20)
    end = int(tl["vo_end"] * SR); g[end:] *= np.linspace(1, 0, N - end)
    music *= g[:, None]
    env = filt(np.abs(voice), "low", 12, 2); env /= max(env.max(), 1e-9)
    sc = np.zeros(N); v = 0.0; att, rel = np.exp(-1 / (0.015 * SR)), np.exp(-1 / (0.30 * SR))
    for i in range(0, N, 48):
        x = env[i]; v = x + (v - x) * (att if x > v else rel) ** 48; sc[i: i + 48] = v
    music *= (10 ** (-7.0 * np.clip(sc / 0.15, 0, 1) / 20))[:, None]

    sfx = np.zeros((N, 2)); MAKE = sfx_bank(SR, rng, t_axis, filt, signal)
    for e in tl["sfx"]:
        make, gain = MAKE[e["kind"]]; x = make(); x = x / np.abs(x).max()
        lead = 0.18 if e["kind"].startswith("whoosh") else 0.0; pan = 0.5 + (0.25 * np.sin(e["t"]) if lead else 0)
        st = np.stack([x * np.sqrt(1 - pan), x * np.sqrt(pan)], 1); i = int(round((e["t"] - lead) * SR))
        if i < N: st = st[: N - i]; sfx[max(i, 0): i + len(st)] += gain * st[max(0, -i):]
    amb = np.zeros((N, 2))
    for s in tl["scenes"]:
        kind = s.get("ambience", "none")
        if kind == "none": continue
        a, b = int(s["start"] * SR), min(N, int(s["end"] * SR)); L = b - a
        base = filt(rng.standard_normal((L, 2)).T, "low", 180 if kind == "cab" else 500, 2).T
        if kind != "cab":
            hiss = filt(rng.standard_normal((L, 2)).T, "band", [600, 3000], 2).T * 0.4
            swell = 0.6 + 0.4 * np.sin(2 * np.pi * np.arange(L) / SR / rng.uniform(3, 6)) ** 2
            base = base + hiss * swell[:, None]
        ramp = np.minimum(1, np.minimum(np.arange(L), L - np.arange(L)) / (0.25 * SR)); amb[a: b] += base * ramp[:, None]
    if np.abs(amb).max() > 0: amb = to_lufs(amb, -36.0)

    mix = voice[:, None] + music + sfx + amb
    for name, x in (("voice", voice), ("music", music), ("sfx", sfx), ("ambience", amb), ("mix_premaster", mix)):
        sf.write(project.w("audio", f"{name}.wav"), x, SR, subtype="FLOAT")
    pre, out = project.w("audio", "mix_premaster.wav"), project.w("audio", "mix_master.wav")
    probe = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", pre, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                            "-f", "null", "-"], capture_output=True, text=True).stderr
    j = json.loads(probe[probe.rindex("{"): probe.rindex("}") + 1])
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", pre, "-af",
                    f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}:"
                    f"measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true,aresample=48000",
                    "-c:a", "pcm_s24le", out], check=True)
    y, _ = sf.read(out)
    print(f"audio: {meter.integrated_loudness(y):.1f} LUFS, {len(y) / SR:.2f}s -> {out}")


def synth_music(bpm, N, SR, DUR, harder, rng, t_axis, filt, place):
    STEP = 60 / bpm / 4; BAR = STEP * 16
    CHORDS = [("A", [57, 60, 64, 67]), ("F", [53, 57, 60, 64]), ("D", [50, 53, 57, 60]), ("E", [52, 56, 59, 62])]
    ROOTS = {"A": 33, "F": 29, "D": 26, "E": 28}; hz = lambda m: 440 * 2 ** ((m - 69) / 12)
    def kick():
        t = t_axis(0.45); f = 45 + 75 * np.exp(-t / 0.03)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.16) + 0.3 * filt(rng.standard_normal(len(t)), "high", 2000) * np.exp(-t / 0.004)
    def snare():
        t = t_axis(0.3); clap = sum(np.roll(filt(rng.standard_normal(len(t)), "band", [900, 3000]) * np.exp(-t / 0.02), int(d * SR)) for d in (0, .011, .022))
        return 0.5 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05) + 0.6 * filt(rng.standard_normal(len(t)), "band", [1200, 6000]) * np.exp(-t / 0.09) + 0.35 * clap
    def hat(o=False):
        t = t_axis(0.25 if o else 0.06); return filt(rng.standard_normal(len(t)), "high", 7500) * np.exp(-t / (0.09 if o else 0.018))
    def bass808(m, L):
        t = t_axis(L); f = hz(m) * (1 + 0.25 * np.exp(-t / 0.03))
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.005) * np.exp(-t / 0.7); return np.tanh(2.2 * x) / np.tanh(2.2)
    def epiano(notes, L):
        t = t_axis(L); env = np.minimum(1, t / 0.02) * np.exp(-t / 1.6)
        x = sum(np.sin(2 * np.pi * hz(n) * t) + 0.3 * np.sin(4 * np.pi * hz(n) * t) * np.exp(-t / 0.3) for n in notes)
        return filt(x * env * (1 + 0.12 * np.sin(2 * np.pi * 4.5 * t)), "low", 2600, 2)
    def pluck(m):
        t = t_axis(0.5); return filt(np.sign(np.sin(2 * np.pi * hz(m) * t)) * np.exp(-t / 0.12), "low", 1800, 2)
    drums, bass, keys, lead = (np.zeros(N) for _ in range(4))
    KICK, KICK_HARD = {0, 7, 10}, {0, 3, 7, 10, 14}; MOTIF = [(0, 69), (3, 72), (6, 71), (8, 69), (11, 64)]
    bar, t0 = 0, 0.0
    while t0 < DUR:
        name, notes = CHORDS[bar % 4]; hard = harder is not None and t0 >= harder; ks = KICK_HARD if hard else KICK
        place(keys, epiano(notes, BAR + 0.5), t0, 0.22)
        if t0 >= 1.3:
            for s in range(16):
                ts = t0 + s * STEP + rng.normal(0, 0.003)
                if s in ks: place(drums, kick(), ts, 0.9)
                if s in (4, 12): place(drums, snare(), ts, 0.7 if hard else 0.55)
                if s % 2 == 0 or (hard and s in (13, 15)): place(drums, hat(), ts, 0.16 * rng.uniform(0.7, 1.0))
                if hard and s == 14: place(drums, hat(True), ts, 0.12)
            ss = sorted(ks)
            for i, s in enumerate(ss): place(bass, bass808(ROOTS[name], ((ss[i + 1] if i + 1 < len(ss) else 16) - s) * STEP + 0.05), t0 + s * STEP, 0.55)
            if bar % 2: [place(lead, pluck(m_), t0 + s * STEP, 0.10) for s, m_ in MOTIF]
        bar += 1; t0 += BAR
    cr = np.zeros(N); idx = rng.integers(0, N, int(DUR * 9)); cr[idx] = rng.uniform(-1, 1, len(idx))
    cr = filt(cr, "band", [800, 6000], 2) * 0.25
    L_ = drums + bass + keys + lead + cr; R_ = drums + bass + np.roll(keys, int(0.012 * SR)) + np.roll(lead, int(0.008 * SR)) + cr
    mus = np.stack([L_, R_], 1); k = int(1.3 * SR); mus[:k] *= np.linspace(0.3, 1, k)[:, None]
    return mus


def sfx_bank(SR, rng, t_axis, filt, signal):
    def whoosh(soft=False):
        L = 0.32 if soft else 0.5; t = t_axis(L); n = rng.standard_normal(len(t)); fc = 300 * 10 ** np.sin(np.pi * t / L)
        y = np.zeros_like(n); state = None
        for k in range(0, len(n), 480):
            f = float(np.clip(fc[k], 150, 8000)); s_ = signal.butter(2, [f * 0.6, f * 1.6], btype="band", fs=SR, output="sos")
            y[k: k + 480], state = signal.sosfilt(s_, n[k: k + 480], zi=state if state is not None else signal.sosfilt_zi(s_) * 0)
        return y * np.sin(np.pi * t / L) ** 2 * (0.5 if soft else 1)
    def kaching():
        t = t_axis(1.0); bell = sum(a * np.sin(2 * np.pi * f * t) * np.exp(-t / d) for f, a, d in ((2093, 1, .5), (2637, .6, .35), (3520, .4, .25)))
        return 0.5 * bell + 0.8 * filt(rng.standard_normal(len(t)), "band", [1500, 5000]) * np.exp(-t / 0.01)
    def tick():
        t = t_axis(0.06); return np.sin(2 * np.pi * 1400 * t) * np.exp(-t / 0.012)
    def thud():
        t = t_axis(0.9); f = 32 + 50 * np.exp(-t / 0.05)
        return np.tanh(1.8 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.28)) + 0.4 * filt(rng.standard_normal(len(t)), "low", 900) * np.exp(-t / 0.06)
    def click():
        t = t_axis(0.04); return np.sin(2 * np.pi * 3200 * t) * np.exp(-t / 0.006)
    return {"whoosh": (whoosh, 0.30), "whoosh_soft": (lambda: whoosh(True), 0.18), "kaching": (kaching, 0.20),
            "tick": (tick, 0.18), "thud": (thud, 0.55), "click": (click, 0.22)}
