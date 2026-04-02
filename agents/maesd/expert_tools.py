from __future__ import annotations

import json
import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from .schema import DesignCandidate, DesignConstraints


EXPERT_METRIC_ALIASES: Dict[str, Dict[str, List[List[str]]]] = {
    "structural_expert": {
        "fold_confidence": [["metrics", "fold_confidence"], ["summary", "fold_confidence"], ["qa", "global_score"], ["confidence"]],
        "topology_score": [["metrics", "topology_score"], ["summary", "topology_score"], ["topology", "agreement"], ["template", "tm_score"]],
    },
    "function_expert": {
        "site_probability": [["metrics", "site_probability"], ["sites", "active_site_probability"], ["summary", "site_probability"]],
        "motif_retention": [["metrics", "motif_retention"], ["motifs", "retention"], ["summary", "motif_retention"]],
    },
    "developability_expert": {
        "solubility_score": [["metrics", "solubility_score"], ["developability", "solubility_score"], ["summary", "solubility"]],
        "aggregation_risk": [["metrics", "aggregation_risk"], ["developability", "aggregation_risk"], ["aggregation", "risk"]],
    },
    "binding_expert": {
        "docking_score": [["metrics", "docking_score"], ["docking", "normalized_score"], ["summary", "docking_score"]],
        "pose_agreement": [["metrics", "pose_agreement"], ["docking", "pose_agreement"], ["poses", "agreement"]],
        "cofactor_fit": [["metrics", "cofactor_fit"], ["cofactor", "fit_score"], ["summary", "cofactor_fit"]],
    },
}


@dataclass
class ToolSignal:
    source: str
    metrics: Dict[str, float]
    notes: List[str]
    raw_payload: Dict[str, object]


def load_tool_signal(expert_name: str, candidate: DesignCandidate, constraints: DesignConstraints) -> ToolSignal | None:
    command_template = os.getenv(f"MAESD_{expert_name.upper()}_TOOL_CMD", "").strip()
    if not command_template:
        return None
    pdb_path = str(candidate.structure.artifacts.get("pdb_path", "")) if candidate.structure else ""
    output_dir = Path(tempfile.mkdtemp(prefix=f"maesd_{expert_name}_"))
    output_json = output_dir / "result.json"
    substitutions = {
        "sequence": candidate.sequence,
        "prompt": constraints.original_prompt,
        "pdb_path": pdb_path,
        "candidate_origin": candidate.origin,
        "iteration": str(candidate.iteration),
        "output_dir": str(output_dir),
        "output_json": str(output_json),
        "expert_name": expert_name,
    }
    command = shlex.split(command_template.format(**substitutions), posix=False)
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        return ToolSignal(source=expert_name, metrics={}, notes=[result.stderr.strip() or "tool command failed"], raw_payload={})
    payload = _resolve_payload(result.stdout, output_json, output_dir)
    if payload is None:
        return ToolSignal(source=expert_name, metrics={}, notes=["tool output could not be parsed"], raw_payload={})
    metrics = _normalize_metrics(expert_name, payload)
    notes = _collect_notes(payload)
    return ToolSignal(
        source=str(payload.get("source", payload.get("tool_name", expert_name))),
        metrics=metrics,
        notes=notes,
        raw_payload=payload,
    )


def merge_focus_metrics(base: Dict[str, float], signal: ToolSignal | None) -> Dict[str, float]:
    merged = dict(base)
    if signal is None:
        return merged
    merged.update(signal.metrics)
    return merged


def append_tool_notes(rationale: str, signal: ToolSignal | None) -> str:
    if signal is None or (not signal.metrics and not signal.notes):
        return rationale
    suffix = f" Tool source: {signal.source}."
    if signal.notes:
        suffix += f" Notes: {'; '.join(signal.notes[:2])}."
    return rationale + suffix


def _resolve_payload(stdout: str, output_json: Path, output_dir: Path) -> Dict[str, object] | None:
    payload = _parse_payload(stdout)
    if payload is not None:
        return payload
    if output_json.exists():
        return _parse_payload(output_json.read_text(encoding="utf-8", errors="ignore"))
    json_files = sorted(output_dir.glob("*.json")) + sorted(output_dir.glob("**/*.json"))
    for path in json_files:
        parsed = _parse_payload(path.read_text(encoding="utf-8", errors="ignore"))
        if parsed is not None:
            return parsed
    return None


def _normalize_metrics(expert_name: str, payload: Dict[str, object]) -> Dict[str, float]:
    aliases = EXPERT_METRIC_ALIASES.get(expert_name, {})
    metrics: Dict[str, float] = {}
    direct_metrics = payload.get("metrics", {})
    if isinstance(direct_metrics, dict):
        for key, value in direct_metrics.items():
            if isinstance(value, (int, float)):
                metrics[str(key)] = float(value)
    for metric_name, candidate_paths in aliases.items():
        if metric_name in metrics:
            continue
        value = _lookup_numeric(payload, candidate_paths)
        if value is not None:
            metrics[metric_name] = value
    return metrics


def _lookup_numeric(payload: Dict[str, object], paths: Iterable[List[str]]) -> float | None:
    for path in paths:
        current: object = payload
        for key in path:
            if not isinstance(current, dict) or key not in current:
                current = None
                break
            current = current[key]
        if isinstance(current, (int, float)):
            return float(current)
    return None


def _collect_notes(payload: Dict[str, object]) -> List[str]:
    notes: List[str] = []
    raw_notes = payload.get("notes", [])
    if isinstance(raw_notes, list):
        notes.extend(str(item) for item in raw_notes if item)
    summary = payload.get("summary", {})
    if isinstance(summary, dict):
        for key in ("status", "model", "tool_version"):
            value = summary.get(key)
            if value:
                notes.append(f"{key}={value}")
    return list(dict.fromkeys(notes))[:4]


def _parse_payload(text: str) -> Dict[str, object] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
