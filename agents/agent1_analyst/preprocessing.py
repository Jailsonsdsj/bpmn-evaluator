"""Deterministic structural pre-processing for LucidChart BPMN diagrams.

All functions work on the RAW shapes/lines arrays extracted directly from
pages[*].items before normalization, so they see every element class
(BPMNGateway, BPMNEvent, BPMNAdvancedPoolBlock, ProcessBlock, …).

Public API
----------
build_connectivity_map(shapes, lines)   -> ConnMap
build_lane_map(shapes)                  -> LaneMap
classify_events(shapes, connectivity)   -> EventMap
resolve_structural_criteria(code, ...)  -> (status, observation)
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Types (for documentation; not enforced at runtime)
# ---------------------------------------------------------------------------

ConnMap = dict[str, dict[str, Any]]
"""
{ element_id: { "inflows": [{"from": id}],
                "outflows": [{"to": id, "label": str}],
                "in_degree": int,
                "out_degree": int } }
"""

LaneMap = dict[str, Any]
"""
{ "pools": [ { "pool_id": str, "pool_name": str,
               "lanes": [str, ...],
               "contained_shapes": [str, ...] } ],
  "element_to_pool": { element_id: pool_id },
  "has_lanes": bool }
"""

EventMap = dict[str, str]
"""{ event_id: "start" | "end" | "intermediate" | "isolated" }"""


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _shape_name(shape: dict[str, Any]) -> str:
    """Return the first non-empty text from a shape's textAreas."""
    for area in shape.get("textAreas") or []:
        txt = str(area.get("text", "")).strip()
        if txt:
            return txt
    return ""


# ---------------------------------------------------------------------------
# Function 1 — connectivity map
# ---------------------------------------------------------------------------

def build_connectivity_map(shapes: list[dict[str, Any]], lines: list[dict[str, Any]]) -> ConnMap:
    """Build inflow/outflow adjacency for every shape.

    Iterates ALL lines on the page (not only those listed in a pool's
    contains). Lines missing either endpoint are silently skipped.
    The line label is the first non-empty text in its textAreas, or "".
    """
    conn: ConnMap = {}

    for shape in shapes:
        sid = shape.get("id")
        if sid:
            conn[sid] = {"inflows": [], "outflows": [], "in_degree": 0, "out_degree": 0}

    for line in lines:
        ep1 = line.get("endpoint1") or {}
        ep2 = line.get("endpoint2") or {}
        src = ep1.get("connectedTo")
        tgt = ep2.get("connectedTo")

        if not src or not tgt:
            continue

        label = ""
        for area in line.get("textAreas") or []:
            txt = str(area.get("text", "")).strip()
            if txt:
                label = txt
                break

        if src not in conn:
            conn[src] = {"inflows": [], "outflows": [], "in_degree": 0, "out_degree": 0}
        if tgt not in conn:
            conn[tgt] = {"inflows": [], "outflows": [], "in_degree": 0, "out_degree": 0}

        conn[src]["outflows"].append({"to": tgt, "label": label})
        conn[src]["out_degree"] += 1
        conn[tgt]["inflows"].append({"from": src})
        conn[tgt]["in_degree"] += 1

    return conn


# ---------------------------------------------------------------------------
# Function 2 — lane / pool map
# ---------------------------------------------------------------------------

def build_lane_map(shapes: list[dict[str, Any]]) -> LaneMap:
    """Extract pool and lane structure from BPMNAdvancedPoolBlock shapes.

    A single pool WITH lane entries in Primary_0, Primary_1, …  is treated
    as "has_lanes=True". The fact that it is the only pool does NOT suppress
    the lane flag.
    """
    pools: list[dict[str, Any]] = []
    element_to_pool: dict[str, str] = {}

    for shape in shapes:
        if shape.get("class") != "BPMNAdvancedPoolBlock":
            continue

        pool_id = shape.get("id", "")
        pool_name = ""
        lane_entries: list[tuple[int, str]] = []

        for area in shape.get("textAreas") or []:
            lbl = area.get("label", "")
            txt = str(area.get("text", "")).strip()
            if lbl == "poolPrimaryTitleKey":
                pool_name = txt
            elif lbl.startswith("Primary_"):
                try:
                    idx = int(lbl.split("_", 1)[1])
                    lane_entries.append((idx, txt))
                except ValueError:
                    pass

        lanes = [t for _, t in sorted(lane_entries) if t]

        contained = list(shape.get("contains", {}).get("shapes", []))

        pools.append({
            "pool_id": pool_id,
            "pool_name": pool_name,
            "lanes": lanes,
            "contained_shapes": contained,
        })

        for eid in contained:
            element_to_pool[str(eid)] = pool_id

    has_lanes = any(len(p["lanes"]) > 0 for p in pools)

    return {
        "pools": pools,
        "element_to_pool": element_to_pool,
        "has_lanes": has_lanes,
    }


# ---------------------------------------------------------------------------
# Function 3 — event classification
# ---------------------------------------------------------------------------

def classify_events(shapes: list[dict[str, Any]], connectivity_map: ConnMap) -> EventMap:
    """Classify every shape whose class contains "Event" by flow degree.

    Role assignment:
      in_degree == 0 and out_degree > 0  -> "start"
      out_degree == 0 and in_degree > 0  -> "end"
      both > 0                           -> "intermediate"
      both == 0                          -> "isolated"
    """
    events: EventMap = {}

    for shape in shapes:
        if "Event" not in shape.get("class", ""):
            continue
        eid = shape.get("id")
        if not eid:
            continue

        c = connectivity_map.get(eid, {})
        in_d = c.get("in_degree", 0)
        out_d = c.get("out_degree", 0)

        if in_d == 0 and out_d > 0:
            events[eid] = "start"
        elif out_d == 0 and in_d > 0:
            events[eid] = "end"
        elif in_d > 0 and out_d > 0:
            events[eid] = "intermediate"
        else:
            events[eid] = "isolated"

    return events


# ---------------------------------------------------------------------------
# Function 4 — structural criteria resolver
# ---------------------------------------------------------------------------

def resolve_structural_criteria(
    code: str,
    connectivity: ConnMap,
    lanes: LaneMap,
    events: EventMap,
    shapes: list[dict[str, Any]],
) -> tuple[str, str]:
    """Return (status, observation) for a structural criterion identified by its CSV code.

    status  ∈ { "cumprido", "nao_cumprido", "nao_aplicavel", "nao_avaliado" }
    observation  is a concrete, evidence-citing string.
    """
    pools = lanes.get("pools", [])
    element_to_pool = lanes.get("element_to_pool", {})
    has_lanes = lanes.get("has_lanes", False)

    gateways = [s for s in shapes if "Gateway" in s.get("class", "")]
    tasks = [s for s in shapes if s.get("class") == "ProcessBlock"]

    # ------------------------------------------------------------------
    # SI1 — sequence flows only within lanes / pool
    # ------------------------------------------------------------------
    if code == "SI1":
        if not pools:
            return "nao_avaliado", "Diagrama sem piscinas — não é possível verificar uso de fluxo de sequência."
        cross_pool: list[str] = []
        for shape in shapes:
            sid = shape.get("id")
            if not sid:
                continue
            c = connectivity.get(sid, {})
            for flow in c.get("outflows", []):
                tgt = flow.get("to", "")
                src_pool = element_to_pool.get(str(sid))
                tgt_pool = element_to_pool.get(str(tgt))
                if src_pool and tgt_pool and src_pool != tgt_pool:
                    src_name = _shape_name(shape) or sid
                    cross_pool.append(src_name)
        if cross_pool:
            return (
                "nao_cumprido",
                f"Conexões cruzando fronteiras de piscina (deveriam ser fluxos de mensagem): "
                f"{', '.join(set(cross_pool))}.",
            )
        return "cumprido", "Todos os fluxos de sequência conectam elementos dentro da mesma piscina."

    # ------------------------------------------------------------------
    # SI2 — message flows only between pools
    # ------------------------------------------------------------------
    if code == "SI2":
        if len(pools) < 2:
            return "nao_aplicavel", "Diagrama possui apenas uma piscina — critério de fluxo de mensagem não se aplica."
        return "nao_avaliado", "Múltiplas piscinas detectadas; tipo de conector não diferenciado no formato LucidChart."

    # ------------------------------------------------------------------
    # SI3 — gateways connected by sequence flow (in_degree>=1, out_degree>=1)
    # ------------------------------------------------------------------
    if code == "SI3":
        if not gateways:
            return "nao_aplicavel", "Diagrama não possui gateways."
        bad: list[str] = []
        ok_parts: list[str] = []
        for g in gateways:
            gid = g.get("id", "")
            gname = _shape_name(g) or gid
            c = connectivity.get(gid, {})
            in_d, out_d = c.get("in_degree", 0), c.get("out_degree", 0)
            if in_d < 1 or out_d < 1:
                bad.append(f"'{gname}' (entrada={in_d}, saída={out_d})")
            else:
                ok_parts.append(f"'{gname}' (entrada={in_d}, saída={out_d})")
        if bad:
            return "nao_cumprido", f"Gateway(s) sem conexões completas de fluxo de sequência: {'; '.join(bad)}."
        return "cumprido", f"Todos os gateways possuem fluxos de entrada e saída: {'; '.join(ok_parts)}."

    # ------------------------------------------------------------------
    # SI4 — each pool has >= 1 start event
    # ------------------------------------------------------------------
    if code == "SI4":
        if not pools:
            return "nao_aplicavel", "Diagrama não possui piscinas."
        bad_pools: list[str] = []
        for pool in pools:
            pool_events = [eid for eid in pool["contained_shapes"] if eid in events]
            if not any(events[eid] == "start" for eid in pool_events):
                bad_pools.append(pool["pool_name"] or pool["pool_id"])
        if bad_pools:
            return "nao_cumprido", f"Piscina(s) sem evento de início: {', '.join(bad_pools)}."
        start_names = []
        for pool in pools:
            for eid in pool["contained_shapes"]:
                if events.get(eid) == "start":
                    start_names.append(
                        _shape_name(next((s for s in shapes if s.get("id") == eid), {})) or eid
                    )
        return "cumprido", f"Cada piscina possui evento de início: {', '.join(start_names)}."

    # ------------------------------------------------------------------
    # SI5 — each pool has >= 1 end event
    # ------------------------------------------------------------------
    if code == "SI5":
        if not pools:
            return "nao_aplicavel", "Diagrama não possui piscinas."
        bad_pools: list[str] = []
        for pool in pools:
            pool_events = [eid for eid in pool["contained_shapes"] if eid in events]
            if not any(events[eid] == "end" for eid in pool_events):
                bad_pools.append(pool["pool_name"] or pool["pool_id"])
        if bad_pools:
            return "nao_cumprido", f"Piscina(s) sem evento de fim: {', '.join(bad_pools)}."
        end_names = []
        for pool in pools:
            for eid in pool["contained_shapes"]:
                if events.get(eid) == "end":
                    end_names.append(
                        _shape_name(next((s for s in shapes if s.get("id") == eid), {})) or eid
                    )
        return "cumprido", f"Cada piscina possui evento(s) de fim: {', '.join(end_names)}."

    # ------------------------------------------------------------------
    # SI6 — each pool has exactly 1 start event
    # ------------------------------------------------------------------
    if code == "SI6":
        if not pools:
            return "nao_aplicavel", "Diagrama não possui piscinas."
        issues: list[str] = []
        for pool in pools:
            pool_events = [eid for eid in pool["contained_shapes"] if eid in events]
            starts = [eid for eid in pool_events if events[eid] == "start"]
            if len(starts) != 1:
                pname = pool["pool_name"] or pool["pool_id"]
                issues.append(f"'{pname}' tem {len(starts)} evento(s) de início")
        if issues:
            return "nao_cumprido", "; ".join(issues) + "."
        return "cumprido", "Cada piscina possui exatamente 1 evento de início."

    # ------------------------------------------------------------------
    # SI8 — each gateway has out_degree >= 2
    # ------------------------------------------------------------------
    if code == "SI8":
        if not gateways:
            return "nao_aplicavel", "Diagrama não possui gateways."
        bad: list[str] = []
        ok_parts: list[str] = []
        for g in gateways:
            gid = g.get("id", "")
            gname = _shape_name(g) or gid
            c = connectivity.get(gid, {})
            out_d = c.get("out_degree", 0)
            if out_d < 2:
                bad.append(f"'{gname}' com {out_d} fluxo(s) de saída")
            else:
                labels = [f["label"] for f in c.get("outflows", []) if f.get("label")]
                lbl_str = ", ".join(labels) if labels else f"{out_d} fluxos"
                ok_parts.append(f"Gateway '{gname}' possui {out_d} fluxos de saída: {lbl_str}")
        if bad:
            return "nao_cumprido", f"Gateway(s) com menos de 2 fluxos de saída: {'; '.join(bad)}."
        return "cumprido", "; ".join(ok_parts) + "."

    # ------------------------------------------------------------------
    # SI12 — each lane has a name (responsible)
    # ------------------------------------------------------------------
    if code == "SI12":
        if not has_lanes:
            return "nao_aplicavel", "Diagrama não possui raias definidas."
        empty: list[str] = []
        all_lanes: list[str] = []
        for pool in pools:
            for i, lane in enumerate(pool.get("lanes", [])):
                if not lane.strip():
                    empty.append(f"Raia {i} da piscina '{pool['pool_name']}'")
                else:
                    all_lanes.append(lane)
        if empty:
            return "nao_cumprido", f"Raias sem responsável definido: {', '.join(empty)}."
        return "cumprido", f"Todas as raias possuem responsável: {', '.join(all_lanes)}."

    # ------------------------------------------------------------------
    # SI13 — each task belongs to exactly one pool
    # ------------------------------------------------------------------
    if code == "SI13":
        if not pools:
            return "nao_aplicavel", "Diagrama não possui piscinas."
        unassigned: list[str] = []
        for t in tasks:
            tid = t.get("id", "")
            if str(tid) not in element_to_pool:
                unassigned.append(_shape_name(t) or tid)
        if unassigned:
            return "nao_cumprido", f"Tarefa(s) fora de piscina/raia: {', '.join(unassigned)}."
        return "cumprido", f"Todas as {len(tasks)} tarefas estão associadas a exatamente uma piscina."

    # ------------------------------------------------------------------
    # SI15 — activities distributed across different lanes
    # ------------------------------------------------------------------
    if code == "SI15":
        if not has_lanes:
            return "nao_aplicavel", "Diagrama não possui raias — critério não se aplica."
        return (
            "nao_avaliado",
            "Distribuição de tarefas por raia requer dados espaciais (coordenadas) não disponíveis no JSON LucidChart.",
        )

    # ------------------------------------------------------------------
    # SE1 — every task has in_degree >= 1
    # ------------------------------------------------------------------
    if code == "SE1":
        if not tasks:
            return "nao_aplicavel", "Diagrama não possui tarefas."
        bad: list[str] = []
        for t in tasks:
            tid = t.get("id", "")
            c = connectivity.get(tid, {})
            if c.get("in_degree", 0) < 1:
                bad.append(_shape_name(t) or tid)
        if bad:
            return "nao_cumprido", f"Tarefa(s) sem fluxo de entrada: {', '.join(bad)}."
        return "cumprido", f"Todas as {len(tasks)} tarefas possuem fluxo de entrada."

    # ------------------------------------------------------------------
    # SE2 — every task has out_degree == 1
    # ------------------------------------------------------------------
    if code == "SE2":
        if not tasks:
            return "nao_aplicavel", "Diagrama não possui tarefas."
        bad: list[str] = []
        for t in tasks:
            tid = t.get("id", "")
            c = connectivity.get(tid, {})
            out_d = c.get("out_degree", 0)
            if out_d != 1:
                tname = _shape_name(t) or tid
                bad.append(f"'{tname}' ({out_d} saída(s))")
        if bad:
            return "nao_cumprido", f"Tarefa(s) com número incorreto de fluxos de saída: {', '.join(bad)}."
        return "cumprido", f"Todas as {len(tasks)} tarefas possuem exatamente 1 fluxo de saída."

    # ------------------------------------------------------------------
    # BP1 — start and end events have labels
    # ------------------------------------------------------------------
    if code == "BP1":
        shape_by_id = {s.get("id"): s for s in shapes}
        no_label: list[str] = []
        checked: list[str] = []
        for eid, role in events.items():
            if role not in ("start", "end"):
                continue
            shape = shape_by_id.get(eid, {})
            name = _shape_name(shape)
            role_label = "início" if role == "start" else "fim"
            if not name:
                no_label.append(f"Evento de {role_label} sem rótulo ({eid})")
            else:
                checked.append(f"'{name}' ({role_label})")
        if not checked and not no_label:
            return "nao_aplicavel", "Diagrama não possui eventos de início ou fim identificáveis."
        if no_label:
            return "nao_cumprido", "; ".join(no_label) + "."
        return "cumprido", f"Eventos de início/fim com rótulo: {', '.join(checked)}."

    # ------------------------------------------------------------------
    # BP3 — gateways have convergence when applicable
    # ------------------------------------------------------------------
    if code == "BP3":
        if not gateways:
            return "nao_aplicavel", "Diagrama não possui gateways."
        diverging = [g for g in gateways if connectivity.get(g.get("id", ""), {}).get("out_degree", 0) >= 2]
        converging = [g for g in gateways if connectivity.get(g.get("id", ""), {}).get("in_degree", 0) >= 2]
        if not diverging:
            return "cumprido", "Nenhum gateway de divergência encontrado — convergência não aplicável."
        if not converging:
            div_names = [f"'{_shape_name(g) or g.get('id', '')}'" for g in diverging]
            return (
                "nao_cumprido",
                f"Gateway(s) de divergência sem gateway de convergência correspondente: "
                f"{', '.join(div_names)}.",
            )
        conv_names = [f"'{_shape_name(g) or g.get('id', '')}'" for g in converging]
        return "cumprido", f"Convergência(s) presente(s): {', '.join(conv_names)}."

    # ------------------------------------------------------------------
    # BP10 — no two tasks share an identical name
    # ------------------------------------------------------------------
    if code == "BP10":
        if not tasks:
            return "nao_aplicavel", "Diagrama não possui tarefas."
        name_counts: dict[str, int] = {}
        for t in tasks:
            name = _shape_name(t).strip().lower()
            if name:
                name_counts[name] = name_counts.get(name, 0) + 1
        duplicates = [name for name, cnt in name_counts.items() if cnt > 1]
        if duplicates:
            return "nao_cumprido", f"Tarefas com nome duplicado: {', '.join(duplicates)}."
        return "cumprido", f"Nenhuma tarefa redundante ({len(tasks)} tarefas com nomes únicos)."

    # ------------------------------------------------------------------
    # L4 — every non-pool/non-annotation element is connected
    # ------------------------------------------------------------------
    if code == "L4":
        _skip_classes = {"BPMNAdvancedPoolBlock", "BPMNPool", "PoolBlock"}
        isolated: list[str] = []
        for s in shapes:
            cls = s.get("class", "")
            if any(cls.startswith(sk) for sk in _skip_classes):
                continue
            sid = s.get("id", "")
            c = connectivity.get(sid, {})
            if c.get("in_degree", 0) == 0 and c.get("out_degree", 0) == 0:
                isolated.append(_shape_name(s) or sid)
        if isolated:
            return "nao_cumprido", f"Elemento(s) sem conexão ao fluxo: {', '.join(isolated)}."
        return "cumprido", "Todos os elementos estão conectados ao fluxo do processo."

    # ------------------------------------------------------------------
    # SI7 — end event established on alternative/interrupting branch
    # ------------------------------------------------------------------
    if code == "SI7":
        if not gateways:
            return "nao_aplicavel", "Diagrama não possui gateways — critério não se aplica."

        end_event_ids = {eid for eid, role in events.items() if role == "end"}
        shape_by_id = {s.get("id"): s for s in shapes}

        # Decision gateways: those with two or more outflows
        decision_gateways = [
            g for g in gateways
            if connectivity.get(g.get("id", ""), {}).get("out_degree", 0) >= 2
        ]
        if not decision_gateways:
            return "nao_aplicavel", "Nenhum gateway de decisão com múltiplos fluxos encontrado."

        confirmed: list[str] = []
        for g in decision_gateways:
            gid = g.get("id", "")
            gname = _shape_name(g) or gid
            c = connectivity.get(gid, {})
            for flow in c.get("outflows", []):
                tgt = flow.get("to", "")
                if tgt in end_event_ids:
                    end_name = _shape_name(shape_by_id.get(tgt, {})) or tgt
                    label = flow.get("label", "")
                    path_desc = f"'{label}'" if label else "alternativo"
                    confirmed.append(
                        f"Caminho {path_desc} de '{gname}' termina no evento de fim '{end_name}'"
                    )

        if confirmed:
            return "cumprido", "; ".join(confirmed) + "."
        return (
            "nao_aplicavel",
            "Nenhum caminho alternativo de gateway termina diretamente em evento de fim.",
        )

    # ------------------------------------------------------------------
    # BP2 — exclusive gateways have a label and all outflows are labelled
    # ------------------------------------------------------------------
    if code == "BP2":
        if not gateways:
            return "nao_aplicavel", "Diagrama não possui gateways."

        unlabelled_gw: list[str] = []
        unlabelled_flows: list[str] = []
        ok_parts: list[str] = []

        for g in gateways:
            gid = g.get("id", "")
            gname = _shape_name(g) or gid
            c = connectivity.get(gid, {})

            if not gname:
                unlabelled_gw.append(gid)
                continue

            missing = [
                f.get("label", "") or "(sem rótulo)"
                for f in c.get("outflows", [])
                if not f.get("label", "").strip()
            ]
            if missing:
                unlabelled_flows.append(
                    f"Gateway '{gname}' tem {len(missing)} saída(s) sem rótulo"
                )
            else:
                labels = [f["label"] for f in c.get("outflows", []) if f.get("label")]
                lbl_str = ", ".join(labels) if labels else "(sem saídas)"
                ok_parts.append(
                    f"Gateway '{gname}' tem rótulo e saídas rotuladas: {lbl_str}"
                )

        if unlabelled_gw:
            return "nao_cumprido", f"Gateway(s) sem rótulo: {', '.join(unlabelled_gw)}."
        if unlabelled_flows:
            return "nao_cumprido", "; ".join(unlabelled_flows) + "."
        return "cumprido", "; ".join(ok_parts) + "."

    return "nao_avaliado", f"Código '{code}' não mapeado no resolvedor estrutural."
