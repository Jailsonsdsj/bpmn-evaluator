from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import Sequence

from agents.agent1_analyst.agent import Agent1Analyst

OUTPUT_FILENAME = "BPMNEvidence.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent1-analyst",
        description="Executa o Agente 1 (Criteria Mapper) via terminal.",
    )
    parser.add_argument("--diagram", type=str, help="Caminho do diagrama BPMN (.json, .pdf, .png, .jpg).")
    parser.add_argument("--checklist", type=str, help="Caminho do checklist (.json, .txt ou .csv).")
    parser.add_argument(
        "--enunciado",
        type=str,
        default=None,
        help="Caminho do enunciado/instruções do processo (.txt). Necessário para critérios P1-P5 e BP6.",
    )
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
        help="Abre a interface gráfica com seleção de diagramas e checklist.",
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


def _build_output_file_path(output_target: str) -> Path:
    target = Path(output_target)
    directory = target.parent if target.suffix else target
    return directory / OUTPUT_FILENAME


def _output_path_for_diagram(output_dir: str, diagram_path: str, multiple: bool) -> Path:
    base_dir = Path(output_dir)
    if not multiple:
        return base_dir / OUTPUT_FILENAME

    stem = Path(diagram_path).stem
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).strip("_") or "diagram"
    return base_dir / sanitized / OUTPUT_FILENAME


def _run_gui() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception as exc:  # pragma: no cover - depends on local Python install
        raise RuntimeError(
            "Interface gráfica indisponível. Instale/suporte Tkinter ou use --interactive."
        ) from exc

    agent = Agent1Analyst()
    diagram_paths: list[str] = []
    checklist_path: str | None = None

    project_root = Path(__file__).resolve().parents[2]
    dataset_dir = str(project_root / "evaluation" / "dataset")

    root = tk.Tk()
    root.title("Agent 1 — Criteria Mapper")
    root.geometry("560x320")
    root.resizable(False, False)

    instructions = (
        "1) Adicione um ou mais diagramas BPMN (JSON, PDF ou imagem)\n"
        "2) Adicione o checklist (TXT, CSV ou JSON)\n"
        "3) Clique em Executar para gerar o BPMNEvidence.json"
    )
    tk.Label(root, text=instructions, justify="left", anchor="w").pack(padx=16, pady=(16, 10), fill="x")

    status_frame = tk.Frame(root)
    status_frame.pack(padx=16, pady=(0, 12), fill="x")

    diagrams_label = tk.Label(status_frame, text="Diagramas anexados: 0", anchor="w")
    diagrams_label.pack(fill="x")

    checklist_label = tk.Label(status_frame, text="Checklist anexado: não", anchor="w")
    checklist_label.pack(fill="x")

    def update_status() -> None:
        diagrams_label.config(text=f"Diagramas anexados: {len(diagram_paths)}")
        checklist_label.config(text=f"Checklist anexado: {'sim' if checklist_path else 'não'}")

    def add_diagrams() -> None:
        paths = filedialog.askopenfilenames(
            title="Selecione um ou mais diagramas BPMN (JSON, PDF ou imagem)",
            initialdir=dataset_dir,
            filetypes=[
                ("Diagramas", "*.json *.pdf *.png *.jpg *.jpeg"),
                ("JSON", "*.json"),
                ("PDF", "*.pdf"),
                ("Imagens", "*.png *.jpg *.jpeg"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if paths:
            diagram_paths.clear()
            diagram_paths.extend(paths)
            update_status()

    def add_checklist() -> None:
        nonlocal checklist_path
        path = filedialog.askopenfilename(
            title="Selecione o checklist (.txt, .csv ou .json)",
            initialdir=dataset_dir,
            filetypes=[
                ("Checklist", "*.txt *.csv *.json"),
                ("CSV", "*.csv"),
                ("Texto", "*.txt"),
                ("JSON", "*.json"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if path:
            checklist_path = path
            update_status()

    def run_agent() -> None:
        if not diagram_paths:
            messagebox.showerror("Erro", "Adicione pelo menos um diagrama.")
            return
        if not checklist_path:
            messagebox.showerror("Erro", "Adicione o checklist.")
            return

        output_dir = str(project_root / "evaluation" / "results")

        try:
            multiple = len(diagram_paths) > 1
            for diagram_path in diagram_paths:
                evidences = agent.run_from_files(diagram_path, checklist_path)
                payload = agent.serialize(evidences)
                output_file = _output_path_for_diagram(output_dir, diagram_path, multiple)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(payload, encoding="utf-8")
            messagebox.showinfo("Concluído", f"Arquivos salvos em: {output_dir}")
        except Exception as exc:  # keep explicit
            messagebox.showerror("Erro", str(exc))

    buttons_frame = tk.Frame(root)
    buttons_frame.pack(padx=16, pady=(0, 12), fill="x")

    tk.Button(buttons_frame, text="Adicionar diagramas", width=22, command=add_diagrams).pack(side="left")
    tk.Button(buttons_frame, text="Adicionar checklist", width=22, command=add_checklist).pack(side="left", padx=8)
    tk.Button(buttons_frame, text="Executar", width=14, command=run_agent).pack(side="right")

    root.mainloop()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.gui or (not args.interactive and not args.diagram and not args.checklist):
            return _run_gui()
        else:
            interactive = args.interactive or not (args.diagram and args.checklist)

            if interactive:
                print("=== Agent 1 — Criteria Mapper ===")
                diagram_path = _ask_existing_path("Caminho do diagrama (.json, .pdf, .png, .jpg): ")
                checklist_path = _ask_existing_path("Caminho do checklist (.json, .txt ou .csv): ")
                output_path = ""
            else:
                diagram_path = args.diagram
                checklist_path = args.checklist
                output_path = (args.output or "").strip()
    except RuntimeError as exc:
        print(f"Erro: {exc}")
        return 2

    agent = Agent1Analyst()
    enunciado_path = getattr(args, "enunciado", None)
    try:
        evidences = agent.run_from_files(diagram_path, checklist_path, enunciado_path=enunciado_path)
    except ValueError as exc:
        print(f"Erro: {exc}")
        return 2

    payload = agent.serialize(evidences)

    if args.interactive or not (args.diagram and args.checklist):
        output_path = input(
            "Pasta de saída (ENTER para imprimir no terminal; arquivo será BPMNEvidence.json): "
        ).strip().strip('"')

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
