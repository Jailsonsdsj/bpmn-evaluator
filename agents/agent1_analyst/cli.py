from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from agents.agent1_analyst.agent import Agent1Analyst

OUTPUT_FILENAME = "BPMNEvidence.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent1-analyst",
        description="Executa o Agente 1 (Criteria Mapper) via terminal.",
    )
    parser.add_argument("--diagram", type=str, help="Caminho do JSON do diagrama BPMN.")
    parser.add_argument("--checklist", type=str, help="Caminho do checklist (.json ou .txt).")
    parser.add_argument(
        "--output",
        type=str,
        help="Diretório opcional para salvar a saída (arquivo fixo: BPMNEvidence.json).",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Força interação por terminal (prompt para caminhos).",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Abre seletores gráficos para diagrama/checklist e, ao final, pasta de saída.",
    )
    return parser


def _ask_existing_path(prompt: str) -> str:
    while True:
        value = input(prompt).strip().strip('"')
        if not value:
            print("Valor vazio. Tente novamente.")
            continue
        path = Path(value)
        if path.exists() and path.is_file():
            return str(path)
        print(f"Arquivo não encontrado: {path}")


def _select_paths_with_gui() -> tuple[str, str]:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python install
        raise RuntimeError(
            "Interface gráfica indisponível. Instale/suporte Tkinter ou use --interactive."
        ) from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    diagram_path = filedialog.askopenfilename(
        title="Selecione o JSON do diagrama BPMN",
        filetypes=[("JSON", "*.json"), ("Todos os arquivos", "*.*")],
    )
    if not diagram_path:
        raise RuntimeError("Seleção cancelada: diagrama não informado.")

    checklist_path = filedialog.askopenfilename(
        title="Selecione o checklist (.json ou .txt)",
        filetypes=[("Checklist", "*.json *.txt"), ("JSON", "*.json"), ("Texto", "*.txt"), ("Todos os arquivos", "*.*")],
    )
    if not checklist_path:
        raise RuntimeError("Seleção cancelada: checklist não informado.")

    root.destroy()

    return diagram_path, checklist_path


def _select_output_dir_with_gui() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:  # pragma: no cover - depends on local Python install
        raise RuntimeError(
            "Interface gráfica indisponível. Instale/suporte Tkinter ou use --interactive."
        ) from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    output_dir = filedialog.askdirectory(title="Selecione a pasta para salvar BPMNEvidence.json")
    root.destroy()
    return output_dir or ""


def _build_output_file_path(output_target: str) -> Path:
    target = Path(output_target)
    directory = target.parent if target.suffix else target
    return directory / OUTPUT_FILENAME


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.gui:
            diagram_path, checklist_path = _select_paths_with_gui()
            output_path = ""
        else:
            interactive = args.interactive or not (args.diagram and args.checklist)

            if interactive:
                print("=== Agent 1 — Criteria Mapper ===")
                diagram_path = _ask_existing_path("Caminho do JSON do diagrama: ")
                checklist_path = _ask_existing_path("Caminho do checklist (.json ou .txt): ")
                output_path = ""
            else:
                diagram_path = args.diagram
                checklist_path = args.checklist
                output_path = (args.output or "").strip()
    except RuntimeError as exc:
        print(f"Erro: {exc}")
        return 2

    agent = Agent1Analyst()
    try:
        evidences = agent.run_from_files(diagram_path, checklist_path)
    except ValueError as exc:
        print(f"Erro: {exc}")
        return 2

    payload = agent.serialize(evidences)

    try:
        if args.gui:
            output_path = _select_output_dir_with_gui()
        elif args.interactive or not (args.diagram and args.checklist):
            output_path = input(
                "Pasta de saída (ENTER para imprimir no terminal; arquivo será BPMNEvidence.json): "
            ).strip().strip('"')
    except RuntimeError as exc:
        print(f"Erro: {exc}")
        return 2

    if output_path:
        output_file = _build_output_file_path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(payload, encoding="utf-8")
        print(f"Saída salva em: {output_file}")
    else:
        print(payload)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
