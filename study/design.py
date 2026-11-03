"""Study design: categories x intents x phrasings, expanded into a prompt set."""
import itertools
import json
from pathlib import Path

CATEGORIES = {
    "running_shoes": "running shoes",
    "headphones": "noise-cancelling headphones",
    "crm": "CRM software for a small business",
}

# Four phrasings per intent. Each works for every category, so any difference
# between intents comes from the intent, not from category-specific wording.
INTENTS = {
    "neutral": [
        "What are the best {p}?",
        "Can you recommend some {p}?",
        "Which {p} should I buy?",
        "I'm looking for {p}. What would you suggest?",
    ],
    "budget": [
        "What are the best {p} on a tight budget?",
        "Can you recommend some affordable {p} that are good value?",
        "Which cheap {p} are actually worth buying?",
        "I don't want to spend much on {p}. What would you suggest?",
    ],
    "premium": [
        "What are the best premium {p}, money no object?",
        "Can you recommend top-of-the-line {p}?",
        "Which high-end {p} are worth the price?",
        "I want the highest quality {p} I can get. What would you suggest?",
    ],
    "sustainable": [
        "What are the most sustainable {p}?",
        "Can you recommend eco-friendly {p}?",
        "Which {p} brands are best for the environment?",
        "I care about sustainability. Which {p} would you suggest?",
    ],
    "novice": [
        "What are the best {p} for someone who knows nothing about them?",
        "Can you recommend {p} for a first-time buyer?",
        "Which {p} are easiest to get right if I'm not an expert?",
        "I don't know much about {p}. Which would you suggest?",
    ],
}

REPEATS = 10

# Pilot: 6 prompts that touch every category, every intent and several wordings.
PILOT_PROMPTS = [
    "running_shoes__neutral__p0", "running_shoes__premium__p2",
    "headphones__budget__p1", "headphones__sustainable__p3",
    "crm__novice__p0", "crm__neutral__p2",
]
PILOT_REPEATS = 2


def build_units(model_ids, providers, prompt_ids=None, repeats=REPEATS):
    """One unit = one API call: (provider, prompt, repeat)."""
    prompts = [p for p in build_prompts() if prompt_ids is None or p["prompt_id"] in prompt_ids]
    return [{"id": f"{prov}|{model_ids[prov]}|{p['prompt_id']}|r{r}", "provider": prov,
             "model": model_ids[prov], "rep": r, **p}
            for prov in providers for p in prompts for r in range(repeats)]


def build_prompts():
    rows = []
    for (cat, product), (intent, phrasings) in itertools.product(CATEGORIES.items(), INTENTS.items()):
        for i, template in enumerate(phrasings):
            rows.append({
                "prompt_id": f"{cat}__{intent}__p{i}",
                "category": cat,
                "intent": intent,
                "phrasing": i,
                "text": template.format(p=product),
            })
    return rows


def write_prompts(path: Path):
    rows = build_prompts()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows
