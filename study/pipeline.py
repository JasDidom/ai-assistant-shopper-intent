"""Run units through collect -> answer gate -> extract -> extraction gate.

Each unit flows on its own: an answer is coded as soon as it passes its gate,
while other answers are still being collected. Retries are per unit, capped at
MAX_ATTEMPTS. A model whose permanent failures pass MAX_FAIL_SHARE is stopped.
"""
import fcntl
import random
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .extract import extract_claude, extract_mock
from .gates import MAX_ATTEMPTS, MAX_FAIL_SHARE, check_answer, check_coding, norm_text
from .models import PROVIDERS, ask_mock


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Account-level errors: no retry of any unit can succeed until the person fixes billing,
# so they halt the whole run and are never recorded as unit failures.
BILLING_ERRORS = ("usage limit", "insufficient_quota", "credit balance is too low",
                  "exceeded your current quota", "billing_hard_limit")


def is_billing_error(e):
    text = str(e).lower()
    return any(p in text for p in BILLING_ERRORS)


class Run:
    def __init__(self, store, units, mock=False, workers=4, mock_fail_rate=0.0):
        self.store, self.units, self.mock, self.workers = store, units, mock, workers
        self.mock_fail_rate = mock_fail_rate
        self.planned = Counter(u["provider"] for u in units)
        self.perm_failed = Counter()
        self.stopped = set()
        self.halted = None
        self.lock = threading.Lock()
        self.stats = Counter()

    def halt(self, where, e):
        with self.lock:
            if not self.halted:
                self.halted = f"{where}: {str(e)[:200]}"
                print(f"HALT: billing or usage limit reached ({self.halted}). Nothing was recorded as a failure; "
                      "fix the account limit, then rerun to continue.")

    # ---- collect node + answer gate ----

    def collect_unit(self, u, prior_failures):
        for attempt in range(prior_failures + 1, MAX_ATTEMPTS + 1):
            if u["provider"] in self.stopped or self.halted:
                return None
            try:
                if self.mock:
                    out = ask_mock(u["model"], u["text"], u["category"], u["intent"], self.mock_fail_rate)
                else:
                    out = PROVIDERS[u["provider"]](u["model"], u["text"])
            except Exception as e:
                if is_billing_error(e):
                    self.halt(u["provider"], e)
                    return None
                self.fail(u, "collect", f"api_error: {type(e).__name__}: {e}"[:300], attempt, retry=True)
                time.sleep(0 if self.mock else 2 ** attempt)
                continue
            v = check_answer(out, u["model"])
            if v.accept:
                row = {"id": u["id"], "provider": u["provider"], "model": u["model"],
                       **{k: u[k] for k in ("prompt_id", "category", "intent", "phrasing", "rep")},
                       "prompt": u["text"], "answer": out["text"], "status": out["status"], "flag": v.flag,
                       "served_model": out.get("served_model"), "in_tokens": out.get("in_tokens"),
                       "out_tokens": out.get("out_tokens"), "attempts": attempt, "at": now()}
                self.store.append("answers", row)
                self.stats["answers_accepted"] += 1
                return row
            self.fail(u, "collect", v.check, attempt, retry=v.retry)
            if not v.retry:
                break
        self.permanent(u)
        return None

    def fail(self, u, stage, check, attempt, retry):
        final = not retry or attempt >= MAX_ATTEMPTS
        self.store.append("errors", {"id": u["id"], "stage": stage, "check": check,
                                     "attempt": attempt, "final": final, "at": now()})
        self.stats[f"{stage}_rejections"] += 1

    def permanent(self, u):
        with self.lock:
            self.perm_failed[u["provider"]] += 1
            share = self.perm_failed[u["provider"]] / self.planned[u["provider"]]
            if share > MAX_FAIL_SHARE and u["provider"] not in self.stopped:
                self.stopped.add(u["provider"])
                print(f"STOP {u['provider']}: {share:.1%} of its units failed permanently "
                      f"(limit {MAX_FAIL_SHARE:.0%}). A setting is probably wrong; check errors.jsonl.")

    # ---- extract node + extraction gate ----

    def code_unit(self, row):
        feedback, coding, problems, tokens = None, None, ["extraction_error"], Counter()
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if self.halted:
                return  # left uncoded, so the next run codes it
            try:
                if self.mock:
                    coding, usage = extract_mock(row["answer"], row["category"], feedback, self.mock_fail_rate)
                else:
                    coding, usage = extract_claude(row["answer"], feedback)
            except Exception as e:
                if is_billing_error(e):
                    self.halt("coding (claude)", e)
                    return
                self.fail(row, "extract", f"api_error: {type(e).__name__}: {e}"[:300], attempt, retry=True)
                continue
            tokens.update({k: v or 0 for k, v in usage.items()})
            problems = check_coding(coding, row["answer"])
            if not problems:
                break
            self.fail(row, "extract", "; ".join(problems)[:500], attempt, retry=True)
            feedback = {"previous": coding, "problems": problems}
        brands, seen = [], set()
        for pos, b in enumerate((coding or {}).get("brands", []), 1):
            key = norm_text(b["brand"])
            if key and key not in seen:
                seen.add(key)
                brands.append({"brand": b["brand"].strip(), "key": key, "stance": b["stance"],
                               "quote": b["quote"], "position": pos})
        rec = {k: row[k] for k in ("id", "provider", "model", "prompt_id", "category", "intent", "phrasing", "rep")}
        rec.update(gives_recommendation=(coding or {}).get("gives_recommendation", False), brands=brands,
                   check_failed=problems if problems else [], attempts=attempt, **dict(tokens), at=now())
        self.store.append("codings", rec)
        self.stats["codings_failed" if problems else "codings_accepted"] += 1

    # ---- orchestration ----

    def go(self):
        # Only one run per data folder: two copies would collect the same units twice.
        self._lockfile = (self.store.dir / ".run.lock").open("w")
        try:
            fcntl.flock(self._lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another run is already using this data folder. Stop it first (Ctrl+C in its terminal).")
            return False
        answers = {a["id"]: a for a in self.store.load("answers")}
        coded = {c["id"] for c in self.store.load("codings")}
        errors = self.store.load("errors")
        fails = Counter(e["id"] for e in errors if e["stage"] == "collect")
        final = {e["id"] for e in errors if e["stage"] == "collect" and e["final"]}
        for u in self.units:
            if u["id"] not in answers and (u["id"] in final or fails[u["id"]] >= MAX_ATTEMPTS):
                self.perm_failed[u["provider"]] += 1
        todo = [u for u in self.units if u["id"] not in answers and u["id"] not in final
                and fails[u["id"]] < MAX_ATTEMPTS]
        to_code = [a for a in answers.values() if a["id"] not in coded and a["answer"].strip()]
        print(f"{len(self.units)} units: {len(answers)} answered, {len(todo)} to collect, "
              f"{sum(self.perm_failed.values())} failed permanently, {len(to_code)} answers waiting for coding")

        random.shuffle(todo)  # spread prompts over time so a model update mid-run hits all cells alike
        collect_pools = {p: ThreadPoolExecutor(self.workers) for p in self.planned}
        code_pool = ThreadPoolExecutor(self.workers)
        code_futures = [code_pool.submit(self.code_unit, a) for a in to_code]
        lock = threading.Lock()

        def collect_then_code(u):
            row = self.collect_unit(u, fails[u["id"]])
            if row and row["answer"].strip():
                with lock:
                    code_futures.append(code_pool.submit(self.code_unit, row))

        start = time.time()
        futures = [collect_pools[u["provider"]].submit(collect_then_code, u) for u in todo]
        for i, f in enumerate(futures, 1):
            f.result()
            if i % 100 == 0 or i == len(futures):
                print(f"  collected {i}/{len(futures)}  {dict(self.stats)}  {time.time() - start:.0f}s")
        for pool in collect_pools.values():
            pool.shutdown()
        with lock:
            pending = list(code_futures)
        for f in pending:
            f.result()
        code_pool.shutdown()
        print(f"done: {dict(self.stats)}")
        if self.halted:
            print(f"halted: {self.halted}")
            return False
        if self.stopped:
            print(f"stopped models: {sorted(self.stopped)} - fix the cause, then rerun to continue")
        return not self.stopped
