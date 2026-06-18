# Evaluation Dataset

Anonymized inputs from the BPM course corpus (2022.2–2024.2) used to run and
evaluate the pipeline. The task modeled in all diagrams is **"Processo de
Recrutamento e Seleção"** (see `Instruções.txt`).

The diagram JSON files are **raw LucidChart exports** (top-level keys
`id`, `title`, `product`, `pages`, `data`, `accountId`) — Agent 1 normalizes
them into the simplified `elements`/`flows` schema before evaluation.

## Files

| File | Description |
|------|-------------|
| `Instruções.txt` | Task statement (enunciado) — the recruitment & selection process. |
| `Checklist.csv` | Scored checklist (the evaluation instrument: category, item, pre-written feedback, penalty). |
| `OK_1.json` | LucidChart export of a model considered **correct** for the task. |
| `NOTOK_1.json` | LucidChart export of a model containing **modeling errors**. |
| `OK_1 - v2.json` | A second export sharing `OK_1.json`'s Lucid `id` (internal Lucid title: "Blank diagram"). |

The `OK_`/`NOTOK_` naming encodes the expected human verdict (ground truth)
for each submission.

**Rules:** do not modify existing files; never add personally identifiable data.
