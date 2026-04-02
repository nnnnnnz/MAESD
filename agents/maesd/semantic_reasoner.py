from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from .ontology import OntologyKnowledge, load_ontology


@dataclass
class ResolvedEntity:
    kind: str
    label: str
    identifier: str
    description: str
    score: float
    canonical_term: str = ""
    sources: List[str] = field(default_factory=list)
    ancestors: List[Dict[str, str]] = field(default_factory=list)


class SemanticReasoner:
    """Resolve, align, disambiguate, and infer biological concepts across libraries."""

    def __init__(self, ontology_path: str | None = None):
        self.ontology = load_ontology(ontology_path)

    def resolve(self, text: str, tokens: Sequence[str], metadata: Dict[str, object]) -> Dict[str, object]:
        lowered = text.lower()
        resolved_go = self._resolve_entities("go", lowered, tokens, metadata)
        resolved_ec = self._resolve_entities("ec", lowered, tokens, metadata)
        resolved_domain = self._resolve_entities("domain", lowered, tokens, metadata)
        disambiguation = self._apply_disambiguation(lowered, tokens, resolved_go, resolved_ec, resolved_domain)
        motifs = self._resolve_motifs(lowered, metadata, disambiguation)
        goals = self._resolve_goals(lowered, metadata, disambiguation)
        translation_hints = list(dict.fromkeys(list(metadata.get("external_translation_hints", [])) + disambiguation["translation_hints"]))
        intent_hints = list(dict.fromkeys(list(metadata.get("external_intent_hints", [])) + disambiguation["intent_hints"]))
        return {
            "go_terms": [self._to_payload(item) for item in resolved_go],
            "ec_numbers": [self._to_payload(item) for item in resolved_ec],
            "domains": [self._to_payload(item) for item in resolved_domain],
            "motifs": motifs,
            "goals": goals,
            "translation_hints": translation_hints,
            "intent_hints": intent_hints,
            "cross_library_links": self._cross_library_links(resolved_go, resolved_ec, resolved_domain),
            "semantic_trace": self._semantic_trace(resolved_go, resolved_ec, resolved_domain),
            "go_ancestors": self._ancestor_payload(resolved_go),
            "ec_ancestors": self._ancestor_payload(resolved_ec),
        }

    def _resolve_entities(self, kind: str, text: str, tokens: Sequence[str], metadata: Dict[str, object]) -> List[ResolvedEntity]:
        local = self._local_candidates(kind, text, tokens)
        external = self._evidence_candidates(kind, metadata)
        merged: Dict[str, ResolvedEntity] = {}
        for item in local + external:
            key = item.identifier or item.label
            if key in merged:
                merged[key].score += item.score
                merged[key].sources = list(dict.fromkeys(merged[key].sources + item.sources))
            else:
                merged[key] = item
        resolved = list(merged.values())
        for item in resolved:
            item.ancestors = self._infer_ancestors(kind, item.identifier)
        resolved.sort(key=lambda entry: entry.score, reverse=True)
        return resolved[:6]

    def _local_candidates(self, kind: str, text: str, tokens: Sequence[str]) -> List[ResolvedEntity]:
        library = {
            "go": self.ontology.go_library,
            "ec": self.ontology.ec_library,
            "domain": self.ontology.domain_library,
        }[kind]
        results: List[ResolvedEntity] = []
        for canonical, payload in library.items():
            matches = self._match_strength(canonical, text, tokens)
            if matches <= 0:
                continue
            identifier = payload.get("go") if kind == "go" else payload.get("ec") if kind == "ec" else payload.get("accession")
            label = payload.get("name", canonical) if kind == "domain" else canonical
            description = payload.get("description", payload.get("name", canonical))
            results.append(
                ResolvedEntity(
                    kind=kind,
                    label=label,
                    identifier=str(identifier),
                    description=str(description),
                    score=matches,
                    canonical_term=canonical,
                    sources=["library"],
                )
            )
        return results

    def _evidence_candidates(self, kind: str, metadata: Dict[str, object]) -> List[ResolvedEntity]:
        evidence_key = {"go": "go_evidence", "ec": "ec_evidence", "domain": "domain_evidence"}[kind]
        items = metadata.get(evidence_key, [])
        results: List[ResolvedEntity] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            identifier = str(item.get("id", ""))
            label = str(item.get("name", identifier))
            description = str(item.get("description", ""))
            score = self._evidence_weight(metadata, item, kind)
            canonical = self._canonical_from_label(label, description)
            results.append(
                ResolvedEntity(
                    kind=kind,
                    label=label,
                    identifier=identifier,
                    description=description,
                    score=score,
                    canonical_term=canonical,
                    sources=[f"evidence:{evidence_key}"],
                )
            )
        return results

    def _evidence_weight(self, metadata: Dict[str, object], item: Dict[str, object], kind: str) -> float:
        base = {"go": 1.1, "ec": 1.15, "domain": 1.0}[kind]
        name = f"{item.get('name', '')} {item.get('description', '')}".lower()
        score = base
        for canonical, synonyms in self.ontology.term_synonyms.items():
            if any(token in name for token in synonyms):
                score += 0.2
        if any(str(item.get("id", "")).startswith(prefix) for prefix in ("GO:", "EC", "IPR")):
            score += 0.15
        if metadata.get("external_knowledge_hits"):
            external_labels = " ".join(str(hit.get("label", "")) for hit in metadata["external_knowledge_hits"]).lower()
            if item.get("name", "").lower() in external_labels:
                score += 0.2
        return round(score, 4)

    def _match_strength(self, canonical: str, text: str, tokens: Sequence[str]) -> float:
        strength = 0.0
        if canonical in text:
            strength += 1.0
        synonyms = self.ontology.term_synonyms.get(canonical, [canonical])
        for synonym in synonyms:
            if synonym in text:
                strength += 0.6
            elif synonym in tokens:
                strength += 0.4
        return round(strength, 4)

    def _canonical_from_label(self, label: str, description: str) -> str:
        searchable = f"{label} {description}".lower()
        for canonical, synonyms in self.ontology.term_synonyms.items():
            if canonical in searchable or any(syn in searchable for syn in synonyms):
                return canonical
        return label.lower()

    def _infer_ancestors(self, kind: str, identifier: str) -> List[Dict[str, str]]:
        hierarchy = self.ontology.go_hierarchy if kind == "go" else self.ontology.ec_hierarchy if kind == "ec" else {}
        ancestors = hierarchy.get(identifier, [])
        return [dict(item) for item in ancestors]

    def _apply_disambiguation(
        self,
        text: str,
        tokens: Sequence[str],
        go_terms: List[ResolvedEntity],
        ec_terms: List[ResolvedEntity],
        domains: List[ResolvedEntity],
    ) -> Dict[str, List[str]]:
        translation_hints: List[str] = []
        intent_hints: List[str] = []
        goals: List[str] = []
        motifs: List[str] = []
        boosts = {}
        searchable = " ".join(tokens) + " " + text
        for pivot, rules in self.ontology.disambiguation_rules.items():
            if pivot not in searchable:
                continue
            for context_term, rule in rules.items():
                if context_term not in searchable:
                    continue
                translation_hints.append(str(rule.get("translation_hint", "")))
                if rule.get("goal"):
                    goals.append(str(rule["goal"]))
                if rule.get("motif"):
                    motifs.append(str(rule["motif"]))
                for key, value in rule.get("boost", {}).items():
                    boosts[key] = boosts.get(key, 0.0) + float(value)
                intent_hints.append(f"{pivot}->{context_term}")
        for collection, prefix in ((go_terms, "go"), (ec_terms, "ec"), (domains, "domain")):
            for item in collection:
                key = f"{prefix}:{item.identifier}"
                if key in boosts:
                    item.score += boosts[key]
        for collection in (go_terms, ec_terms, domains):
            collection.sort(key=lambda entry: entry.score, reverse=True)
        return {
            "translation_hints": [hint for hint in translation_hints if hint],
            "intent_hints": [hint for hint in intent_hints if hint],
            "goals": list(dict.fromkeys(goals)),
            "motifs": list(dict.fromkeys(motifs)),
        }

    def _resolve_motifs(self, text: str, metadata: Dict[str, object], disambiguation: Dict[str, List[str]]) -> List[str]:
        motifs = [motif for key, motif in self.ontology.motif_library.items() if key in text]
        motifs.extend(str(motif) for motif in metadata.get("external_motif_hints", []))
        motifs.extend(disambiguation["motifs"])
        if "disulfide" in text:
            motifs.append("CXXC")
        return list(dict.fromkeys(motifs))

    def _resolve_goals(self, text: str, metadata: Dict[str, object], disambiguation: Dict[str, List[str]]) -> List[str]:
        goal_map = {
            "thermostability": ["thermostable", "temperature", "heat", "thermostability"],
            "salt_tolerance": ["salt", "haloph", "osmotic"],
            "binding_affinity": ["bind", "binding", "affinity", "receptor"],
            "membrane_localization": ["membrane", "transmembrane"],
            "catalytic_activity": ["catal", "hydrol", "oxidoreduct", "transferase", "enzyme"],
        }
        goals = []
        for goal, keywords in goal_map.items():
            if any(keyword in text for keyword in keywords):
                goals.append(goal)
        goals.extend(str(goal) for goal in metadata.get("external_goal_hints", []))
        goals.extend(disambiguation["goals"])
        return list(dict.fromkeys(goals or ["general_function_preservation"]))

    def _cross_library_links(
        self,
        go_terms: Sequence[ResolvedEntity],
        ec_terms: Sequence[ResolvedEntity],
        domains: Sequence[ResolvedEntity],
    ) -> List[Dict[str, str]]:
        links = []
        go_ids = {item.identifier for item in go_terms}
        ec_ids = {item.identifier for item in ec_terms}
        domain_ids = {item.identifier for item in domains}
        for canonical, mapping in self.ontology.cross_library_alignments.items():
            if (
                ("go" not in mapping or mapping["go"] in go_ids)
                and ("ec" not in mapping or mapping["ec"] in ec_ids)
                and ("domain" not in mapping or mapping["domain"] in domain_ids)
            ):
                links.append({"canonical_term": canonical, **{k: v for k, v in mapping.items()}})
        return links

    def _semantic_trace(
        self,
        go_terms: Sequence[ResolvedEntity],
        ec_terms: Sequence[ResolvedEntity],
        domains: Sequence[ResolvedEntity],
    ) -> List[Dict[str, object]]:
        trace = []
        for item in list(go_terms) + list(ec_terms) + list(domains):
            trace.append(
                {
                    "kind": item.kind,
                    "id": item.identifier,
                    "label": item.label,
                    "score": round(item.score, 4),
                    "canonical_term": item.canonical_term,
                    "sources": item.sources,
                    "ancestors": item.ancestors,
                }
            )
        return trace

    def _ancestor_payload(self, entities: Sequence[ResolvedEntity]) -> List[Dict[str, str]]:
        seen = {}
        for entity in entities:
            for ancestor in entity.ancestors:
                seen[ancestor["id"]] = ancestor
        return list(seen.values())

    def _to_payload(self, entity: ResolvedEntity) -> Dict[str, object]:
        return {
            "id": entity.identifier,
            "name": entity.label,
            "description": entity.description,
            "score": round(entity.score, 4),
            "canonical_term": entity.canonical_term,
            "sources": entity.sources,
            "ancestors": entity.ancestors,
        }

    @property
    def ontology_summary(self) -> Dict[str, object]:
        return self.ontology.summary()
