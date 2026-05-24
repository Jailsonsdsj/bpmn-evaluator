from __future__ import annotations

import structlog

from agents.contracts import BPMNAssessment, BPMNEvidence


class Agent2Evaluator:
    """Agent 2: applies checklist penalty criteria to BPMNEvidence from Agent 1.

    Uses a Planning + Reflection (Producer-Critic) loop to refine its output.
    Not yet implemented — stub only.
    """

    def __init__(self) -> None:
        self.logger = structlog.get_logger(self.__class__.__name__)

    def run(self, evidence_list: list[BPMNEvidence]) -> list[BPMNAssessment]:
        """Evaluate evidence and return a list of BPMNAssessment instances.

        Stub — evaluation logic not yet implemented.
        # Note: real Agent 1 output contains only 'present' and 'absent'; 'incorrect'
        # and 'not_applicable' are handled by the contract but absent in current data.
        """
        self.logger.info("agent2.start", total_evidence=len(evidence_list))
        assessments: list[BPMNAssessment] = []
        self.logger.info("agent2.finished", total_assessments=len(assessments))
        return assessments
