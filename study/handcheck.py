"""Human review of coding: a random sample plus every unit the extraction gate escalated.

Also the learning edge: brand-name fixes confirmed here are saved to aliases.json,
which the analysis applies on every run.
"""
import csv
import json
import random

from .env import ROOT
from .gates import norm_text

ALIASES = ROOT / "study" / "aliases.json"
FIELDS = ["id", "answer", "extracted_brands", "check_failed", "correct", "alias_fix", "notes"]


def draw(store, n=100, seed=42):
    path = store.dir / "handcheck.csv"
    if path.exists():
        print(f"{path} already exists; delete it first to draw a new sample")
        return
    answers = {a["id"]: a["answer"] for a in store.load("answers")}
    codings = store.load("codings")
    escalated = [c for c in codings if c.get("check_failed")]
    passed = [c for c in codings if not c.get("check_failed")]
    random.Random(seed).shuffle(passed)
    rows = escalated + passed[:n]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        for c in rows:
            w.writerow({"id": c["id"], "answer": answers.get(c["id"], ""),
                        "extracted_brands": "; ".join(f"{b['brand']} ({b['stance']})" for b in c["brands"]),
                        "check_failed": "; ".join(c.get("check_failed", [])),
                        "correct": "", "alias_fix": "", "notes": ""})
    print(f"wrote {len(rows)} rows ({len(escalated)} escalated, {min(n, len(passed))} random) to {path}")
    print("Fill 'correct' with y or n (n = any brand missing, extra, or wrong stance).")
    print("If a brand name should be merged, write it in 'alias_fix' as  AirPods=Apple; Beats by Dre=Beats")


def _rows(store):
    path = store.dir / "handcheck.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def score(store):
    """Accuracy on the random sample only (escalated rows would bias it downward).

    'correct' is the human check; 'precheck' is the AI audit. They are reported separately
    and never merged, so the summary can say exactly who validated the coding.
    """
    rows = [r for r in _rows(store) if not r["check_failed"]]
    if not rows:
        return None
    out = {}
    for col, prefix in (("correct", ""), ("precheck", "ai_")):
        marks = [(r.get(col) or "").strip().lower() for r in rows]
        marks = [m for m in marks if m in ("y", "n")]
        if marks:
            out[prefix + "checked"], out[prefix + "accuracy"] = len(marks), marks.count("y") / len(marks)
    return out or None


def review(store, target=30):
    """Walk the human through the sample one answer at a time, saving after every mark.

    The AI audit's verdict is not shown, so the human judgement stays independent.
    """
    path, rows = store.dir / "handcheck.csv", _rows(store)
    if not rows:
        print("No handcheck.csv yet: run  python -m study handcheck  first")
        return
    fields = list(rows[0].keys())
    done = sum(r["correct"].strip().lower() in ("y", "n") for r in rows)
    print(f"{done} of {target} answers checked so far. Keys: y = coding correct, n = something wrong, "
          "s = skip, q = save and quit.\n")
    for i, r in enumerate(rows, 1):
        if done >= target:
            break
        if r["correct"].strip().lower() in ("y", "n"):
            continue
        print("=" * 80, f"\nAnswer {done + 1} of {target}   (row {i}, {r['id'].split('|')[0]})\n", "=" * 80, sep="")
        print(r["answer"].strip(), "\n")
        print("-" * 80, "\nBRANDS THE CODER FOUND (in order):")
        for b in r["extracted_brands"].split("; "):
            print("  -", b)
        print("\nCorrect = every brand offered as an option is 'recommended', shops/review sites/integrations are\n"
              "'mentioned', brands the answer advises against are 'warned_against', nothing missing or invented.")
        while True:
            k = input("Is the coding correct? [y/n/s/q] ").strip().lower()
            if k in ("y", "n", "s", "q"):
                break
        if k == "q":
            break
        if k == "s":
            continue
        r["correct"] = k
        if k == "n":
            r["notes"] = input("What is wrong? (one line) ").strip()
        merge = input("Brand names to merge? e.g. Soundcore=Anker (Enter to skip) ").strip()
        if merge:
            r["alias_fix"] = merge
        done += 1
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fields)
            w.writeheader()
            w.writerows(rows)
        print()
    print(f"\nSaved. {done} of {target} answers checked." + ("  Done - tell Claude." if done >= target else ""))


def load_aliases():
    return json.loads(ALIASES.read_text(encoding="utf-8")) if ALIASES.exists() else {}


def learn(store):
    aliases, added = load_aliases(), []
    for r in _rows(store):
        for pair in filter(None, (p.strip() for p in r.get("alias_fix", "").split(";"))):
            if "=" not in pair:
                print(f"  skipped '{pair}' in {r['id']}: use the form Source=Brand")
                continue
            src, target = (s.strip() for s in pair.split("=", 1))
            key = norm_text(src)
            if key and target and aliases.get(key) != target:
                aliases[key] = target
                added.append(f"{src} -> {target}")
    ALIASES.write_text(json.dumps(dict(sorted(aliases.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(added)} new brand-name rules saved to {ALIASES.name}" + "".join(f"\n  {a}" for a in added))
