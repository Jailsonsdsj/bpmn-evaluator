from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import Sequence

from agents.agent3_feedback import Agent3Feedback
from agents.contracts import *

OUTPUT_FILENAME = "BPMNFeedback.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent3-feedback",
        description="Executa o Agente 3 (Feedback) via terminal.",
    )
    parser.add_argument("--enunciado", type=str, help="Caminho do enunciado (.txt)")
    parser.add_argument("--diagram", type=str, help="Caminho do diagrama BPMN (.json, .pdf, .png, .jpg)")
    parser.add_argument("--assessment", type=str, help="Avaliação do diagrama (lista de BPMNAssessment)")
    parser.add_argument(
        "--output",
        type=str
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Força interação por terminal (prompt para caminhos).",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Abre a interface gráfica com seleção de diagramas e bpmnassessment.",
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

    agent = Agent3Feedback()
    diagram_paths: list[str] = []
    bpmnassessment_path: str | None = None
    enunciado_path: str | None = None

    root = tk.Tk()
    root.title("Agent 3 — Feedback")
    root.geometry("560x320")
    root.resizable(False, False)

    instructions = (
        "1) Adicione um ou mais diagramas BPMN (JSON, PDF ou imagem)\n"
        "2) Adicione o BPMNAssessment\n"
        "3) Clique em Executar para gerar o BPMNFeedback.json"
    )
    tk.Label(root, text=instructions, justify="left", anchor="w").pack(padx=16, pady=(16, 10), fill="x")

    status_frame = tk.Frame(root)
    status_frame.pack(padx=16, pady=(0, 12), fill="x")

    diagrams_label = tk.Label(status_frame, text="Diagramas anexados: 0", anchor="w")
    diagrams_label.pack(fill="x")

    bpmnassessment_label = tk.Label(status_frame, text="bpmnassessment anexado: não", anchor="w")
    bpmnassessment_label.pack(fill="x")

    def update_status() -> None:
        diagrams_label.config(text=f"Diagramas anexados: {len(diagram_paths)}")
        bpmnassessment_label.config(text=f"bpmnassessment anexado: {'sim' if bpmnassessment_path else 'não'}")

    def add_diagrams() -> None:
        paths = filedialog.askopenfilenames(
            title="Selecione um ou mais diagramas BPMN (JSON, PDF ou imagem)",
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
            
    def add_enunciado() -> None:
        nonlocal enunciado_path
        path = filedialog.askopenfilename(
            title="Selecione um enunciado",
            filetypes=[
                ("Enunciado", "*.txt"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if path:
            enunciado_path = path
            update_status()

    def add_bpmnassessment() -> None:
        nonlocal bpmnassessment_path
        path = filedialog.askopenfilename(
            title="Selecione o bpmnassessment"
        )
        if path:
            bpmnassessment_path = path
            update_status()

    def run_agent() -> None:
        if not enunciado_path:
            messagebox.showerror("Erro", "Adicione o enunciado.")
            return
        if not bpmnassessment_path:
            messagebox.showerror("Erro", "Adicione o bpmnassessment.")
            return

        output_dir = filedialog.askdirectory(title="Selecione a pasta para salvar BPMNFeedback.json")
        if not output_dir:
            messagebox.showinfo("Cancelado", "Nenhuma pasta de saída selecionada.")
            return

        try:
            multiple = len(diagram_paths) > 1
            for diagram_path in diagram_paths:
                feedback = agent.run_from_files(enunciado_path, diagram_path, bpmnassessment_path)
                payload = agent.serialize(feedback)
                output_file = _output_path_for_diagram(output_dir, diagram_path, multiple)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                output_file.write_text(payload, encoding="utf-8")
            messagebox.showinfo("Concluído", f"Arquivos salvos em: {output_dir}")
        except Exception as exc:  # keep explicit
            messagebox.showerror("Erro", str(exc))

    buttons_frame = tk.Frame(root)
    root.geometry("800x320")
    buttons_frame.pack(padx=16, pady=(0, 12), fill="x")

    tk.Button(buttons_frame, text="Adicionar enunciado", width=22, command=add_enunciado).pack(side="left")
    tk.Button(buttons_frame, text="Adicionar diagramas", width=22, command=add_diagrams).pack(side="left", padx=8)
    tk.Button(buttons_frame, text="Adicionar bpmnassessment", width=22, command=add_bpmnassessment).pack(side="left", padx=16)
    tk.Button(buttons_frame, text="Executar", width=14, command=run_agent).pack(side="right")

    root.mainloop()
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.gui or (not args.interactive and not args.diagram and not args.assessment):
            return _run_gui()
        else:
            interactive = args.interactive or not (args.diagram and args.assessment)

            if interactive:
                print("=== Agent 3 — Feedback ===")
                enunciado_path = _ask_existing_path("Caminho do enunciado (.txt): ")
                diagram_path = _ask_existing_path("Caminho do diagrama (.json, .pdf, .png, .jpg): ")
                bpmnassessment_path = _ask_existing_path("Caminho do bpmnassessment (.json, .txt ou .csv): ")
                output_path = ""
            else:
                enunciado_path = args.enunciado
                diagram_path = args.diagram
                bpmnassessment_path = args.assessment
                output_path = (args.output or "").strip()
                print(f"Enunciado: {enunciado_path}")
                print(f"Diagrama: {diagram_path}")
                print(f"BPMNAssessment: {bpmnassessment_path}")
                print(f"Output: {output_path}")
    except RuntimeError as exc:
        print(f"Erro: {exc}")
        return 2
    print("Executando no modo CLI")
    agent = Agent3Feedback()
    try:
        feedback = agent.run_from_files(enunciado_path, diagram_path, bpmnassessment_path)
    except ValueError as exc:
        print(f"Erro: {exc}")
        return 2

    print("Finalizado!")
    payload = agent.serialize(feedback)
    if args.interactive:
        output_path = input(
            "Pasta de saída (ENTER para imprimir no terminal; arquivo será BPMNFeedback.json): "
        ).strip().strip('"')
    if output_path:
        output_file = Path(output_path)
        output_file.write_text(payload, encoding="utf-8")
        print(f"Saída salva em: {output_file}")
    

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
