from __future__ import annotations

from .knowledge import CHARGED, HYDROPHOBIC, POLAR
from .structure_analysis import aggregate_sghfs, analyze_structure_file, compute_sghfs_details
from .schema import DesignCandidate, DesignConstraints, ScreeningScores


class ProteinScreeningExpert:
    """Approximate SGHFS-style functional screening with pluggable structure scores."""

    def score(self, candidate: DesignCandidate, constraints: DesignConstraints) -> ScreeningScores:
        sequence = candidate.sequence
        structure_confidence = candidate.structure.confidence if candidate.structure else 0.0
        structure_artifacts = candidate.structure.artifacts if candidate.structure else {}
        constraint_metadata = constraints.metadata or {}
        candidate_structure = analyze_structure_file(structure_artifacts.get("pdb_path"), sequence, constraint_metadata)
        reference_structure = analyze_structure_file(constraints.reference_structure_path, "", constraint_metadata)
        detailed_metrics = compute_sghfs_details(
            sequence=sequence,
            motifs=constraints.motifs,
            structure=candidate_structure,
            reference=reference_structure,
            optimization_goals=constraints.optimization_goals,
            constraint_metadata=constraint_metadata,
        )
        aggregated = aggregate_sghfs(detailed_metrics)
        structural_score = self._structural_score(sequence, constraints, structure_confidence, structure_artifacts, detailed_metrics)
        energy_score = self._energy_score(sequence, structure_artifacts, detailed_metrics)
        fsm = aggregated["fsm"]
        smr = aggregated["smr"]
        gci = aggregated["gci"]
        backend_metrics = {}
        if candidate.structure:
            backend_metrics = {
                "ptm": candidate.structure.ptm,
                "iptm": candidate.structure.iptm,
                "rmsd_hint": candidate.structure.rmsd_hint,
            }
            if "mean_bfactor_confidence" in structure_artifacts:
                backend_metrics["mean_bfactor_confidence"] = float(structure_artifacts["mean_bfactor_confidence"])
            if candidate_structure is not None:
                backend_metrics["hbond_density"] = candidate_structure.hbond_density
                backend_metrics["salt_bridge_density"] = candidate_structure.salt_bridge_density
                backend_metrics["pocket_score"] = candidate_structure.pocket_score
                backend_metrics["residue_contact_ratio"] = candidate_structure.residue_contact_ratio
                backend_metrics["secondary_structure_source"] = candidate_structure.secondary_structure_source
                backend_metrics["raw_energy"] = candidate_structure.raw_energy
                backend_metrics["normalized_energy"] = candidate_structure.normalized_energy
                backend_metrics["clash_score"] = candidate_structure.clash_score
                backend_metrics["energy_source"] = candidate_structure.energy_source
        return ScreeningScores(
            structural_score=structural_score,
            energy_score=energy_score,
            functional_score=(fsm + smr + gci) / 3.0,
            fsm=fsm,
            smr=smr,
            gci=gci,
            structure_confidence=structure_confidence,
            backend_metrics=backend_metrics,
            detailed_metrics=detailed_metrics,
        )

    def passes(self, scores: ScreeningScores) -> bool:
        return (
            scores.fsm >= 0.7
            and scores.smr >= 0.6
            and scores.gci >= 0.6
            and scores.structural_score >= 0.45
            and scores.energy_score >= 0.45
        )

    def _structural_score(
        self,
        sequence: str,
        constraints: DesignConstraints,
        structure_confidence: float,
        structure_artifacts: dict,
        detailed_metrics: dict,
    ) -> float:
        length_penalty = min(abs(len(sequence) - constraints.target_length) / max(constraints.target_length, 1), 1.0)
        helix_bonus = 0.15 if any("transmembrane" in domain.name for domain in constraints.domains) and "LV" in sequence else 0.0
        gly_pro_ratio = sum(aa in "GP" for aa in sequence) / len(sequence)
        structure_bonus = structure_confidence * 0.25
        global_bonus = (
            detailed_metrics.get("global_compactness", 0.0) * 0.08
            + detailed_metrics.get("global_contact_order", 0.0) * 0.08
            + detailed_metrics.get("global_reference_agreement", 0.0) * 0.08
            + detailed_metrics.get("catalytic_site_geometry", 0.0) * 0.08
            + detailed_metrics.get("metal_binding_geometry", 0.0) * 0.06
        )
        compactness_hint = float(structure_artifacts.get("compactness_hint", 4.0))
        compactness_penalty = min(0.12, abs(compactness_hint - 4.0) / 25.0)
        return max(
            0.0,
            min(1.0, 0.62 - 0.35 * length_penalty - 0.25 * gly_pro_ratio + helix_bonus + structure_bonus + global_bonus - compactness_penalty),
        )

    def _energy_score(self, sequence: str, structure_artifacts: dict, detailed_metrics: dict) -> float:
        hydrophobic_ratio = sum(aa in HYDROPHOBIC for aa in sequence) / len(sequence)
        charged_ratio = sum(aa in CHARGED for aa in sequence) / len(sequence)
        polarity_ratio = sum(aa in POLAR for aa in sequence) / len(sequence)
        gly_pro_ratio = sum(aa in "GP" for aa in sequence) / len(sequence)
        compactness_hint = float(structure_artifacts.get("compactness_hint", 4.0))
        compactness_penalty = min(0.25, abs(compactness_hint - 4.0) / 20.0)
        imbalance = abs(hydrophobic_ratio - 0.38) + abs(charged_ratio - 0.20) + abs(polarity_ratio - 0.28)
        site_bonus = (
            detailed_metrics.get("core_site_accessibility", 0.0) * 0.05
            + detailed_metrics.get("microenvironment_hydrophobic_balance", 0.0) * 0.05
            + detailed_metrics.get("microenvironment_charge_balance", 0.0) * 0.05
            + detailed_metrics.get("microenvironment_hbond_potential", 0.0) * 0.04
            + detailed_metrics.get("microenvironment_salt_bridge_support", 0.0) * 0.03
            + detailed_metrics.get("motif_pocket_overlap", 0.0) * 0.03
            + detailed_metrics.get("global_energy_favorability", 0.0) * 0.1
            + detailed_metrics.get("metal_binding_geometry", 0.0) * 0.03
            + detailed_metrics.get("catalytic_site_geometry", 0.0) * 0.04
        )
        return max(0.0, min(1.0, 1.0 - imbalance - gly_pro_ratio * 0.15 - compactness_penalty + site_bonus))
