from __future__ import annotations

from pathlib import Path

from agents.agent2_evaluator.evaluator import Agent2Evaluator, build_output
from agents.agent2_evaluator.loaders import load_evidence

REAL_EVIDENCE_PATH = (
    Path(__file__).parents[2] / "evaluation" / "results" / "BPMNEvidence.json"
)
CHECKLIST_PATH = (
    Path(__file__).parents[2]
    / "evaluation"
    / "dataset"
    / "Checklist completo - Modelagem 1 - Básico.csv"
)
OUTPUT_PATH = (
    Path(__file__).parents[2] / "evaluation" / "results" / "BPMNAssessment.json"
)



def main() -> None:
    print("Loading evidence...")
    evidence_list = load_evidence(REAL_EVIDENCE_PATH)
    print(f"  Evidence items : {len(evidence_list)}")

    print("\nRunning full Agent 2 pipeline (load → plan → loop → serialize)...")
    evaluator = Agent2Evaluator()
    assessments = evaluator.run(evidence_list, CHECKLIST_PATH, OUTPUT_PATH)

    output = build_output(assessments, evaluator.iteration_log)

    # --- Iteration log ---
    print(f"\n{'='*70}")
    print("ITERATION LOG")
    print(f"{'='*70}")
    for entry in evaluator.iteration_log:
        stop = f"  → STOP: {entry['stop_reason']}" if entry["stop_reason"] else ""
        refined = (
            f"  refined={len(entry['items_refined'])} items"
            if entry["items_refined"]
            else ""
        )
        print(
            f"  Iter {entry['iteration']}:  avg_conf={entry['avg_confidence']:.4f}"
            f"  weak={entry['items_weak']}/{entry['items_total']}"
            f"{refined}{stop}"
        )

    # --- Summary ---
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    s = output["summary"]
    print(f"  Total criteria         : {s['total_criteria']}")
    print(f"  Status counts          : {s['status_counts']}")
    print(f"  Total applied_penalty  : {s['total_applied_penalty']}")
    print(f"  Iterations ran         : {s['iterations_ran']}  (stop: {s['stop_reason']})")
    print(f"  Final avg_confidence   : {s['final_avg_confidence']}")
    print(f"  Items for review       : {len(s['items_for_review'])}")
    print(f"    {s['items_for_review']}")

    # --- Per-item results ---
    print(f"\n{'='*70}")
    print(f"ASSESSMENTS  ({len(assessments)} items)")
    print(f"{'='*70}")
    penalty_ok = True
    for a in assessments:
        flag = " ⚑" if a.flag_review else "  "
        print(
            f"  {flag} [{a.criterion_id:<20}] {a.status:<14} "
            f"penalty={a.checklist_penalty:.2f}  applied={a.applied_penalty:.2f}  "
            f"conf={a.confidence:.2f}"
        )
        if a.status in ("cumprido", "nao_aplicavel") and a.applied_penalty != 0.0:
            print(f"    *** ERROR: applied_penalty should be 0.0")
            penalty_ok = False
        elif a.status == "nao_cumprido" and a.applied_penalty != a.checklist_penalty:
            print(f"    *** ERROR: applied_penalty {a.applied_penalty} != checklist_penalty {a.checklist_penalty}")
            penalty_ok = False

    has_plan_log = sum(1 for a in assessments if a.plan_log is not None)
    print(f"\n  applied_penalty rules : {'PASS' if penalty_ok else 'FAIL'}")
    print(f"  Items with plan_log   : {has_plan_log}  (expected: 1)")

    print(f"\n  Output written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
