"""Command line. Pilot and full run keep separate data folders, so pilot answers
(collected before settings were final) never enter the results.

  python -m study pilot              # small capped run (Lane A)
  python -m study approve            # YOU, in your own terminal: the one human gate
  python -m study run                # full paid run; refuses without a valid approval (Lane C)
  python -m study handcheck          # draw the review sample
  python -m study review             # YOU: check answers one by one (y/n)
  python -m study learn              # save confirmed brand-name fixes (learning edge)
  python -m study analyze            # results + results gate
"""
import argparse
import sys

from .env import DATA, load_env, model_ids

PROVIDERS = ["claude", "gpt", "gemini"]


def main():
    load_env()
    ap = argparse.ArgumentParser(prog="study")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("pilot", "run"):
        p = sub.add_parser(name)
        p.add_argument("--providers", nargs="+", default=PROVIDERS, choices=PROVIDERS)
        p.add_argument("--workers", type=int, default=4)
        p.add_argument("--mock", action="store_true", help="fake answers, no API calls")
        p.add_argument("--mock-fail-rate", type=float, default=0.0, help="inject failures to test the gates")
    sub.add_parser("approve").add_argument("--providers", nargs="+", default=PROVIDERS, choices=PROVIDERS)
    sub.add_parser("report").add_argument("--providers", nargs="+", default=PROVIDERS, choices=PROVIDERS)
    for name in ("handcheck", "review", "learn", "analyze"):
        p = sub.add_parser(name)
        p.add_argument("--stage", default="full", choices=["pilot", "full"])
        if name == "handcheck":
            p.add_argument("-n", type=int, default=100)
    a = ap.parse_args()

    from .approval import approve, pilot_report, verify
    from .design import PILOT_PROMPTS, PILOT_REPEATS, REPEATS, build_units
    from .gates import design_check
    from .store import Store

    pilot, full = Store(DATA / "pilot"), Store(DATA / "full")
    approval_path = DATA / "approval.json"

    problems = design_check()
    if problems:
        sys.exit("Design gate failed:\n" + "\n".join(f"- {p}" for p in problems))

    if a.cmd in ("pilot", "run"):
        from .pipeline import Run
        if a.cmd == "pilot":
            units = build_units(model_ids(), a.providers, PILOT_PROMPTS, PILOT_REPEATS)
            store = pilot
        else:
            units = build_units(model_ids(), a.providers, None, REPEATS)
            store = full
            blocked = None if a.mock else verify(approval_path, a.providers)
            if blocked:
                sys.exit(f"Full run is locked: {blocked}")
        ok = Run(store, units, a.mock, a.workers, a.mock_fail_rate).go()
        if a.cmd == "pilot":
            report, _ = pilot_report(pilot, a.providers)
            (pilot.dir / "pilot_report.md").write_text(report, encoding="utf-8")
            print(f"\nPilot report: {pilot.dir / 'pilot_report.md'}")
        sys.exit(0 if ok else 2)
    elif a.cmd == "report":
        print(pilot_report(pilot, a.providers)[0])
    elif a.cmd == "approve":
        approve(pilot, approval_path, a.providers)
    else:
        store = pilot if a.stage == "pilot" else full
        if a.cmd == "handcheck":
            from .handcheck import draw
            draw(store, a.n)
        elif a.cmd == "review":
            from .handcheck import review
            review(store)
        elif a.cmd == "learn":
            from .handcheck import learn
            learn(store)
        else:
            from .analyze import analyze
            units = (build_units(model_ids(), PROVIDERS, PILOT_PROMPTS, PILOT_REPEATS) if a.stage == "pilot"
                     else build_units(model_ids(), PROVIDERS, None, REPEATS))
            providers = {x["provider"] for x in store.load("answers")} or set(PROVIDERS)
            analyze(store, [u for u in units if u["provider"] in providers])


if __name__ == "__main__":
    main()
