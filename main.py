from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

_DEFAULT_DIAGRAM    = ROOT / "evaluation" / "dataset" / "diagram_001.json"
_DEFAULT_CHECKLIST  = ROOT / "evaluation" / "dataset" / "Checklist completo - Modelagem 1 - Básico.csv"
_DEFAULT_ENUNCIADO  = ROOT / "evaluation" / "dataset" / "Instruções.txt"
_DEFAULT_OUTPUT_DIR = ROOT / "evaluation" / "results"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BPMN hybrid evaluation pipeline (Agent 1 → 2 → 3)")
    parser.add_argument("--diagram",   type=Path, default=_DEFAULT_DIAGRAM,
                        help=f"BPMN diagram JSON (default: {_DEFAULT_DIAGRAM})")
    parser.add_argument("--checklist", type=Path, default=_DEFAULT_CHECKLIST,
                        help=f"Checklist CSV (default: {_DEFAULT_CHECKLIST})")
    parser.add_argument("--enunciado", type=Path, default=_DEFAULT_ENUNCIADO,
                        help=f"Task statement text file (default: {_DEFAULT_ENUNCIADO})")
    parser.add_argument("--output",    type=Path, default=_DEFAULT_OUTPUT_DIR,
                        help=f"Output folder for all result files (default: {_DEFAULT_OUTPUT_DIR})")
    return parser.parse_args()


def _build_steps(diagram: Path, checklist: Path, enunciado: Path, output_dir: Path) -> list[dict]:
    evidence   = output_dir / "BPMNEvidence.json"
    assessment = output_dir / "BPMNAssessment.json"
    feedback   = output_dir / "BPMNFeedback.json"
    return [
        {
            "label": "Agent 1 — Criteria Mapper",
            "output": evidence,
            "cmd": [
                sys.executable, "-m", "agents.agent1_analyst",
                "--diagram",   str(diagram),
                "--checklist", str(checklist),
                "--output",    str(evidence),
            ],
        },
        {
            "label": "Agent 2 — Critic Validator",
            "output": assessment,
            "cmd": [
                sys.executable, "-m", "agents.agent2_evaluator",
                "--evidence",  str(evidence),
                "--checklist", str(checklist),
                "--output",    str(assessment),
            ],
        },
        {
            "label": "Agent 3 — Feedback Generator",
            "output": feedback,
            "cmd": [
                sys.executable, "-m", "agents.agent3_feedback",
                "--diagram",    str(diagram),
                "--enunciado",  str(enunciado),
                "--assessment", str(assessment),
                "--output",     str(feedback),
            ],
        },
    ]


def main() -> None:
    args = _parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    steps = _build_steps(args.diagram, args.checklist, args.enunciado, args.output)

    for n, step in enumerate(steps):
        print(f"\n{'='*70}")
        print(f"  {step['label']}")
        print(f"{'='*70}")
        result = subprocess.run(step["cmd"], cwd=ROOT)
        if result.returncode != 0:
            print(f"\nPipeline aborted: {step['label']} exited with code {result.returncode}.")
            sys.exit(result.returncode)
        if (n == 1):
            input("""Revise o BPMNAssessment.json gerado, aplicando a penalidade correta em cada assessment. Utilize a flag review para auxiliar.
                  
Pressione ENTER para continuar"""
            )

    print(f"\n{'='*70}")
    print("  Pipeline complete.")
    for step in steps:
        print(f"  {step['output']}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
