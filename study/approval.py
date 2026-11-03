"""The one human gate: the full paid run opens only after a person approves the pilot evidence.

The approval is bound to a fingerprint of the design and settings. Changing a
prompt, a model or a setting after approving invalidates it.
"""
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone

from .design import PILOT_PROMPTS, PILOT_REPEATS, REPEATS, build_prompts, build_units
from .env import ROOT, model_ids
from .gates import pilot_check, predictions_filled
from .models import SETTINGS

PRICES = ROOT / "study" / "prices.json"   # USD per million tokens [input, output]; fill from pricing pages


def fingerprint(providers):
    blob = json.dumps({"prompts": build_prompts(), "repeats": REPEATS, "models": model_ids(),
                       "providers": sorted(providers), "settings": SETTINGS}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def prices():
    return json.loads(PRICES.read_text()) if PRICES.exists() else {}


def pilot_report(pilot_store, providers):
    """Evidence for the human: pass rates, examples, measured tokens and projected cost."""
    ids = model_ids()
    units = build_units(ids, providers, PILOT_PROMPTS, PILOT_REPEATS)
    answers, codings, errors = (pilot_store.load(n) for n in ("answers", "codings", "errors"))
    problems = pilot_check(units, answers, codings, errors)
    readme_ok = predictions_filled((ROOT / "README.md").read_text(encoding="utf-8"))
    if not readme_ok:
        problems.append("README predictions are not filled in (write them before the full run)")

    lines = ["# Pilot report", "", f"Design fingerprint: `{fingerprint(providers)}`", ""]
    full_units = len(build_prompts()) * REPEATS
    table = prices()
    total_cost, unknown = 0.0, []
    lines += ["| model | answers accepted | first-try coding pass | mean tokens in/out | projected tokens for full run | projected cost |",
              "|---|---|---|---|---|---|"]
    by_prov = defaultdict(list)
    for a in answers:
        by_prov[a["provider"]].append(a)
    first_try = defaultdict(lambda: [0, 0])
    for c in codings:
        first_try[c["provider"]][0] += c["attempts"] == 1 and not c["check_failed"]
        first_try[c["provider"]][1] += 1
    for prov in providers:
        rows = by_prov[prov]
        planned = sum(u["provider"] == prov for u in units)
        tin = [r["in_tokens"] for r in rows if r.get("in_tokens") is not None]
        tout = [r["out_tokens"] for r in rows if r.get("out_tokens") is not None]
        m_in, m_out = (sum(tin) / len(tin) if tin else 0), (sum(tout) / len(tout) if tout else 0)
        p_in, p_out = m_in * full_units, m_out * full_units
        price = table.get(ids[prov])
        if price:
            cost = p_in / 1e6 * price[0] + p_out / 1e6 * price[1]
            total_cost += cost
            cost_s = f"${cost:,.2f}"
        else:
            unknown.append(ids[prov])
            cost_s = "price not set"
        ok, n = first_try[prov]
        lines.append(f"| {prov} ({ids[prov]}) | {len(rows)}/{planned} | {ok}/{n} | {m_in:.0f} / {m_out:.0f} | "
                     f"{p_in:,.0f} / {p_out:,.0f} | {cost_s} |")
    ctin = [c.get("in_tokens", 0) for c in codings]
    ctout = [c.get("out_tokens", 0) for c in codings]
    if ctin:
        n_full = full_units * len(providers)
        c_in, c_out = sum(ctin) / len(ctin) * n_full, sum(ctout) / len(ctout) * n_full
        price = table.get(ids["claude"])
        cost_s = f"${c_in / 1e6 * price[0] + c_out / 1e6 * price[1]:,.2f}" if price else "price not set"
        if price:
            total_cost += c_in / 1e6 * price[0] + c_out / 1e6 * price[1]
        lines.append(f"| coding ({ids['claude']}) | - | - | - | {c_in:,.0f} / {c_out:,.0f} | {cost_s} |")
    lines += ["", f"**Projected total: ${total_cost:,.2f}**" + (f" plus models with no price set: {', '.join(unknown)}" if unknown else ""), ""]
    lines += ["## Example answers", ""]
    for prov in providers:
        for r in by_prov[prov][:3]:
            lines += [f"**{prov} - {r['prompt']}**", "", "> " + r["answer"][:600].replace("\n", "\n> "), ""]
    lines += ["## Gate checks", ""] + ([f"- FAIL: {p}" for p in problems] or ["- all checks passed"])
    return "\n".join(lines), problems


def approve(pilot_store, approval_path, providers):
    report, problems = pilot_report(pilot_store, providers)
    print(report)
    if problems:
        sys.exit("\nThe pilot gate has failed checks; the full run cannot be approved until they pass.")
    if not sys.stdin.isatty():
        sys.exit("\nApproval must be typed by a person in an interactive terminal.")
    typed = input("\nType APPROVE to allow the full paid run with exactly this design: ").strip()
    if typed != "APPROVE":
        sys.exit("Not approved.")
    approval_path.write_text(json.dumps({"fingerprint": fingerprint(providers), "providers": sorted(providers),
                                         "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                                        indent=1))
    print(f"Approved. Saved {approval_path}")


def verify(approval_path, providers):
    if not approval_path.exists():
        return "no approval yet: run the pilot, then `study approve` in your own terminal"
    a = json.loads(approval_path.read_text())
    if a["fingerprint"] != fingerprint(providers):
        return "the design, models or settings changed since approval: rerun the pilot and approve again"
    return None
