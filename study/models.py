"""One function per provider: prompt in, answer + served model + token usage out."""
import random
import threading

# Default sampling settings on every provider, so each assistant behaves as it
# does for an ordinary user. No system prompt, no web search, no memory.
SETTINGS = {"claude_max_tokens": 4000, "claude_effort": "low"}


def ask_claude(model, prompt):
    import anthropic
    # No refusal fallback on purpose: an answer from a different model would
    # contaminate the data. A refusal is recorded as its own outcome.
    resp = anthropic.Anthropic().messages.create(
        model=model,
        max_tokens=SETTINGS["claude_max_tokens"],
        output_config={"effort": SETTINGS["claude_effort"]},
        messages=[{"role": "user", "content": prompt}],
    )
    status = {"refusal": "refusal", "max_tokens": "truncated"}.get(resp.stop_reason, "ok")
    text = "" if status == "refusal" else "".join(b.text for b in resp.content if b.type == "text")
    return {"text": text, "status": status, "served_model": resp.model,
            "in_tokens": resp.usage.input_tokens, "out_tokens": resp.usage.output_tokens}


def ask_gpt(model, prompt):
    from openai import OpenAI
    resp = OpenAI().responses.create(model=model, input=prompt)
    usage = getattr(resp, "usage", None)
    truncated = getattr(resp, "status", "") == "incomplete"
    return {"text": resp.output_text or "", "status": "truncated" if truncated else "ok",
            "served_model": getattr(resp, "model", ""),
            "in_tokens": getattr(usage, "input_tokens", None), "out_tokens": getattr(usage, "output_tokens", None)}


_gemini_client = None
_gemini_lock = threading.Lock()


def ask_gemini(model, prompt):
    # One shared client, created once under a lock: a temporary or duplicate client
    # can be garbage-collected mid-request, which closes its connection.
    global _gemini_client
    from google import genai
    with _gemini_lock:
        if _gemini_client is None:
            _gemini_client = genai.Client()
    resp = _gemini_client.models.generate_content(model=model, contents=prompt)
    finish = str(getattr((resp.candidates or [None])[0], "finish_reason", "") or "")
    status = "refusal" if "SAFETY" in finish or "PROHIBITED" in finish else (
        "truncated" if "MAX_TOKENS" in finish else "ok")
    usage = getattr(resp, "usage_metadata", None)
    return {"text": "" if status == "refusal" else (resp.text or ""), "status": status,
            "served_model": getattr(resp, "model_version", "") or "",
            "in_tokens": getattr(usage, "prompt_token_count", None),
            "out_tokens": (getattr(usage, "candidates_token_count", 0) or 0) + (getattr(usage, "thoughts_token_count", 0) or 0)}


PROVIDERS = {"claude": ask_claude, "gpt": ask_gpt, "gemini": ask_gemini}

# ---- mock mode: fake but structured answers, to test the pipeline for free ----

MOCK_BRANDS = {
    "running_shoes": ["Nike", "Adidas", "Brooks", "Asics", "Hoka", "New Balance", "Saucony", "On", "Allbirds", "Veja"],
    "headphones": ["Sony", "Bose", "Apple", "Sennheiser", "Anker", "JBL", "Jabra", "Bowers & Wilkins", "Fairphone", "House of Marley"],
    "crm": ["HubSpot", "Salesforce", "Zoho", "Pipedrive", "Freshsales", "Monday", "Insightly", "Copper", "Less Annoying CRM", "Capsule"],
}
MOCK_BIAS = {"budget": [5, 6, 7], "premium": [2, 3, 7], "sustainable": [8, 9], "novice": [0, 1, 4]}


def ask_mock(model, prompt, category, intent, fail_rate=0.0):
    """Fake answers. fail_rate injects technical failures to exercise the answer gate."""
    roll = random.random()
    if roll < fail_rate / 2:
        raise ConnectionError("mock network error")
    if roll < fail_rate:
        return {"text": "", "status": "ok", "served_model": model, "in_tokens": 12, "out_tokens": 0}
    brands = MOCK_BRANDS[category]
    weights = [3.0] * 3 + [1.5] * 4 + [0.5] * 3
    for i in MOCK_BIAS.get(intent, []):
        weights[i] += 3.0
    picks = []
    while len(picks) < random.randint(3, 6):
        b = random.choices(brands, weights)[0]
        if b not in picks:
            picks.append(b)
    lines = [f"{i + 1}. **{b}** - a solid choice for most people." for i, b in enumerate(picks)]
    text = "Here are some good options:\n" + "\n".join(lines)
    return {"text": text, "status": "ok", "served_model": model, "in_tokens": 15, "out_tokens": len(text) // 4}
