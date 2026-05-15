# Agent 1 — Criteria Mapper

Receives the BPMN diagram JSON and the evaluation checklist.
For each criterion, maps whether the corresponding element is present, absent, or incorrect.
Outputs a list of `BPMNEvidence` objects — no judgment, only evidence mapping.
