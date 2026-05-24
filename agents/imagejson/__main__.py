"""Agente simples para converter uma imagem ou pdf de um diagrama num json

Execute com python -m agents.imagejson
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import Sequence
import json

from agents.shared_tools.diagram.reader import read_diagram_file

OUTPUT_FILENAME = "diagram.json"

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

    diagram_paths: list[str] = []
    checklist_path: str | None = None

    root = tk.Tk()
    root.title("Create Json from image/pdf")
    root.geometry("560x320")
    root.resizable(False, False)

    instructions = (
        "1) Adicione um ou mais diagramas BPMN (PDF ou imagem)\n"
        "2) Clique em Executar para gerar o json"
    )
    tk.Label(root, text=instructions, justify="left", anchor="w").pack(padx=16, pady=(16, 10), fill="x")

    status_frame = tk.Frame(root)
    status_frame.pack(padx=16, pady=(0, 12), fill="x")

    diagrams_label = tk.Label(status_frame, text="Diagramas anexados: 0", anchor="w")
    diagrams_label.pack(fill="x")

    def update_status() -> None:
        diagrams_label.config(text=f"Diagramas anexados: {len(diagram_paths)}")

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

    def run_agent() -> None:
        if not diagram_paths:
            messagebox.showerror("Erro", "Adicione pelo menos um diagrama.")
            return
        output_dir = filedialog.askdirectory(title="Selecione a pasta para salvar diagram.json")
        if not output_dir:
            messagebox.showinfo("Cancelado", "Nenhuma pasta de saída selecionada.")
            return

        try:
            multiple = len(diagram_paths) > 1
            for diagram_path in diagram_paths:
                diagram = read_diagram_file(diagram_path)
                output_file = _output_path_for_diagram(output_dir, diagram_path, multiple)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                to_json = diagram
                with output_file.open("w", encoding="utf-8") as file:
                    json.dump(to_json, file, ensure_ascii=True, indent=2)
            messagebox.showinfo("Concluído", f"Arquivos salvos em: {output_dir}")
        except Exception as exc:  # keep explicit
            messagebox.showerror("Erro", str(exc))

    buttons_frame = tk.Frame(root)
    buttons_frame.pack(padx=16, pady=(0, 12), fill="x")

    tk.Button(buttons_frame, text="Adicionar diagramas", width=22, command=add_diagrams).pack(side="left")
    tk.Button(buttons_frame, text="Executar", width=14, command=run_agent).pack(side="right")

    root.mainloop()
    return 0


if __name__ == "__main__":
    _run_gui()
 