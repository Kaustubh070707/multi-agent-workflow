"""20-scenario eval. Measures success rate, avg cost, avg steps. Run: python eval/run_eval.py"""
import json
from pathlib import Path

from app.main import ApproveRequest, RunRequest, approve, run


def main():
    with open(Path("eval/scenarios.jsonl"), encoding="utf-8") as f:
        scenarios = [json.loads(line) for line in f if line.strip()]
    ok = total_cost = total_steps = 0
    rows = []
    for sc in scenarios:
        goal, expect, must = sc["goal"], sc["expect"], sc.get("must_contain", "")
        body = run(RunRequest(goal=goal))
        if body["status"] == "awaiting_approval" and expect == "awaiting_approval":
            passed = True
            # prove the gate resumes too (auto-approve in eval only)
            resumed = approve(ApproveRequest(approval_token=body["approval_token"]))
            passed = passed and resumed["status"] in ("done", "error", "stopped")
        elif expect == "done_or_error":
            passed = body["status"] in ("done", "error", "stopped")
        else:
            passed = body["status"] == expect and (not must or must in json.dumps(body, default=str))
        total_cost += sum(t.get("cost_usd", 0) for t in body["trace"] if "cost_usd" in t)
        total_steps += sum(1 for t in body["trace"] if "tool" in t)
        ok += passed
        rows.append((sc["id"], goal[:40], body["status"], "PASS" if passed else "FAIL"))
    n = len(scenarios)
    print(f"HIT {ok}/{n} ({ok/n:.0%}) avg_cost=${total_cost/n:.4f} avg_steps={total_steps/n:.1f}", flush=True)
    for row in rows:
        print(f"  {'PASS' if row[3]=='PASS' else 'FAIL'} #{row[0]} [{row[2]}] {row[1]!r}", flush=True)


if __name__ == "__main__":
    main()
