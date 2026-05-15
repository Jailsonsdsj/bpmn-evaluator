# Agent 2 — Critic Evaluator

Receives `BPMNEvidence` from Agent 1 and applies checklist penalty criteria.
Uses a Planning + Reflection (Producer-Critic) loop to refine its own output.
Outputs a list of `BPMNAssessment` objects with penalty, justification, and confidence per item.
