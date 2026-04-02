from __future__ import annotations

import csv
import json
import os
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import requests
import yaml

from agents.system.tools.enzy_api import get_ec_info, search_ec_by_annotation
from agents.system.tools.go_api import get_go_definition, search_go_by_definition
from agents.system.tools.interpro_api import InterProSearcher


UNIPROT_SEARCH_URL = "https://rest.uniprot.org/uniprotkb/search"
PFAM_SEARCH_URL = "https://www.ebi.ac.uk/interpro/api/entry/pfam"


@dataclass
class RetrievalEvidence:
    source: str
    query: str
    items: List[Dict[str, str]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class ExternalKnowledgeConnector:
    name: str
    kind: str
    path: str | None = None
    command: List[str] = field(default_factory=list)
    enabled: bool = True


def enrich_go_term(term: str, timeout: int = 4) -> RetrievalEvidence:
    evidence = RetrievalEvidence(source="QuickGO", query=term)
    try:
        results, error = search_go_by_definition(term, max_results=5)
        if error:
            evidence.errors.append(error)
            return evidence
        for item in results[:3]:
            go_id = item.get("id", "")
            detail, _ = get_go_definition(go_id) if go_id else (None, None)
            evidence.items.append(
                {
                    "id": go_id,
                    "name": detail.get("name", item.get("name", "")) if detail else item.get("name", ""),
                    "description": detail.get("definition", item.get("definition", "")) if detail else item.get("definition", ""),
                }
            )
    except requests.RequestException as exc:
        evidence.errors.append(str(exc))
    except Exception as exc:
        evidence.errors.append(str(exc))
    return evidence


def enrich_ec_term(term: str, timeout: int = 4) -> RetrievalEvidence:
    evidence = RetrievalEvidence(source="Expasy/KEGG", query=term)
    try:
        results = search_ec_by_annotation(term)
        if isinstance(results, list):
            for item in results[:3]:
                if not isinstance(item, dict):
                    continue
                ec_id = item.get("EC_Number", "")
                detail, _ = get_ec_info(ec_id) if ec_id else (None, None)
                evidence.items.append(
                    {
                        "id": f"EC {ec_id}" if ec_id and not ec_id.startswith("EC ") else ec_id,
                        "name": detail.get("accepted_name", item.get("Description", "")) if detail else item.get("Description", ""),
                        "description": "; ".join(detail.get("reaction", [])[:1]) if detail else item.get("Description", ""),
                    }
                )
    except requests.RequestException as exc:
        evidence.errors.append(str(exc))
    except Exception as exc:
        evidence.errors.append(str(exc))
    return evidence


def enrich_domain_term(term: str, timeout: int = 4) -> RetrievalEvidence:
    evidence = RetrievalEvidence(source="InterPro", query=term)
    try:
        searcher = InterProSearcher()
        results = searcher.search(term, timeout=timeout) or []
        for item in results[:5]:
            evidence.items.append(
                {
                    "id": item.get("accession", ""),
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                    "type": item.get("type", ""),
                    "score": str(item.get("score", "")),
                }
            )
    except Exception as exc:
        evidence.errors.append(str(exc))
    return evidence


def search_uniprot(query: str, size: int = 3, timeout: int = 4) -> RetrievalEvidence:
    evidence = RetrievalEvidence(source="UniProt", query=query)
    try:
        params = {
            "query": query,
            "format": "json",
            "fields": "accession,protein_name,gene_names,organism_name,go_id,ec,cc_function",
            "size": size,
        }
        response = requests.get(UNIPROT_SEARCH_URL, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        for item in payload.get("results", []):
            protein_description = item.get("proteinDescription", {})
            recommended = protein_description.get("recommendedName", {})
            full_name = recommended.get("fullName", {}).get("value", "")
            genes = ",".join(gene.get("geneName", {}).get("value", "") for gene in item.get("genes", []) if gene.get("geneName"))
            comments = item.get("comments", [])
            function_text = ""
            for comment in comments:
                if comment.get("commentType") == "FUNCTION" and comment.get("texts"):
                    function_text = comment["texts"][0].get("value", "")
                    break
            evidence.items.append(
                {
                    "id": item.get("primaryAccession", ""),
                    "name": full_name,
                    "description": function_text,
                    "genes": genes,
                }
            )
    except Exception as exc:
        evidence.errors.append(str(exc))
    return evidence


def search_pfam(query: str, size: int = 3, timeout: int = 4) -> RetrievalEvidence:
    evidence = RetrievalEvidence(source="Pfam", query=query)
    try:
        response = requests.get(
            PFAM_SEARCH_URL,
            params={"search": query, "page_size": size},
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        for item in payload.get("results", [])[:size]:
            metadata = item.get("metadata", {})
            evidence.items.append(
                {
                    "id": metadata.get("accession", ""),
                    "name": metadata.get("name", ""),
                    "description": metadata.get("description", ""),
                    "type": metadata.get("type", ""),
                }
            )
    except Exception as exc:
        evidence.errors.append(str(exc))
    return evidence


def query_external_knowledge(
    query_terms: Sequence[str],
    text: str,
    tokens: Sequence[str],
    connector_config_path: str | None = None,
) -> Dict[str, object]:
    result: Dict[str, object] = {
        "go_evidence": [],
        "ec_evidence": [],
        "domain_evidence": [],
        "external_motif_hints": [],
        "external_goal_hints": [],
        "external_intent_hints": [],
        "external_translation_hints": [],
        "external_metal_constraints": [],
        "external_catalytic_constraints": [],
        "external_knowledge_hits": [],
        "external_connector_errors": [],
        "external_connectors": [],
    }
    connectors = load_external_connectors(connector_config_path)
    if not connectors:
        return result

    for connector in connectors:
        if not connector.enabled:
            continue
        result["external_connectors"].append(connector.name)
        try:
            records = _run_connector(connector, query_terms, text, tokens)
            matches = _match_external_records(records, query_terms, text, tokens)
            result["go_evidence"].extend(_collect_nested_annotations(matches, "go_terms"))
            result["ec_evidence"].extend(_collect_nested_annotations(matches, "ec_numbers"))
            result["domain_evidence"].extend(_collect_nested_annotations(matches, "domains"))
            result["external_motif_hints"].extend(_collect_string_values(matches, "motifs"))
            result["external_goal_hints"].extend(_collect_string_values(matches, "goals"))
            result["external_intent_hints"].extend(_collect_string_values(matches, "intent_hints"))
            result["external_translation_hints"].extend(_collect_string_values(matches, "translation_hints"))
            result["external_metal_constraints"].extend(_collect_object_values(matches, "metal_constraints"))
            result["external_catalytic_constraints"].extend(_collect_object_values(matches, "catalytic_constraints"))
            for item in matches:
                result["external_knowledge_hits"].append(
                    {
                        "source": connector.name,
                        "id": item.get("id", ""),
                        "label": item.get("label", ""),
                        "description": item.get("description", ""),
                        "score": item.get("_match_score", 0.0),
                    }
                )
        except Exception as exc:
            result["external_connector_errors"].append(f"{connector.name}: {exc}")

    result["go_evidence"] = merge_evidence_items(result["go_evidence"])
    result["ec_evidence"] = merge_evidence_items(result["ec_evidence"])
    result["domain_evidence"] = merge_evidence_items(result["domain_evidence"])
    result["external_motif_hints"] = list(dict.fromkeys(result["external_motif_hints"]))
    result["external_goal_hints"] = list(dict.fromkeys(result["external_goal_hints"]))
    result["external_intent_hints"] = list(dict.fromkeys(result["external_intent_hints"]))
    result["external_translation_hints"] = list(dict.fromkeys(result["external_translation_hints"]))
    result["external_knowledge_hits"] = sorted(
        result["external_knowledge_hits"],
        key=lambda item: float(item.get("score", 0.0)),
        reverse=True,
    )[:20]
    return result


def load_external_connectors(config_path: str | None = None) -> List[ExternalKnowledgeConnector]:
    resolved = config_path or os.getenv("MAESD_IRA_CONNECTORS", "").strip()
    if not resolved:
        return []
    path = Path(resolved)
    if not path.exists():
        return []
    payload = _load_structured_file(path)
    connectors = payload.get("connectors", payload if isinstance(payload, list) else [])
    result = []
    for item in connectors:
        if not isinstance(item, dict):
            continue
        command = item.get("command", [])
        if isinstance(command, str):
            command = shlex.split(command, posix=False)
        result.append(
            ExternalKnowledgeConnector(
                name=str(item.get("name", item.get("path", item.get("kind", "external")))),
                kind=str(item.get("kind", item.get("type", "file"))),
                path=str(item["path"]) if item.get("path") else None,
                command=[str(part) for part in command],
                enabled=bool(item.get("enabled", True)),
            )
        )
    return result


def merge_evidence_items(*sources: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    merged: Dict[str, Dict[str, str]] = {}
    for source in sources:
        for item in source:
            key = item.get("id") or item.get("name") or str(item)
            if key not in merged:
                merged[key] = dict(item)
    return list(merged.values())


def _run_connector(
    connector: ExternalKnowledgeConnector,
    query_terms: Sequence[str],
    text: str,
    tokens: Sequence[str],
) -> List[Dict[str, object]]:
    if connector.kind == "file":
        if not connector.path:
            return []
        records = _load_records_from_path(Path(connector.path))
    elif connector.kind == "command":
        records = _load_records_from_command(connector.command, query_terms, text, tokens)
    else:
        raise ValueError(f"Unsupported connector kind: {connector.kind}")
    return [_normalize_external_record(record) for record in records]


def _load_records_from_path(path: Path) -> List[Dict[str, object]]:
    payload = _load_structured_file(path)
    if isinstance(payload, dict):
        items = payload.get("records", payload.get("items", []))
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _load_records_from_command(
    command: Sequence[str],
    query_terms: Sequence[str],
    text: str,
    tokens: Sequence[str],
) -> List[Dict[str, object]]:
    if not command:
        return []
    substitutions = {
        "query": query_terms[0] if query_terms else "",
        "query_terms_json": json.dumps(list(query_terms), ensure_ascii=False),
        "text": text,
        "tokens_json": json.dumps(list(tokens), ensure_ascii=False),
    }
    rendered = [str(part).format(**substitutions) for part in command]
    result = subprocess.run(rendered, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"connector command failed: {' '.join(rendered)}")
    payload = json.loads(result.stdout.strip() or "[]")
    if isinstance(payload, dict):
        payload = payload.get("records", payload.get("items", []))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _load_structured_file(path: Path):
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            return [dict(row) for row in reader]
    raise ValueError(f"Unsupported connector file format: {path.suffix}")


def _normalize_external_record(raw: Dict[str, object]) -> Dict[str, object]:
    normalized = dict(raw)
    normalized["aliases"] = _ensure_list(raw.get("aliases"))
    normalized["motifs"] = _ensure_list(raw.get("motifs"))
    normalized["goals"] = _ensure_list(raw.get("goals"))
    normalized["intent_hints"] = _ensure_list(raw.get("intent_hints", raw.get("intents")))
    normalized["translation_hints"] = _ensure_list(raw.get("translation_hints"))
    normalized["metal_constraints"] = _ensure_object_list(raw.get("metal_constraints"))
    normalized["catalytic_constraints"] = _ensure_object_list(raw.get("catalytic_constraints"))
    normalized["go_terms"] = _normalize_annotation_list(raw.get("go_terms"))
    normalized["ec_numbers"] = _normalize_annotation_list(raw.get("ec_numbers"))
    normalized["domains"] = _normalize_annotation_list(raw.get("domains"))
    normalized["label"] = str(raw.get("label", raw.get("name", raw.get("id", ""))))
    normalized["description"] = str(raw.get("description", ""))
    return normalized


def _match_external_records(
    records: Sequence[Dict[str, object]],
    query_terms: Sequence[str],
    text: str,
    tokens: Sequence[str],
) -> List[Dict[str, object]]:
    token_set = set(tokens)
    matches = []
    for record in records:
        searchable = " ".join(
            [
                str(record.get("label", "")),
                str(record.get("description", "")),
                " ".join(str(alias) for alias in record.get("aliases", [])),
                " ".join(str(term.get("name", "")) for term in record.get("go_terms", [])),
                " ".join(str(term.get("name", "")) for term in record.get("ec_numbers", [])),
                " ".join(str(term.get("name", "")) for term in record.get("domains", [])),
            ]
        ).lower()
        score = 0.0
        for term in query_terms:
            if term and term.lower() in searchable:
                score += 1.0
        for token in token_set:
            if token and token in searchable:
                score += 0.25
        if record.get("label") and str(record["label"]).lower() in text:
            score += 1.5
        if score > 0:
            matched = dict(record)
            matched["_match_score"] = round(score, 3)
            matches.append(matched)
    return sorted(matches, key=lambda item: float(item.get("_match_score", 0.0)), reverse=True)[:10]


def _collect_nested_annotations(items: Sequence[Dict[str, object]], key: str) -> List[Dict[str, str]]:
    collected: List[Dict[str, str]] = []
    for item in items:
        for entry in item.get(key, []):
            if isinstance(entry, dict) and (entry.get("id") or entry.get("name")):
                collected.append(
                    {
                        "id": str(entry.get("id", "")),
                        "name": str(entry.get("name", entry.get("label", ""))),
                        "description": str(entry.get("description", "")),
                    }
                )
    return collected


def _collect_string_values(items: Sequence[Dict[str, object]], key: str) -> List[str]:
    values: List[str] = []
    for item in items:
        for value in item.get(key, []):
            if value:
                values.append(str(value))
    return values


def _collect_object_values(items: Sequence[Dict[str, object]], key: str) -> List[Dict[str, object]]:
    values: List[Dict[str, object]] = []
    for item in items:
        for value in item.get(key, []):
            if isinstance(value, dict):
                values.append(dict(value))
    return values


def _normalize_annotation_list(payload: object) -> List[Dict[str, str]]:
    if not isinstance(payload, list):
        return []
    result = []
    for item in payload:
        if isinstance(item, dict):
            result.append(
                {
                    "id": str(item.get("id", "")),
                    "name": str(item.get("name", item.get("label", ""))),
                    "description": str(item.get("description", "")),
                }
            )
        elif item:
            result.append({"id": str(item), "name": str(item), "description": ""})
    return result


def _ensure_list(value: object) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        if "|" in value:
            return [segment.strip() for segment in value.split("|") if segment.strip()]
        if "," in value:
            return [segment.strip() for segment in value.split(",") if segment.strip()]
        return [value] if value.strip() else []
    return []


def _ensure_object_list(value: object) -> List[Dict[str, object]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, dict)]
    if isinstance(value, str) and value.strip():
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, list):
            return [dict(item) for item in payload if isinstance(item, dict)]
    return []
