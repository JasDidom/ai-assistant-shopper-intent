"""Program-evaluable checks. Every gate returns evidence, never a model's opinion."""
import re
from collections import Counter
from dataclasses import dataclass

from .design import CATEGORIES, INTENTS, build_prompts

MAX_ATTEMPTS = 3
MAX_FAIL_SHARE = 0.02      # more permanent failures than this per model = stop and ask the human
MIN_CHARS = 80             # shorter answers are kept but flagged for review
MIN_HANDCHECK_ACCURACY = 0.90
MIN_HANDCHECK_ROWS = 20    # human-checked rows needed; an AI audit alone never makes results READY


def norm_text(s):
    s = s.translate({ord("’"): "'", ord("‘"): "'", ord("“"): '"', ord("”"): '"', ord("–"): "-", ord("—"): "-"})
    return re.sub(r"[^a-z0-9&]+", " ", s.lower()).strip()


# ---- design gate ----

def design_check():
    prompts = build_prompts()
    problems = []
    ids = [p["prompt_id"] for p in prompts]
    if len(set(ids)) != len(CATEGORIES) * len(INTENTS) * 4:
        problems.append(f"expected {len(CATEGORIES) * len(INTENTS) * 4} unique prompts, got {len(set(ids))}")
    for intent, phrasings in INTENTS.items():
        if len(phrasings) != 4:
            problems.append(f"intent {intent} has {len(phrasings)} phrasings, expected 4")
    problems += [f"unrendered placeholder in {p['prompt_id']}" for p in prompts if "{" in p["text"]]
    return problems


# ---- answer gate ----

@dataclass
class Verdict:
    accept: bool
    check: str = ""
    retry: bool = False
    flag: str = ""


def check_answer(out, requested_model):
    """Retry only technical failures. Refusals and short answers are data, not errors."""
    served = out.get("served_model") or ""
    if served and not served.startswith(requested_model):
        return Verdict(False, f"served_model_mismatch: asked {requested_model}, got {served}", retry=False)
    if out["status"] == "refusal":
        return Verdict(True, flag="refusal")
    if out["status"] == "truncated":
        return Verdict(False, "truncated", retry=True)
    if not out["text"].strip():
        return Verdict(False, "empty_answer", retry=True)
    if len(out["text"].strip()) < MIN_CHARS:
        return Verdict(True, flag="short")
    return Verdict(True)


# ---- extraction gate ----

def check_coding(coding, answer_text):
    """Every brand must be backed by a quote that really appears in the answer."""
    problems = []
    text = norm_text(answer_text)
    for b in coding["brands"]:
        quote = norm_text(b.get("quote", ""))
        if not quote:
            problems.append(f"brand '{b['brand']}' has no quote")
        elif quote not in text:
            problems.append(f"brand '{b['brand']}': quote '{b['quote']}' is not in the answer text")
    has_rec = any(b["stance"] == "recommended" for b in coding["brands"])
    if coding["gives_recommendation"] != has_rec:
        problems.append(f"gives_recommendation={coding['gives_recommendation']} but "
                        f"{'a' if has_rec else 'no'} brand is marked recommended")
    return problems


# ---- results gate ----

def results_gate(units_planned, answers, codings, handcheck):
    """READY only if the design is complete enough and coding accuracy was measured."""
    reasons = []
    done = Counter()
    for a in answers:
        if a["status"] == "refusal":
            done[a["provider"]] += 1
    for c in codings:
        if not c.get("check_failed"):
            done[c["provider"]] += 1
    for prov, planned in units_planned.items():
        missing = 1 - done[prov] / planned
        if missing > MAX_FAIL_SHARE:
            reasons.append(f"{prov}: {missing:.1%} of planned answers missing or failed checks (limit {MAX_FAIL_SHARE:.0%})")
    handcheck = handcheck or {}
    if handcheck.get("checked", 0) < MIN_HANDCHECK_ROWS:
        reasons.append(f"only {handcheck.get('checked', 0)} rows hand-checked by a human (need {MIN_HANDCHECK_ROWS})")
    elif handcheck["accuracy"] < MIN_HANDCHECK_ACCURACY:
        reasons.append(f"hand-check accuracy {handcheck['accuracy']:.0%} is below {MIN_HANDCHECK_ACCURACY:.0%}")
    if "ai_accuracy" in handcheck and handcheck["ai_accuracy"] < MIN_HANDCHECK_ACCURACY:
        reasons.append(f"AI audit accuracy {handcheck['ai_accuracy']:.0%} is below {MIN_HANDCHECK_ACCURACY:.0%}")
    return reasons


# ---- pilot gate (evidence shown to the human before the paid run) ----

def predictions_filled(readme_text):
    section = readme_text.split("## Predictions", 1)[-1].split("\n## ", 1)[0]
    items = re.findall(r"^\d\.\s*[^:\n]+:(.*)$", section, flags=re.M)
    return len(items) >= 4 and all(i.strip() for i in items)


def pilot_check(units, answers, codings, errors):
    reasons = []
    answered = {a["id"] for a in answers}
    final = {e["id"] for e in errors if e["stage"] == "collect" and e.get("final")}
    for u in units:
        if u["id"] not in answered:
            reasons.append(f"{u['id']}: no accepted answer" + (" (failed permanently)" if u["id"] in final else ""))
    bad = [c["id"] for c in codings if c.get("check_failed")]
    reasons += [f"{i}: coding failed its checks" for i in bad]
    return reasons
