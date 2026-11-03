"""Code one answer into an ordered brand list, with a verbatim quote backing each brand."""
import json
import random

from .env import model_ids
from .models import MOCK_BRANDS

SCHEMA = {
    "type": "object",
    "properties": {
        "gives_recommendation": {"type": "boolean"},
        "brands": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "brand": {"type": "string"},
                    "stance": {"type": "string", "enum": ["recommended", "mentioned", "warned_against"]},
                    "quote": {"type": "string"},
                },
                "required": ["brand", "stance", "quote"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["gives_recommendation", "brands"],
    "additionalProperties": False,
}

INSTRUCTIONS = """You are coding answers for a research study on which brands AI assistants recommend.

Read the answer below and list every brand it names, in the order each brand first appears.

Rules:
- brand: the brand or company name only, not the product line: "Nike Pegasus 41" -> "Nike", "Sony WH-1000XM6" -> "Sony", "AirPods Max" -> "Apple", "HubSpot Starter" -> "HubSpot". Use the brand's usual spelling.
- quote: copy the exact words from the answer where the brand or its product first appears (2 to 8 words, verbatim).
- stance: "recommended" if the answer suggests buying or trying it, "warned_against" if it advises against it, "mentioned" otherwise (for example a comparison point or a retailer).
- Every brand offered as an option counts as recommended, even if the answer later names one favourite: each row of a shortlist or options table, each item in a list of picks, and conditional picks ("if you use an iPhone, AirPods Max").
- Shops, marketplaces and review sites (for example Running Warehouse, Fleet Feet, Amazon, RTINGS) are always "mentioned", even when the answer tells the reader to buy there. A store's own house brand offered as a product (for example Decathlon's Kiprun) is a brand.
- Name each brand once. Do not add brands the answer does not name.
- gives_recommendation: true if at least one brand is recommended, otherwise false (for example the answer only gives buying criteria or declines).

Answer to code:
<answer>
{answer}
</answer>"""

FEEDBACK = """

Your previous coding of this answer was:
{previous}

It failed these checks:
{problems}

Fix only the items listed above. Keep every other brand, stance and quote exactly as it was."""


def extract_claude(answer, feedback=None):
    import anthropic
    content = INSTRUCTIONS.format(answer=answer)
    if feedback:
        content += FEEDBACK.format(previous=json.dumps(feedback["previous"], ensure_ascii=False),
                                   problems="\n".join(f"- {p}" for p in feedback["problems"]))
    resp = anthropic.Anthropic().messages.create(
        model=model_ids()["claude"],
        max_tokens=4000,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": content}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("extraction refused")
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text), {"in_tokens": resp.usage.input_tokens, "out_tokens": resp.usage.output_tokens}


def extract_mock(answer, category, feedback=None, error_rate=0.0):
    """Finds the known mock brands. error_rate injects a made-up brand on first attempts."""
    found = sorted((answer.find(b), b) for b in MOCK_BRANDS[category] if b in answer)
    brands = [{"brand": b, "stance": "recommended", "quote": b} for _, b in found]
    if not feedback and random.random() < error_rate:
        brands.append({"brand": "Zzyzx", "stance": "recommended", "quote": "Zzyzx is great"})
    return {"gives_recommendation": bool(brands), "brands": brands}, {"in_tokens": 0, "out_tokens": 0}
