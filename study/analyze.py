"""Compute the study's measures and charts from data/extracted.jsonl into results/."""
import itertools
import random
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .design import CATEGORIES, INTENTS  # noqa: E402
from .gates import norm_text, results_gate  # noqa: E402
from .handcheck import load_aliases, score  # noqa: E402

PERMUTATIONS = 2000


def ruzicka(a, b):
    """Weighted Jaccard distance between two visibility vectors: 0 same, 1 disjoint."""
    keys = set(a) | set(b)
    top = sum(max(a.get(k, 0), b.get(k, 0)) for k in keys)
    return 1 - sum(min(a.get(k, 0), b.get(k, 0)) for k in keys) / top if top else 0.0


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 1.0


def visibility(rows):
    """Share of answers in `rows` that recommend each brand."""
    c = Counter(k for r in rows for k in r["rec"])
    return {k: v / len(rows) for k, v in c.items()} if rows else {}


def intent_gap(cells, labels):
    within, between = [], []
    for i, j in itertools.combinations(range(len(cells)), 2):
        (within if labels[i] == labels[j] else between).append(ruzicka(cells[i], cells[j]))
    if not within or not between:
        return None  # e.g. the pilot has one wording per intent: no comparison possible
    return sum(within) / len(within), sum(between) / len(between)


def intent_vs_wording(groups):
    """Per provider x category: within-intent vs between-intent distance, with a permutation p-value."""
    out = []
    rng = random.Random(0)
    for (prov, cat), by_prompt in sorted(groups.items()):
        keys = sorted(by_prompt)
        cells = [visibility(by_prompt[k]) for k in keys]
        labels = [k.split("__")[1] for k in keys]
        observed = intent_gap(cells, labels)
        if observed is None:
            continue
        w, b = observed
        gap, hits, valid = b - w, 0, 0
        for _ in range(PERMUTATIONS):
            shuffled = labels[:]
            rng.shuffle(shuffled)
            perm = intent_gap(cells, shuffled)
            if perm:
                valid += 1
                hits += (perm[1] - perm[0]) >= gap
        out.append({"provider": prov, "category": cat, "within": w, "between": b,
                    "ratio": b / w if w else float("inf"), "p": (hits + 1) / (valid + 1)})
    return out


def stability(rows):
    by_prompt = defaultdict(list)
    for r in rows:
        by_prompt[(r["provider"], r["prompt_id"])].append(r)
    per_provider = defaultdict(list)
    identical = defaultdict(lambda: [0, 0])
    for (prov, _), rs in by_prompt.items():
        pairs = list(itertools.combinations(rs, 2))
        if not pairs:
            continue
        per_provider[prov].append(sum(jaccard(set(a["rec"]), set(b["rec"])) for a, b in pairs) / len(pairs))
        identical[prov][0] += sum(a["rec"] == b["rec"] for a, b in pairs)
        identical[prov][1] += len(pairs)
    return per_provider, {p: s / n for p, (s, n) in identical.items()}


def concentration(rows):
    groups = defaultdict(Counter)
    for r in rows:
        groups[(r["provider"], r["category"], r["intent"])].update(r["rec"])
    return {g: sum(n for _, n in c.most_common(3)) / sum(c.values()) for g, c in groups.items() if c}


def agreement(rows, providers):
    out = {}
    for cat, intent in itertools.product(CATEGORIES, INTENTS):
        tops = {}
        for prov in providers:
            vis = visibility([r for r in rows if r["provider"] == prov and r["category"] == cat and r["intent"] == intent])
            tops[prov] = {k for k, _ in sorted(vis.items(), key=lambda kv: -kv[1])[:5]}
        for a, b in itertools.combinations(providers, 2):
            out.setdefault((a, b), []).append(jaccard(tops[a], tops[b]))
    return {k: sum(v) / len(v) for k, v in out.items()}


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def charts(out, gaps, stab, rows, names, providers):
    fig, axes = plt.subplots(1, len(CATEGORIES), figsize=(4 * len(CATEGORIES), 3.6), sharey=True)
    for ax, cat in zip(axes, CATEGORIES):
        g = [x for x in gaps if x["category"] == cat]
        xs = range(len(g))
        ax.bar([x - 0.2 for x in xs], [x["within"] for x in g], 0.4, label="same intent, other wording", color="#9db4d6")
        ax.bar([x + 0.2 for x in xs], [x["between"] for x in g], 0.4, label="different intent", color="#2f5597")
        ax.set_xticks(list(xs), [x["provider"] for x in g])
        ax.set_title(CATEGORIES[cat])
    axes[0].set_ylabel("distance between brand lists (0-1)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, fontsize=9, frameon=False)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(out / "fig1_intent_vs_wording.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5, 3.6))
    ax.boxplot([stab[p] for p in providers], tick_labels=providers)
    ax.set_ylabel("overlap between repeated answers (Jaccard)")
    ax.set_title("Same prompt, asked 10 times")
    fig.tight_layout()
    fig.savefig(out / "fig2_stability.png", dpi=160)
    plt.close(fig)

    for cat in CATEGORIES:
        cols = [(p, i) for p in providers for i in INTENTS]
        vis = {c: visibility([r for r in rows if (r["provider"], r["intent"]) == c and r["category"] == cat]) for c in cols}
        total = Counter()
        for v in vis.values():
            total.update(v)
        brands = [k for k, _ in total.most_common(12)]
        grid = [[vis[c].get(b, 0) for c in cols] for b in brands]
        fig, ax = plt.subplots(figsize=(1 + 0.45 * len(cols), 1 + 0.35 * len(brands)))
        im = ax.imshow(grid, cmap="Blues", vmin=0, vmax=1, aspect="auto")
        ax.set_yticks(range(len(brands)), [names[b] for b in brands])
        ax.set_xticks(range(len(cols)), [f"{p} · {i}" for p, i in cols], fontsize=7, rotation=60, ha="right")
        ax.set_title(f"Share of answers recommending each brand: {CATEGORIES[cat]}")
        fig.colorbar(im, ax=ax, shrink=0.8)
        fig.tight_layout()
        fig.savefig(out / f"fig3_visibility_{cat}.png", dpi=160)
        plt.close(fig)


def analyze(store, units):
    """Codings that failed the extraction gate are excluded and counted as missing."""
    answers, all_codings, errors = (store.load(n) for n in ("answers", "codings", "errors"))
    coded = [c for c in all_codings if not c.get("check_failed")]
    if not coded:
        raise SystemExit("no accepted codings yet: run the pipeline first")
    aliases = load_aliases()  # learning edge: confirmed brand-name fixes, applied on every run
    canon = {norm_text(k): (norm_text(v), v) for k, v in aliases.items()}
    names_count = defaultdict(Counter)
    for r in coded:
        keys = []
        for b in r["brands"]:
            key, name = canon.get(b["key"], (b["key"], b["brand"]))
            names_count[key][name] += 1
            if b["stance"] == "recommended" and key not in keys:
                keys.append(key)
        r["rec"] = keys
    names = {k: c.most_common(1)[0][0] for k, c in names_count.items()}
    providers = sorted({r["provider"] for r in coded})
    out = store.dir / "results"
    out.mkdir(exist_ok=True)

    groups = defaultdict(lambda: defaultdict(list))
    for r in coded:
        groups[(r["provider"], r["category"])][r["prompt_id"]].append(r)
    gaps = intent_vs_wording(groups)
    stab, identical = stability(coded)
    conc = concentration(coded)
    agree = agreement(coded, providers)
    charts(out, gaps, stab, coded, names, providers)

    status = Counter((a["provider"], a["status"]) for a in answers)
    flags = Counter((a["provider"], a.get("flag")) for a in answers)
    no_rec = Counter(r["provider"] for r in coded if not r["rec"])
    gate_failed = Counter(c["provider"] for c in all_codings if c.get("check_failed"))
    answered = {a["id"] for a in answers}
    perm = Counter(u["provider"] for u in units if u["id"] not in answered
                   and any(e["id"] == u["id"] and e["final"] for e in errors))
    check = score(store)
    blockers = results_gate(Counter(u["provider"] for u in units), answers, all_codings, check)
    verdict = ("**Status: READY** - all results-gate checks passed." if not blockers else
               "**Status: NOT READY** - do not cite these numbers yet:\n" + "\n".join(f"- {b}" for b in blockers))

    parts = ["# Results", "", verdict, "",
             f"Accepted codings: {len(coded)} of {len(units)} planned units. "
             + (f"Coding accuracy, AI audit (independent model reviewers): {check['ai_accuracy']:.0%} of "
                f"{check['ai_checked']} randomly sampled answers. " if check and "ai_checked" in check else "")
             + (f"Human hand-check: {check['accuracy']:.0%} of {check['checked']} answers."
                if check and "checked" in check else "Human hand-check not done yet (fill 'correct' in handcheck.csv)."), "",
             "## 1. Does intent move the brand list more than wording does?", "",
             "Distance 0 = identical brand visibility, 1 = no overlap. p = share of 2,000 random relabelings "
             "with a gap at least as large (small p: intent effect unlikely to be wording noise).", "",
             md_table(["model", "category", "same intent, other wording", "different intent", "ratio", "p"],
                      [[g["provider"], g["category"], f"{g['within']:.2f}", f"{g['between']:.2f}",
                        f"{g['ratio']:.2f}", f"{g['p']:.3f}"] for g in gaps]), "",
             "## 2. Stability when the same prompt is repeated", "",
             md_table(["model", "mean overlap", "identical brand lists"],
                      [[p, f"{sum(stab[p]) / len(stab[p]):.2f}", f"{identical[p]:.1%}"] for p in providers]), "",
             "## 3. Concentration: share of mentions going to the top 3 brands", "",
             md_table(["model", "category"] + list(INTENTS),
                      [[p, c] + [f"{conc.get((p, c, i), 0):.0%}" for i in INTENTS] for p in providers for c in CATEGORIES]), "",
             "## 4. Agreement between models (overlap of top-5 brands, averaged)", "",
             md_table(["pair", "overlap"], [[f"{a} vs {b}", f"{v:.2f}"] for (a, b), v in agree.items()]), "",
             "## Data quality", "",
             md_table(["model", "accepted answers", "refusals", "short (flagged)", "failed permanently",
                       "coding failed gate", "no brand recommended"],
                      [[p, status[(p, "ok")], status[(p, "refusal")], flags[(p, "short")], perm[p],
                        gate_failed[p], no_rec[p]] for p in providers]),
             ""]
    (out / "summary.md").write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {out / 'summary.md'} and charts")
    print(verdict)
