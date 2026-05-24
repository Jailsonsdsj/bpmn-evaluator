from __future__ import annotations

from pathlib import Path

from agents.agent2_evaluator.evaluator import evaluate_once
from agents.agent2_evaluator.loaders import load_checklist, load_evidence
from agents.agent2_evaluator.planning import generate_analysis_plan

REAL_EVIDENCE_PATH = (
    Path(__file__).parents[2] / "evaluation" / "results" / "BPMNEvidence.json"
)
CHECKLIST_PATH = (
    Path(__file__).parents[2]
    / "evaluation"
    / "dataset"
    / "Checklist completo - Modelagem 1 - Básico.csv"
)


def main() -> None:
    print("Loading evidence and checklist...")
    evidence_list = load_evidence(REAL_EVIDENCE_PATH)
    checklist = load_checklist(CHECKLIST_PATH)
    print(f"  Evidence items : {len(evidence_list)}")
    print(f"  Checklist keys : {len(checklist)}")

    print("\nGenerating analysis plan...")
    plan = generate_analysis_plan(evidence_list)
    print(f"  Plan length    : {len(plan)} chars")

    print("\nRunning single-pass evaluation...")
    assessments = evaluate_once(evidence_list, checklist, plan)

    print(f"\n{'='*70}")
    print(f"ASSESSMENT RESULTS  ({len(assessments)} items)")
    print(f"{'='*70}")

    penalty_ok = True
    for a in assessments:
        flag = " ⚑ FLAG" if a.flag_review else ""
        print(
            f"\n[{a.criterion_id}]  status={a.status:<14} "
            f"checklist_penalty={a.checklist_penalty:.2f}  "
            f"applied_penalty={a.applied_penalty:.2f}  "
            f"confidence={a.confidence:.2f}{flag}"
        )
        print(f"  {a.justification[:120]}{'...' if len(a.justification) > 120 else ''}")

        # Verify applied_penalty rule
        if a.status in ("present", "not_applicable"):
            if a.applied_penalty != 0.0:
                print(f"  *** ERROR: applied_penalty should be 0.0 for status={a.status}")
                penalty_ok = False
        else:  # absent / incorrect
            if a.applied_penalty != a.checklist_penalty:
                print(
                    f"  *** ERROR: applied_penalty {a.applied_penalty} "
                    f"!= checklist_penalty {a.checklist_penalty}"
                )
                penalty_ok = False

    print(f"\n{'='*70}")
    total_applied = sum(a.applied_penalty for a in assessments)
    flagged = [a for a in assessments if a.flag_review]
    has_plan_log = sum(1 for a in assessments if a.plan_log is not None)
    print(f"Total applied_penalty : {total_applied:.2f}")
    print(f"Flagged for review    : {len(flagged)}")
    print(f"Items with plan_log   : {has_plan_log}  (expected: 1, first item only)")
    print(f"applied_penalty rules : {'PASS' if penalty_ok else 'FAIL'}")


if __name__ == "__main__":
    main()
