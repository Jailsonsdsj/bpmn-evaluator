from __future__ import annotations

from collections import Counter
from pathlib import Path

from agents.agent2_evaluator.loaders import load_evidence

MOCK_PATH = Path(__file__).parent / "mocks" / "mock_bpmn_evidence.json"


def main() -> None:
    evidence_list = load_evidence(MOCK_PATH)

    status_counts = Counter(e.status for e in evidence_list)
    category_counts = Counter(e.category for e in evidence_list)

    print(f"Total items   : {len(evidence_list)}")
    print()
    print("Status breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status:<12}: {count}")
    print()
    print("Category breakdown:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category:<20}: {count}")


if __name__ == "__main__":
    main()
