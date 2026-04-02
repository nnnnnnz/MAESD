from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

from .knowledge import (
    CROSS_LIBRARY_ALIGNMENTS,
    DISAMBIGUATION_RULES,
    DOMAIN_LIBRARY,
    EC_HIERARCHY,
    EC_LIBRARY,
    GO_HIERARCHY,
    GO_LIBRARY,
    MOTIF_LIBRARY,
    TERM_SYNONYMS,
)


@dataclass
class OntologyKnowledge:
    go_library: Dict[str, Dict[str, str]]
    ec_library: Dict[str, Dict[str, str]]
    domain_library: Dict[str, Dict[str, str]]
    motif_library: Dict[str, str]
    term_synonyms: Dict[str, list[str]]
    go_hierarchy: Dict[str, list[Dict[str, str]]]
    ec_hierarchy: Dict[str, list[Dict[str, str]]]
    cross_library_alignments: Dict[str, Dict[str, str]]
    disambiguation_rules: Dict[str, Dict[str, Dict[str, Any]]]
    source_path: str | None = None

    @property
    def is_external(self) -> bool:
        return bool(self.source_path)

    def summary(self) -> Dict[str, object]:
        return {
            "source_path": self.source_path,
            "uses_external_ontology": self.is_external,
            "term_count": len(self.term_synonyms),
            "go_terms": len(self.go_library),
            "ec_terms": len(self.ec_library),
            "domains": len(self.domain_library),
            "motifs": len(self.motif_library),
        }


def load_ontology(path: str | None = None) -> OntologyKnowledge:
    resolved_path = path or os.getenv("MAESD_ONTOLOGY_PATH", "").strip() or None
    payload = _default_payload()
    if resolved_path:
        external_payload = _load_payload(Path(resolved_path))
        payload = _merge_payload(payload, external_payload)
    return OntologyKnowledge(
        go_library=payload["go_library"],
        ec_library=payload["ec_library"],
        domain_library=payload["domain_library"],
        motif_library=payload["motif_library"],
        term_synonyms=payload["term_synonyms"],
        go_hierarchy=payload["go_hierarchy"],
        ec_hierarchy=payload["ec_hierarchy"],
        cross_library_alignments=payload["cross_library_alignments"],
        disambiguation_rules=payload["disambiguation_rules"],
        source_path=str(Path(resolved_path).resolve()) if resolved_path else None,
    )


def _default_payload() -> Dict[str, Any]:
    return {
        "go_library": deepcopy(GO_LIBRARY),
        "ec_library": deepcopy(EC_LIBRARY),
        "domain_library": deepcopy(DOMAIN_LIBRARY),
        "motif_library": deepcopy(MOTIF_LIBRARY),
        "term_synonyms": deepcopy(TERM_SYNONYMS),
        "go_hierarchy": deepcopy(GO_HIERARCHY),
        "ec_hierarchy": deepcopy(EC_HIERARCHY),
        "cross_library_alignments": deepcopy(CROSS_LIBRARY_ALIGNMENTS),
        "disambiguation_rules": deepcopy(DISAMBIGUATION_RULES),
    }


def _load_payload(path: Path) -> Dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in {".yaml", ".yml"}:
        payload = yaml.safe_load(text) or {}
    elif suffix == ".json":
        payload = json.loads(text)
    else:
        raise ValueError(f"Unsupported ontology file format: {path}")
    if not isinstance(payload, Mapping):
        raise ValueError("Ontology payload must be a mapping/object at the top level")
    return dict(payload)


def _merge_payload(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key in (
        "go_library",
        "ec_library",
        "domain_library",
        "motif_library",
        "term_synonyms",
        "go_hierarchy",
        "ec_hierarchy",
        "cross_library_alignments",
    ):
        section = override.get(key)
        if isinstance(section, Mapping):
            _merge_mapping_section(merged[key], section)
    rules = override.get("disambiguation_rules")
    if isinstance(rules, Mapping):
        _merge_disambiguation_rules(merged["disambiguation_rules"], rules)
    return merged


def _merge_mapping_section(target: Dict[str, Any], incoming: Mapping[str, Any]) -> None:
    for key, value in incoming.items():
        if isinstance(value, Mapping) and isinstance(target.get(key), Mapping):
            nested = dict(target[key])
            nested.update(dict(value))
            target[key] = nested
        elif isinstance(value, list) and isinstance(target.get(key), list):
            target[key] = list(dict.fromkeys(list(target[key]) + list(value)))
        else:
            target[key] = deepcopy(value)


def _merge_disambiguation_rules(
    target: Dict[str, Dict[str, Dict[str, Any]]],
    incoming: Mapping[str, Any],
) -> None:
    for pivot, pivot_rules in incoming.items():
        if not isinstance(pivot_rules, Mapping):
            continue
        existing_pivot = target.setdefault(str(pivot), {})
        for context_term, rule in pivot_rules.items():
            if not isinstance(rule, Mapping):
                continue
            context_key = str(context_term)
            existing_rule = dict(existing_pivot.get(context_key, {}))
            for rule_key, rule_value in rule.items():
                if rule_key == "boost" and isinstance(rule_value, Mapping):
                    boosts = dict(existing_rule.get("boost", {}))
                    for boost_key, boost_value in rule_value.items():
                        boosts[str(boost_key)] = float(boost_value)
                    existing_rule["boost"] = boosts
                elif isinstance(rule_value, list) and isinstance(existing_rule.get(rule_key), list):
                    existing_rule[rule_key] = list(dict.fromkeys(list(existing_rule[rule_key]) + list(rule_value)))
                else:
                    existing_rule[rule_key] = deepcopy(rule_value)
            existing_pivot[context_key] = existing_rule
