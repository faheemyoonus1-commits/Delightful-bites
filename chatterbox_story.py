#!/usr/bin/env python3
r"""
chatterbox_story.py - slow, emotional, child-friendly story reading with Chatterbox TTS.
Created by Faheem Yoonus V K, ALPS Cherukulathur East.

Reads the passages straight from your index.html (so the words are exactly the textbook
text on the site) and makes one audio file per passage: stone-01 ... stone-09, pancake-01 ... pancake-03.

SETUP (Windows PowerShell, once)
  py -3.11 -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install chatterbox-tts
RUN
  python chatterbox_story.py --dry-run                      (see the plan, makes no audio)
  python chatterbox_story.py --only stone-01 --voice female.wav
  python chatterbox_story.py --voice female.wav             (all 12 passages)

FEMALE VOICE: Chatterbox copies the voice of a short reference clip (5-15 s, clear, quiet room).
Use a female clip you recorded or have permission to use, e.g. --voice female.wav.
Without --voice it uses the built-in default voice, which may not sound female.
Needs the first run to download the model (several GB). A GPU is much faster; CPU works but is slow.
Optional --tempo 0.92 slows the finished audio a little more (needs ffmpeg installed).

READING TECHNIQUES FOR KIDS (all automatic, see delivery() below)
  1 slow pace            low cfg_weight + optional --tempo
  2 gentle lead-in        quiet pause before the story and after the last line
  3 emotion by sentence   "!" excited, "?" curious, quotes = character voice, plain = calm narrator
  4 mood per passage      sad / hopeful / playful / joyful / sleepy settings
  5 pauses                longer after a question (child can think), after "!" and before a reveal
  6 repeated refrain      "round and round / hummed a little tune" read softly like a lullaby
  7 chunking              one sentence at a time so every sentence gets its own expression
  8 same voice every time fixed random seed
"""
import argparse, json, os, re, subprocess, sys

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

# mood per passage: (exaggeration offset, cfg_weight offset). Higher exaggeration = more emotion.
STONE_MOOD = [(-0.05, -0.05), (-0.10, -0.05), (0.10, 0), (0.05, 0), (0.05, 0), (0.0, -0.05), (0.05, 0), (0.15, 0), (0.0, -0.05)]
PANCAKE_MOOD = [(0.15, 0.05), (0.20, 0.10), (0.10, 0)]

def load(name):
    s = open(HTML, encoding="utf-8").read()
    a = s.index("const %s = [" % name) + len("const %s = " % name)
    b = s.index("\n  ];", a) + 4
    txt = re.sub(r'"(image2?)"\s*:\s*"data:[^"]*"', r'"\1":""', s[a:b])
    return json.loads(txt)

def delivery(sent, mood):
    """Return (exaggeration, cfg_weight, pause_after_seconds, label) for one sentence."""
    t = sent.strip()
    exa, cfg = 0.5, 0.30                      # calm slow narrator
    quoted = bool(re.search(r'[“"”]', t))
    pause = 0.55
    label = "narration"
    if quoted:   exa, cfg, pause, label = 0.65, 0.30, 0.75, "character"
    if t.rstrip('”"’\' ').endswith("!"):  exa, pause, label = 0.85, 0.65, "excited"
    if t.rstrip('”"’\' ').endswith("?"):  exa, cfg, pause, label = 0.70, 0.35, 1.00, "question"   # time to think
    if re.search(r"round and round|hummed a little tune|little tune", t, re.I):
        exa, cfg, pause, label = 0.40, 0.20, 0.90, "lullaby"                                   # soft refrain
    if re.search(r"happily ever after|brought the villagers together|It is really delicious", t, re.I):
        pause, label = max(pause, 1.0), label + "+reveal"
    exa = min(1.2, max(0.25, exa + mood[0]))
    cfg = min(0.6, max(0.12, cfg + mood[1]))
    return round(exa, 2), round(cfg, 2), pause, label

def jobs():
    out = []
    for p, m in zip(load("STONE_SOUP_PASSAGES"), STONE_MOOD):
        out.append(("stone-%02d" % p["num"], p["title"], [x["en"] for x in p["sentences"]], m))
    for p, m in zip(load("PANCAKE_PASSAGES"), PANCAKE_MOOD):
        out.append(("pancake-%02d" % p["num"], p["title"], [x["en"] for x in p["sentences"]], m))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only"); ap.add_argument("--voice", help="reference clip of a female voice you may use")
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--tempo", type=float, default=1.0)
    ap.add_argument("--mp3", action="store_true", help="also save .mp3 (needs ffmpeg)"); ap.add_argument("--out", default="audio_chatterbox"); ap.add_argument("--seed", type=int, default=1234)
    a = ap.parse_args()
    js = [j for j in jobs() if not a.only or j[0] == a.only]
    if not js: sys.exit("No passage called %s" % a.only)

    if a.dry_run:
        for pid, title, sents, m in js:
            print("---", pid, title)
            for s in sents:
                e, c, p, l = delivery(s, m)
                print("  [%-14s exa=%.2f cfg=%.2f pause=%.2fs] %s" % (l, e, c, p, s))
        return

    import torch, torchaudio as ta
    from chatterbox.tts import ChatterboxTTS
    dev = "cuda" if torch.cuda.is_available() else ("mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu")
    print("Loading model on", dev); model = ChatterboxTTS.from_pretrained(device=dev)
    os.makedirs(a.out, exist_ok=True)
    def silence(sec): return torch.zeros(1, int(model.sr * sec))
    for pid, title, sents, m in js:
        path = os.path.join(a.out, pid + ".wav")
        if os.path.exists(path) or os.path.exists(path[:-4] + ".mp3"): print("skip", pid); continue
        print("Reading", pid, title)
        parts = [silence(0.8)]                                   # gentle lead-in
        for s in sents:
            e, c, p, _ = delivery(s, m)
            torch.manual_seed(a.seed)                            # same voice every sentence
            kw = dict(exaggeration=e, cfg_weight=c)
            if a.voice: kw["audio_prompt_path"] = a.voice
            parts += [model.generate(s, **kw).cpu(), silence(p)]
        parts.append(silence(0.6))
        wav = torch.cat(parts, dim=1)
        ta.save(path, wav, model.sr)
        if a.tempo != 1.0:
            tmp = path + ".tmp.wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-filter:a", "atempo=%s" % a.tempo, tmp], check=True)
            os.replace(tmp, path)
        if a.mp3:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-codec:a", "libmp3lame", "-q:a", "3", path[:-4] + ".mp3"], check=True)
            os.remove(path); path = path[:-4] + ".mp3"
        print("  saved", path)

if __name__ == "__main__":
    main()
