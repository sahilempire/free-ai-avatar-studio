# Lip sync on Kaggle (free T4 x2)

## One-time setup
1. Create a Kaggle account and verify your phone number (needed for Internet access in notebooks).
2. **Create → New Notebook → File → Import Notebook**, then pick `kaggle/lipsync_fast.ipynb` (or `lipsync_realistic.ipynb`).
3. **Settings:** set Accelerator to **GPU T4 x2** and turn Internet **On**.

## Every reel
1. Run `studio prep -p project.json` locally. It writes `work/kit.zip`.
2. Upload it: **Datasets → New Dataset**, drop `kit.zip`, keep it **Private**. Kaggle unzips it (and may flatten the
   folders; the notebooks find files by name either way).
3. In the notebook, **Add Input** and pick the dataset.
4. Run it:
   - **Run All**, or
   - **Save Version → Save & Run All**, which keeps running after you close the tab.
5. When it finishes, download the output from the **Output** panel:
   - fast: `clips.zip` → unzip into `work/clips/`
   - realistic: `takes.zip` → unzip into `work/takes/`
6. Back on your machine: `studio post -p project.json` (fast) or `studio post --source scenes -p project.json` (realistic).

## Test first
Set `ONLY = ["c00", "c01"]` in the fast notebook's first cell. Two clips take about 20 minutes, which is enough to
check the face, the hands and the lip sync before spending 1.5 hours on the full set.

## Fixing a single clip
If one clip has a glitch (a smeared hand, say), set `ONLY = ["c07"]` and `SEEDS = {"c07": 44}` and run again. A
different seed gives a different take of the same line, and every other clip is untouched.

## GPU budget (free tier: 30 h/week)

| Job | Time |
|---|---|
| Setup + model download | ~3 min |
| Fast: 60 s of speech, both GPUs | ~1.5 h |
| Realistic: one 5 s take | ~18 min (renders one at a time on GPU 0) |
| Realistic: dub, per second of speech | ~1.2 min (fp32 on T4), both GPUs in parallel |

Kaggle can queue a run for a while before it starts. That wait doesn't count against your quota.
