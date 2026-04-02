from __future__ import annotations

import os
import re
from typing import Dict, Iterable, List, Sequence

from .knowledge import DOMAIN_LIBRARY, EC_LIBRARY, GO_LIBRARY, MOTIF_LIBRARY
from .retrieval import (
    enrich_domain_term,
    enrich_ec_term,
    enrich_go_term,
    merge_evidence_items,
    query_external_knowledge,
    search_pfam,
    search_uniprot,
)
from .semantic_reasoner import SemanticReasoner
from .schema import BiologicalAnnotation, DesignConstraints, DomainConstraint


class IntentRecognitionAgent:
    """Translate natural language into executable biological constraints."""

    def __init__(self, connector_config_path: str | None = None, ontology_path: str | None = None):
        self.connector_config_path = connector_config_path
        self.ontology_path = ontology_path
        self.reasoner = SemanticReasoner(ontology_path=ontology_path)

    def parse(self, prompt: str) -> DesignConstraints:
        lowered = prompt.lower()
        tokens = [token for token in re.split(r"[^a-z0-9\-\+]+", lowered) if token]
        metadata = self._empty_metadata(tokens)
        if self._retrieval_enabled():
            metadata.update(self._collect_retrieval_metadata(tokens, lowered))
        external_metadata = self._collect_external_metadata(tokens, lowered)
        metadata["go_evidence"] = merge_evidence_items(metadata.get("go_evidence", []), external_metadata.get("go_evidence", []))
        metadata["ec_evidence"] = merge_evidence_items(metadata.get("ec_evidence", []), external_metadata.get("ec_evidence", []))
        metadata["domain_evidence"] = merge_evidence_items(metadata.get("domain_evidence", []), external_metadata.get("domain_evidence", []))
        metadata["retrieval_errors"] = list(metadata.get("retrieval_errors", [])) + list(external_metadata.get("external_connector_errors", []))
        for key, value in external_metadata.items():
            if key not in {"go_evidence", "ec_evidence", "domain_evidence"}:
                metadata[key] = value
        semantic_resolution = self.reasoner.resolve(lowered, tokens, metadata)
        metadata.update(
            {
                "semantic_trace": semantic_resolution.get("semantic_trace", []),
                "cross_library_links": semantic_resolution.get("cross_library_links", []),
                "go_ancestor_terms": semantic_resolution.get("go_ancestors", []),
                "ec_ancestor_terms": semantic_resolution.get("ec_ancestors", []),
                "external_translation_hints": list(dict.fromkeys(list(metadata.get("external_translation_hints", [])) + list(semantic_resolution.get("translation_hints", [])))),
                "external_intent_hints": list(dict.fromkeys(list(metadata.get("external_intent_hints", [])) + list(semantic_resolution.get("intent_hints", [])))),
                "external_motif_hints": list(dict.fromkeys(list(metadata.get("external_motif_hints", [])) + list(semantic_resolution.get("motifs", [])))),
                "external_goal_hints": list(dict.fromkeys(list(metadata.get("external_goal_hints", [])) + list(semantic_resolution.get("goals", [])))),
            }
        )
        metadata["go_evidence"] = merge_evidence_items(metadata.get("go_evidence", []), semantic_resolution.get("go_terms", []))
        metadata["ec_evidence"] = merge_evidence_items(metadata.get("ec_evidence", []), semantic_resolution.get("ec_numbers", []))
        metadata["domain_evidence"] = merge_evidence_items(metadata.get("domain_evidence", []), semantic_resolution.get("domains", []))

        go_terms = self._collect_go_terms(tokens, lowered, metadata)
        ec_numbers = self._collect_ec_numbers(tokens, lowered, metadata)
        domains = self._collect_domains(tokens, lowered, metadata)
        motifs = self._collect_motifs(lowered, metadata)
        goals = self._collect_goals(lowered, metadata)
        target_length = self._infer_length(lowered)
        intents = self._segment_intents(prompt, metadata)
        reference_structure_path = self._extract_reference_structure(prompt)

        return DesignConstraints(
            original_prompt=prompt,
            intents=intents,
            go_terms=go_terms,
            ec_numbers=ec_numbers,
            domains=domains,
            motifs=motifs,
            target_length=target_length,
            optimization_goals=goals,
            reference_structure_path=reference_structure_path,
            metadata={
                "semantic_terms": tokens[:50],
                "translation_strategy": self._translation_strategy(metadata),
                "ontology_summary": self.reasoner.ontology_summary,
                "metal_constraints": self._merge_object_lists(self._collect_metal_constraints(lowered), metadata.get("external_metal_constraints", [])),
                "catalytic_constraints": self._merge_object_lists(
                    self._collect_catalytic_constraints(lowered),
                    metadata.get("external_catalytic_constraints", []),
                ),
                **metadata,
            },
        )

    def _collect_go_terms(self, tokens: Sequence[str], text: str, metadata: Dict[str, object]) -> List[BiologicalAnnotation]:
        annotations: List[BiologicalAnnotation] = []
        for key, value in GO_LIBRARY.items():
            if key in text or key in tokens:
                annotations.append(
                    BiologicalAnnotation(
                        label=key,
                        identifier=value["go"],
                        description=value["description"],
                    )
                )
        for item in metadata.get("go_evidence", []):
            if item.get("id"):
                annotations.append(
                    BiologicalAnnotation(
                        label=item.get("name", item["id"]),
                        identifier=item["id"],
                        description=item.get("description", item.get("name", "")),
                    )
                )
        for item in metadata.get("go_ancestor_terms", []):
            if item.get("id"):
                annotations.append(
                    BiologicalAnnotation(
                        label=item.get("name", item["id"]),
                        identifier=item["id"],
                        description=item.get("description", "inferred ancestor concept"),
                    )
                )
        return self._unique_by_identifier(annotations)

    def _collect_ec_numbers(self, tokens: Sequence[str], text: str, metadata: Dict[str, object]) -> List[BiologicalAnnotation]:
        annotations: List[BiologicalAnnotation] = []
        ec_pattern = re.findall(r"\bEC\s*\d+\.\d+\.\d+\.\d+\b", text, flags=re.IGNORECASE)
        for raw_ec in ec_pattern:
            clean = re.sub(r"\s+", " ", raw_ec.upper())
            annotations.append(BiologicalAnnotation(label=clean, identifier=clean, description="explicit EC number"))
        for key, value in EC_LIBRARY.items():
            if key in text or key in tokens:
                annotations.append(
                    BiologicalAnnotation(
                        label=key,
                        identifier=value["ec"],
                        description=value["description"],
                    )
                )
        for item in metadata.get("ec_evidence", []):
            ec_id = item.get("id", "")
            if ec_id:
                annotations.append(
                    BiologicalAnnotation(
                        label=item.get("name", ec_id),
                        identifier=ec_id,
                        description=item.get("description", item.get("name", "")),
                    )
                )
        for item in metadata.get("ec_ancestor_terms", []):
            if item.get("id"):
                annotations.append(
                    BiologicalAnnotation(
                        label=item.get("name", item["id"]),
                        identifier=item["id"],
                        description=item.get("description", "inferred ancestor class"),
                    )
                )
        return self._unique_by_identifier(annotations)

    def _collect_domains(self, tokens: Sequence[str], text: str, metadata: Dict[str, object]) -> List[DomainConstraint]:
        results: List[DomainConstraint] = []
        for key, value in DOMAIN_LIBRARY.items():
            if key in text or key in tokens:
                results.append(
                    DomainConstraint(
                        name=value["name"],
                        accession=value["accession"],
                        evidence=f"keyword:{key}",
                    )
                )
        for item in metadata.get("domain_evidence", []):
            accession = item.get("id", "")
            if accession:
                results.append(
                    DomainConstraint(
                        name=item.get("name", accession),
                        accession=accession,
                        evidence="interpro-evidence",
                    )
                )
        return self._unique_domains(results)

    def _collect_motifs(self, text: str, metadata: Dict[str, object]) -> List[str]:
        motifs = [motif for key, motif in MOTIF_LIBRARY.items() if key in text]
        if "disulfide" in text:
            motifs.append("CXXC")
        motifs.extend(str(motif) for motif in metadata.get("external_motif_hints", []))
        return list(dict.fromkeys(motifs))

    def _collect_goals(self, text: str, metadata: Dict[str, object]) -> List[str]:
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
        if not goals:
            goals.append("general_function_preservation")
        return list(dict.fromkeys(goals))

    def _collect_metal_constraints(self, text: str) -> List[Dict[str, object]]:
        constraints: List[Dict[str, object]] = []
        metal_map = {
            "zinc": ("ZN", ["H", "C", "D", "E"], "tetrahedral"),
            "magnesium": ("MG", ["D", "E", "N", "Q"], "octahedral"),
            "calcium": ("CA", ["D", "E", "N", "Q"], "octahedral"),
            "iron": ("FE", ["H", "D", "E", "Y", "C"], "octahedral"),
            "copper": ("CU", ["H", "C", "M"], "trigonal"),
            "manganese": ("MN", ["D", "E", "H"], "octahedral"),
        }
        for keyword, (ion, residues, geometry) in metal_map.items():
            if keyword in text:
                constraints.append(
                    {
                        "ion": ion,
                        "coordinating_residues": residues,
                        "preferred_geometry": geometry,
                    }
                )
        if "metal binding" in text and not constraints:
            constraints.append({"ion": "ZN", "coordinating_residues": ["H", "D", "E", "C"], "preferred_geometry": "tetrahedral"})
        return constraints

    def _collect_catalytic_constraints(self, text: str) -> List[Dict[str, object]]:
        constraints: List[Dict[str, object]] = []
        if "catalytic triad" in text:
            constraints.append({"type": "triad", "residues": ["S", "H", "D"]})
        if "catalytic dyad" in text:
            constraints.append({"type": "dyad", "residues": ["C", "H"]})
        if "esterase" in text or "hydrolase" in text or "serine hydrolase" in text:
            constraints.append({"type": "serine-hydrolase", "residues": ["S", "H", "D"]})
        if "cysteine protease" in text:
            constraints.append({"type": "cysteine-protease", "residues": ["C", "H", "N"]})
        deduped: Dict[str, Dict[str, object]] = {}
        for item in constraints:
            key = f"{item.get('type')}:{','.join(item.get('residues', []))}"
            deduped[key] = item
        return list(deduped.values())

    def _infer_length(self, text: str) -> int:
        match = re.search(r"(?:length|residues?|aa)\D{0,8}(\d{2,4})", text)
        if match:
            value = int(match.group(1))
            return max(60, min(value, 1200))
        if "membrane" in text:
            return 320
        if "domain" in text or "enzyme" in text:
            return 240
        return 180

    def _segment_intents(self, prompt: str, metadata: Dict[str, object]) -> List[str]:
        parts = [segment.strip() for segment in re.split(r"[.;,\n]+", prompt) if segment.strip()]
        parts.extend(str(intent) for intent in metadata.get("external_intent_hints", []))
        deduped = [part for part in dict.fromkeys(parts) if part]
        return deduped[:5] or [prompt.strip()]

    def _extract_reference_structure(self, prompt: str) -> str | None:
        match = re.search(r"([A-Za-z]:\\[^\\/:*?\"<>|\r\n]+(?:\\[^\\/:*?\"<>|\r\n]+)+\.(?:pdb|cif))", prompt)
        return match.group(1) if match else None

    def _retrieval_enabled(self) -> bool:
        flag = os.getenv("MAESD_DISABLE_RETRIEVAL", "").strip().lower()
        return flag not in {"1", "true", "yes", "on"}

    def _empty_metadata(self, tokens: Sequence[str]) -> Dict[str, object]:
        return {
            "go_evidence": [],
            "ec_evidence": [],
            "domain_evidence": [],
            "uniprot_hits": [],
            "pfam_hits": [],
            "retrieval_errors": [],
            "external_motif_hints": [],
            "external_goal_hints": [],
            "external_intent_hints": [],
            "external_translation_hints": [],
            "external_metal_constraints": [],
            "external_catalytic_constraints": [],
            "external_knowledge_hits": [],
            "external_connector_errors": [],
            "external_connectors": [],
            "semantic_terms": list(tokens[:50]),
        }

    def _collect_retrieval_metadata(self, tokens: Sequence[str], text: str) -> Dict[str, object]:
        query_terms = []
        for candidate in ("hydrolase", "protease", "esterase", "kinase", "membrane", "zinc", "binding", "transmembrane"):
            if candidate in text:
                query_terms.append(candidate)
        query_terms.extend(tokens[:3])
        query_terms = list(dict.fromkeys(query_terms))[:3]

        go_items = []
        ec_items = []
        domain_items = []
        uniprot_items = []
        pfam_items = []
        retrieval_errors: List[str] = []

        for term in query_terms:
            go_ev = enrich_go_term(term)
            ec_ev = enrich_ec_term(term)
            domain_ev = enrich_domain_term(term)
            uniprot_ev = search_uniprot(term)
            pfam_ev = search_pfam(term)
            go_items.extend(go_ev.items)
            ec_items.extend(ec_ev.items)
            domain_items.extend(domain_ev.items)
            uniprot_items.extend(uniprot_ev.items)
            pfam_items.extend(pfam_ev.items)
            retrieval_errors.extend(go_ev.errors + ec_ev.errors + domain_ev.errors + uniprot_ev.errors + pfam_ev.errors)

        return {
            "go_evidence": merge_evidence_items(go_items),
            "ec_evidence": merge_evidence_items(ec_items),
            "domain_evidence": merge_evidence_items(domain_items),
            "uniprot_hits": merge_evidence_items(uniprot_items),
            "pfam_hits": merge_evidence_items(pfam_items),
            "retrieval_errors": retrieval_errors[:20],
        }

    def _collect_external_metadata(self, tokens: Sequence[str], text: str) -> Dict[str, object]:
        query_terms = []
        for candidate in ("hydrolase", "protease", "esterase", "kinase", "membrane", "zinc", "binding", "transmembrane"):
            if candidate in text:
                query_terms.append(candidate)
        query_terms.extend(tokens[:5])
        external = query_external_knowledge(list(dict.fromkeys(query_terms))[:5], text, tokens, self.connector_config_path)
        return {
            "go_evidence": external.get("go_evidence", []),
            "ec_evidence": external.get("ec_evidence", []),
            "domain_evidence": external.get("domain_evidence", []),
            "external_motif_hints": external.get("external_motif_hints", []),
            "external_goal_hints": external.get("external_goal_hints", []),
            "external_intent_hints": external.get("external_intent_hints", []),
            "external_translation_hints": external.get("external_translation_hints", []),
            "external_metal_constraints": external.get("external_metal_constraints", []),
            "external_catalytic_constraints": external.get("external_catalytic_constraints", []),
            "external_knowledge_hits": external.get("external_knowledge_hits", []),
            "external_connector_errors": external.get("external_connector_errors", []),
            "external_connectors": external.get("external_connectors", []),
        }

    def _translation_strategy(self, metadata: Dict[str, object]) -> str:
        strategy = ["heuristic-keyword-expansion", "semantic-reasoning"]
        ontology_summary = self.reasoner.ontology_summary
        if ontology_summary.get("uses_external_ontology"):
            strategy.append("ontology-config")
        if metadata.get("external_connectors"):
            strategy.append("external-knowledge-connectors")
        if metadata.get("cross_library_links"):
            strategy.append("cross-library-alignment")
        return "+".join(strategy)

    def _merge_object_lists(self, primary: List[Dict[str, object]], secondary: Sequence[object]) -> List[Dict[str, object]]:
        merged: Dict[str, Dict[str, object]] = {}
        for item in list(primary) + [entry for entry in secondary if isinstance(entry, dict)]:
            key = json_key = f"{item.get('type', item.get('ion', 'obj'))}:{','.join(str(v) for v in item.values())}"
            merged[json_key] = dict(item)
        return list(merged.values())

    def _unique_by_identifier(self, annotations: Iterable[BiologicalAnnotation]) -> List[BiologicalAnnotation]:
        deduped: Dict[str, BiologicalAnnotation] = {}
        for annotation in annotations:
            deduped[annotation.identifier] = annotation
        return list(deduped.values())

    def _unique_domains(self, domains: Iterable[DomainConstraint]) -> List[DomainConstraint]:
        deduped: Dict[str, DomainConstraint] = {}
        for domain in domains:
            deduped[domain.accession] = domain
        return list(deduped.values())
