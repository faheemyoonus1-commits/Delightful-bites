#!/usr/bin/env python3
"""
voice.py - Emotional ElevenLabs narration for Unit 4 "Delightful Bites".

Creates one MP3 per passage (nine Stone Soup parts, six Runaway Pancake
scenes) plus audio/index.json that lists every file.

Created by Faheem Yoonus V K, ALPS Cherukulathur East.

SETUP
  1. pip install requests
  2. Put your key in an environment variable. Never paste it into this file.
       Windows PowerShell:  $env:ELEVENLABS_API_KEY = "your-key"
       Mac / Linux:         export ELEVENLABS_API_KEY="your-key"
  3. python voice.py                 (all passages)
     python voice.py --only stone-01 (one passage, good for a first test)
     python voice.py --list          (show passages, no credits used)
     python voice.py --dry-run       (show the text that would be sent)

NOTES
  * Each passage is a short retelling written for Class 4 learners, with
    emotion tags such as [softly] and [excited]. Tags need a model that
    supports them (eleven_v3 by default; set ELEVENLABS_MODEL to change).
  * Every passage uses credits. Existing files are skipped, so you can
    re-run safely after a failure or a rate limit.
  * VOICE_ID below is a library voice. If your account cannot use it, add
    it to "My Voices" on elevenlabs.io or set ELEVENLABS_VOICE_ID.
"""

import argparse
import json
import os
import sys
import time

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("Please run:  pip install requests")

API_ROOT = "https://api.elevenlabs.io/v1/text-to-speech"
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "7wlfJf72PCt9FjPj0Beg")
MODEL_ID = os.environ.get("ELEVENLABS_MODEL", "eleven_v3")
OUT_DIR = os.environ.get("VOICE_OUT_DIR", "audio")
PAUSE_SECONDS = 4  # gap between requests, kind to free-plan rate limits

# Slightly more expressive than the default; lower stability = more emotion.
VOICE_SETTINGS = {"stability": 0.35, "similarity_boost": 0.8, "style": 0.6, "use_speaker_boost": True}

# id, title, emotion-tagged narration (own retelling, not the textbook text)
PASSAGES = [
    ("stone-01", "The Stone Soup 1 - The Journey",
     "[gently, with a tired sigh] It was a hot, sunny day. A young traveller walked into a village. "
     "[weary] He was exhausted, and so very hungry. [softly, worried] But the streets were empty. "
     "Every door and every window was shut. [sadly] The village did not feel like a friendly place."),
    ("stone-02", "The Stone Soup 2 - The Hope",
     "[hopeful] At last, he found a small cottage, and he knocked. [curious] An old woman peeped out. "
     "[politely, pleading] Please, could you give me something to eat? "
     "[sadly, firmly] Oh, we are very poor, she said. We barely have enough for ourselves. "
     "[quietly] And she closed the door."),
    ("stone-03", "The Stone Soup 3 - The Soup Stone",
     "[playfully] The traveller took a round stone from his bag, and knocked again. "
     "[irritated] What now? asked the old woman. "
     "[proud, confident] I am going to make stone soup! It is delicious! "
     "[giggling] Stone soup? How can you make soup from a stone? "
     "[smiling] Oh yes, I can! He looked so sure that she let him in."),
    ("stone-04", "The Stone Soup 4 - The Delicious Dish",
     "[calmly, cheerful] Fill the pot with water, and put it on the fire, said the traveller. "
     "The water began to bubble. He washed the big round stone, and dropped it in. "
     "[humming softly] He stirred, and stirred, and hummed a little tune. "
     "[excited whisper] It is almost ready! A pinch of salt and a bit of butter would make it better!"),
    ("stone-05", "The Stone Soup 5 - The Ingredients",
     "[eagerly] Is the soup ready? asked the old woman. [teasing] Not yet! "
     "An onion or two would make it tastier. She sliced the onions into the pot. "
     "[amazed] The lovely smell floated out of the window, and a neighbour came to see. "
     "[surprised] Stone soup? I have never heard of it! "
     "[cheerful] Do you have anything to add? Yes! I have turnips and beans! And he ran home to fetch them."),
    ("stone-06", "The Stone Soup 6 - The Curiosity",
     "[whispering excitedly] Soon, the whole village was talking about the strange soup. "
     "One by one, people followed the delicious smell. [teasing] Is it ready? Not yet! "
     "A carrot or two would make it tastier. [cheerful] I will get some from my garden! "
     "said a young woman. She chopped the fresh carrots, and added them to the pot. "
     "[humming softly] The traveller stirred, and hummed a little tune."),
    ("stone-07", "The Stone Soup 7 - The Happiness",
     "[warmly] Is this soup ready? asked another villager. [playfully] Oh, not yet! "
     "Chicken would make it taste even better. [delighted] An old farmer hurried home, "
     "and brought a chicken. The old woman and the traveller cut it, and put it in the pot with "
     "the carrots, the onions and the stone. [happily] Finally, the traveller sprinkled in some spices, "
     "and stirred, and hummed his little tune."),
    ("stone-08", "The Stone Soup 8 - The Tasty Soup",
     "[joyful] After a few minutes, the traveller smiled and licked his lips. "
     "It smells good, and it tastes good! Now the soup is ready to serve! "
     "[bustling] The old woman hurried to bring bowls. The traveller took the stone out, cleaned it, "
     "and put it in his pocket. He poured the soup into the bowls. "
     "[thrilled] The villagers tasted it, and cried, It is really delicious!"),
    ("stone-09", "The Stone Soup 9 - The Realisation",
     "[curious] We would love to make this soup, too! Where can we get such a magic stone? "
     "[gently, smiling] The traveller smiled, and showed the stone. "
     "Look, it is just an ordinary stone. The soup tasted good because of all the vegetables and "
     "chicken that you shared. [amazed] The villagers were surprised. "
     "[warmly, happily] Making the soup brought them together. From that day, they shared their food, "
     "and lived happily ever after."),
    ("pancake-01", "The Runaway Pancake 1 - A busy kitchen",
     "[excited] Mother is making a pancake, and the whole family gathers around! "
     "[eager] I will eat first! It will be delicious! It looks so crispy! "
     "Mom, you are making my favourite dish!"),
    ("pancake-02", "The Runaway Pancake 2 - It jumps",
     "[suddenly, shocked] All of a sudden, the pancake jumped out of the pan! "
     "[shouting] Oh! The pancake jumped out! Catch it! [urgent] OK, I will catch it! Stop there!"),
    ("pancake-03", "The Runaway Pancake 3 - The dog",
     "[panicked, out of breath] Help! Help! The pancake ran as fast as it could. "
     "[curious, friendly] A dog asked, Why are you running? "
     "[gasping] The seven children, their father and mother are following me! "
     "And the dog joined the chase."),
    ("pancake-04", "The Runaway Pancake 4 - The cat and the goat",
     "[cheerful] Hey, why are you running? asked a cat. The pancake gasped, "
     "The children, their parents and the dog are following me! The cat ran, too. "
     "[friendly] Hello, friend, what happened? asked a goat. "
     "[frightened] They are going to eat me! And the goat joined the chase."),
    ("pancake-05", "The Runaway Pancake 5 - The fox",
     "[slyly, softly] Why are you running? asked a fox. "
     "[desperate] Everyone is going to catch me! Can you give me a place to hide? "
     "[mischievous whisper] Of course, said the fox. Come here. [pause] "
     "[gulp] Yummy, yummy!"),
    ("pancake-06", "The Runaway Pancake 6 - It is gone",
     "[disappointed, sighing] The family looked all around. Oh! It is gone! "
     "[laughing softly] And the fox licked his lips. "
     "[gently] Moral: be careful whom you trust."),
]


def parse_args():
    p = argparse.ArgumentParser(description="Generate emotional narration for Unit 4 with ElevenLabs.")
    p.add_argument("--only", help="generate one passage by id, for example stone-01")
    p.add_argument("--list", action="store_true", help="list passages and exit")
    p.add_argument("--dry-run", action="store_true", help="print the text, send nothing")
    p.add_argument("--force", action="store_true", help="regenerate files that already exist")
    return p.parse_args()


def synthesize(api_key, text):
    url = f"{API_ROOT}/{VOICE_ID}?output_format=mp3_44100_128"
    body = {"text": text, "model_id": MODEL_ID, "voice_settings": VOICE_SETTINGS}
    headers = {"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"}
    return requests.post(url, headers=headers, json=body, timeout=120)


def main():
    args = parse_args()
    chosen = [p for p in PASSAGES if not args.only or p[0] == args.only]
    if not chosen:
        sys.exit("No passage with id '%s'. Use --list to see ids." % args.only)

    if args.list:
        for pid, title, text in PASSAGES:
            print(f"{pid:12} {title}  ({len(text)} characters)")
        return

    if args.dry_run:
        for pid, title, text in chosen:
            print(f"--- {pid}: {title}\n{text}\n")
        return

    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        sys.exit("Set ELEVENLABS_API_KEY first (see the setup notes at the top of this file).")

    os.makedirs(OUT_DIR, exist_ok=True)
    index = []
    failures = 0
    for n, (pid, title, text) in enumerate(chosen, 1):
        path = os.path.join(OUT_DIR, pid + ".mp3")
        entry = {"id": pid, "title": title, "file": path.replace(os.sep, "/"), "text": text}
        if os.path.exists(path) and not args.force:
            print(f"[{n}/{len(chosen)}] skip   {pid} (already exists)")
            index.append(entry)
            continue
        print(f"[{n}/{len(chosen)}] making {pid}: {title}")
        try:
            r = synthesize(api_key, text)
        except requests.RequestException as err:
            print("   network error:", err)
            failures += 1
            continue
        if r.status_code == 200:
            with open(path, "wb") as f:
                f.write(r.content)
            index.append(entry)
            print(f"   saved {path} ({len(r.content) // 1024} KB)")
        else:
            failures += 1
            msg = r.text[:300].replace("\n", " ")
            print(f"   failed ({r.status_code}): {msg}")
            if r.status_code in (401, 403):
                print("   Check the API key, and that this voice is in your account.")
                break
            if r.status_code == 429:
                print("   Rate or plan limit reached. Re-run later; finished files are kept.")
                break
        time.sleep(PAUSE_SECONDS)

    with open(os.path.join(OUT_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"Done. {len(index)} file(s) listed in {OUT_DIR}/index.json, {failures} failure(s).")


if __name__ == "__main__":
    main()
