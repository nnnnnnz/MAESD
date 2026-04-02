from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import mean
from typing import List, Sequence

from .expert_tools import append_tool_notes, load_tool_signal, merge_focus_metrics
from .schema import DesignCandidate, DesignConstraints, ExpertFeedback, ExpertRoundSummary, ScreeningScores


@dataclass
class ExpertReviewResult:
    candidate: DesignCandidate
    consensus_score: float
    lead_expert: str
    rounds: List[ExpertRoundSummary]


class CandidateExpert:
    name = "generic"
    weight = 1.0

    def review(self, candidate: DesignCandidate, constraints: DesignConstraints, round_index: int) -> ExpertFeedback:
        raise NotImplementedError

    def _recommendation(self, score: float) -> str:
        if score >= 0.78:
            return "promote"
        if score >= 0.58:
            return "revise"
        return "reject"


class StructuralExpert(CandidateExpert):
    name = "structural_expert"
    weight = 1.15

    def review(self, candidate: DesignCandidate, constraints: DesignConstraints, round_index: int) -> ExpertFeedback:
        scores = candidate.scores
        tool_signal = load_tool_signal(self.name, candidate, constraints)
        structural = scores.structural_score if scores else 0.0
        geometry = (
            (scores.detailed_metrics.get("global_reference_agreement", 0.0) + scores.detailed_metrics.get("global_compactness", 0.0)) / 2.0
            if scores
            else 0.0
        )
        tool_score = (tool_signal.metrics.get("fold_confidence", 0.0) + tool_signal.metrics.get("topology_score", 0.0)) / 2.0 if tool_signal else 0.0
        score = max(0.0, min(1.0, structural * 0.7 + geometry * 0.3))
        if tool_signal and tool_signal.metrics:
            score = max(0.0, min(1.0, score * 0.7 + tool_score * 0.3))
        actions = []
        if scores and scores.detailed_metrics.get("global_reference_agreement", 0.0) < 0.55:
            actions.append("bias refinement toward reference-like topology")
        if scores and scores.detailed_metrics.get("global_secondary_structure_agreement", 0.0) < 0.6:
            actions.append("stabilize secondary-structure pattern before next iteration")
        if tool_signal and tool_signal.metrics.get("fold_confidence", 1.0) < 0.55:
            actions.append("improve fold confidence according to structure-QA tool")
        return ExpertFeedback(
            expert=self.name,
            round_index=round_index,
            score=round(score, 4),
            confidence=round(0.65 + min(0.3, structural * 0.25), 4),
            recommendation=self._recommendation(score),
            rationale=append_tool_notes("Evaluates fold plausibility, compactness, and structural agreement.", tool_signal),
            suggested_actions=actions,
            focus_metrics=merge_focus_metrics(
                {
                "structural_score": structural,
                "global_reference_agreement": scores.detailed_metrics.get("global_reference_agreement", 0.0) if scores else 0.0,
                },
                tool_signal,
            ),
        )


class FunctionExpert(CandidateExpert):
    name = "function_expert"
    weight = 1.2

    def review(self, candidate: DesignCandidate, constraints: DesignConstraints, round_index: int) -> ExpertFeedback:
        scores = candidate.scores
        tool_signal = load_tool_signal(self.name, candidate, constraints)
        functional = scores.functional_score if scores else 0.0
        motif_score = scores.detailed_metrics.get("core_site_match", 0.0) if scores else 0.0
        catalytic_score = scores.detailed_metrics.get("catalytic_site_geometry", 0.5) if scores else 0.5
        score = max(0.0, min(1.0, functional * 0.55 + motif_score * 0.2 + catalytic_score * 0.25))
        if tool_signal and tool_signal.metrics:
            function_tool = (
                tool_signal.metrics.get("site_probability", 0.0) + tool_signal.metrics.get("motif_retention", 0.0)
            ) / 2.0
            score = max(0.0, min(1.0, score * 0.7 + function_tool * 0.3))
        actions = []
        if scores and scores.detailed_metrics.get("core_site_match", 0.0) < 0.75:
            actions.append("recover motif integrity around active residues")
        if scores and scores.detailed_metrics.get("catalytic_site_geometry", 0.0) < 0.55:
            actions.append("improve catalytic residue spacing and orientation")
        if tool_signal and tool_signal.metrics.get("site_probability", 1.0) < 0.55:
            actions.append("strengthen predicted functional-site signal from expert tool")
        return ExpertFeedback(
            expert=self.name,
            round_index=round_index,
            score=round(score, 4),
            confidence=round(0.66 + min(0.28, functional * 0.24), 4),
            recommendation=self._recommendation(score),
            rationale=append_tool_notes("Evaluates active-site retention, motif fidelity, and catalytic geometry.", tool_signal),
            suggested_actions=actions,
            focus_metrics=merge_focus_metrics(
                {
                "functional_score": functional,
                "core_site_match": motif_score,
                "catalytic_site_geometry": catalytic_score,
                },
                tool_signal,
            ),
        )


class DevelopabilityExpert(CandidateExpert):
    name = "developability_expert"
    weight = 0.95

    def review(self, candidate: DesignCandidate, constraints: DesignConstraints, round_index: int) -> ExpertFeedback:
        scores = candidate.scores
        tool_signal = load_tool_signal(self.name, candidate, constraints)
        energy = scores.energy_score if scores else 0.0
        normalized_energy = scores.backend_metrics.get("normalized_energy", 0.5) if scores else 0.5
        clash_score = scores.backend_metrics.get("clash_score", 0.0) if scores else 0.0
        score = max(0.0, min(1.0, energy * 0.65 + normalized_energy * 0.35 - clash_score * 0.25))
        if tool_signal and tool_signal.metrics:
            dev_tool = (
                tool_signal.metrics.get("solubility_score", 0.0)
                + tool_signal.metrics.get("aggregation_risk", 0.0) * -1.0
                + 1.0
            ) / 2.0
            score = max(0.0, min(1.0, score * 0.7 + dev_tool * 0.3))
        actions = []
        if clash_score > 0.1:
            actions.append("reduce steric crowding around packed core")
        if normalized_energy < 0.55:
            actions.append("prioritize lower-energy sequence variants")
        if tool_signal and tool_signal.metrics.get("aggregation_risk", 0.0) > 0.4:
            actions.append("reduce aggregation-prone segments flagged by developability tool")
        return ExpertFeedback(
            expert=self.name,
            round_index=round_index,
            score=round(score, 4),
            confidence=round(0.64 + min(0.25, energy * 0.22), 4),
            recommendation=self._recommendation(score),
            rationale=append_tool_notes("Evaluates energy favorability, clashes, and developability risk.", tool_signal),
            suggested_actions=actions,
            focus_metrics=merge_focus_metrics(
                {
                "energy_score": energy,
                "normalized_energy": normalized_energy,
                "clash_score": clash_score,
                },
                tool_signal,
            ),
        )


class BindingExpert(CandidateExpert):
    name = "binding_expert"
    weight = 1.05

    def review(self, candidate: DesignCandidate, constraints: DesignConstraints, round_index: int) -> ExpertFeedback:
        scores = candidate.scores
        tool_signal = load_tool_signal(self.name, candidate, constraints)
        pocket = scores.detailed_metrics.get("pocket_score", 0.0) if scores else 0.0
        overlap = scores.detailed_metrics.get("motif_pocket_overlap", 0.0) if scores else 0.0
        metal = scores.detailed_metrics.get("metal_binding_geometry", 0.5) if scores else 0.5
        score = max(0.0, min(1.0, pocket * 0.35 + overlap * 0.35 + metal * 0.3))
        if tool_signal and tool_signal.metrics:
            bind_tool = (
                tool_signal.metrics.get("docking_score", 0.0)
                + tool_signal.metrics.get("pose_agreement", 0.0)
                + tool_signal.metrics.get("cofactor_fit", 0.0)
            ) / 3.0
            score = max(0.0, min(1.0, score * 0.65 + bind_tool * 0.35))
        actions = []
        if overlap < 0.5:
            actions.append("align pocket residues with annotated motif/active site")
        if metal < 0.55 and constraints.metadata.get("metal_constraints"):
            actions.append("improve metal coordination geometry near binding pocket")
        if tool_signal and tool_signal.metrics.get("docking_score", 1.0) < 0.55:
            actions.append("improve ligand/cofactor docking compatibility around the pocket")
        return ExpertFeedback(
            expert=self.name,
            round_index=round_index,
            score=round(score, 4),
            confidence=round(0.62 + min(0.3, score * 0.25), 4),
            recommendation=self._recommendation(score),
            rationale=append_tool_notes("Evaluates pocket support, motif-pocket overlap, and cofactor binding geometry.", tool_signal),
            suggested_actions=actions,
            focus_metrics=merge_focus_metrics(
                {
                "pocket_score": pocket,
                "motif_pocket_overlap": overlap,
                "metal_binding_geometry": metal,
                },
                tool_signal,
            ),
        )


class DecisionExpert:
    """Multi-expert selection, Pareto filtering, and optimization progress tracking."""

    def __init__(self, review_rounds: int = 2):
        self.review_rounds = max(1, review_rounds)
        self.experts: List[CandidateExpert] = [
            StructuralExpert(),
            FunctionExpert(),
            DevelopabilityExpert(),
            BindingExpert(),
        ]

    def review_candidates(self, candidates: Sequence[DesignCandidate], constraints: DesignConstraints) -> List[ExpertReviewResult]:
        results: List[ExpertReviewResult] = []
        for candidate in candidates:
            candidate.expert_feedback = []
            round_summaries: List[ExpertRoundSummary] = []
            for round_index in range(self.review_rounds):
                feedbacks = [expert.review(candidate, constraints, round_index) for expert in self.experts]
                candidate.expert_feedback.extend(feedbacks)
                round_summaries.append(self._summarize_round(feedbacks, round_index))
                self._inject_feedback(candidate, feedbacks, round_index)
            consensus_score = mean(summary.mean_score for summary in round_summaries) if round_summaries else 0.0
            lead_expert = max(candidate.expert_feedback, key=lambda item: item.score * item.confidence).expert if candidate.expert_feedback else "decision_expert"
            candidate.metadata["decision_consensus_score"] = round(consensus_score, 4)
            candidate.metadata["decision_lead_expert"] = lead_expert
            candidate.metadata["feedback_digest"] = self._digest_feedback(candidate.expert_feedback)
            results.append(
                ExpertReviewResult(
                    candidate=candidate,
                    consensus_score=round(consensus_score, 4),
                    lead_expert=lead_expert,
                    rounds=round_summaries,
                )
            )
        return results

    def pareto_front(self, candidates: Sequence[DesignCandidate]) -> List[DesignCandidate]:
        front: List[DesignCandidate] = []
        for candidate in candidates:
            if candidate.scores is None:
                continue
            dominated = False
            for other in candidates:
                if candidate is other or other.scores is None:
                    continue
                if self._dominates(other, candidate):
                    dominated = True
                    break
            if not dominated:
                front.append(candidate)
        front.sort(key=self._ranking_key, reverse=True)
        return front

    def improved(self, previous_metrics: Sequence[float] | None, current_metrics: Sequence[float]) -> bool:
        if previous_metrics is None:
            return True
        return any((curr - prev) > 0.01 for prev, curr in zip(previous_metrics, current_metrics))

    def _dominates(self, lhs_candidate: DesignCandidate, rhs_candidate: DesignCandidate) -> bool:
        lhs = lhs_candidate.scores
        rhs = rhs_candidate.scores
        if lhs is None or rhs is None:
            return False
        lhs_consensus = float(lhs_candidate.metadata.get("decision_consensus_score", 0.0))
        rhs_consensus = float(rhs_candidate.metadata.get("decision_consensus_score", 0.0))
        lhs_values = (lhs.structural_score, lhs.energy_score, lhs.functional_score, lhs_consensus)
        rhs_values = (rhs.structural_score, rhs.energy_score, rhs.functional_score, rhs_consensus)
        return all(a >= b for a, b in zip(lhs_values, rhs_values)) and any(a > b for a, b in zip(lhs_values, rhs_values))

    def _ranking_key(self, candidate: DesignCandidate) -> tuple[float, float, float, float]:
        scores = candidate.scores
        return (
            float(candidate.metadata.get("decision_consensus_score", 0.0)),
            scores.functional_score if scores else 0.0,
            scores.structural_score if scores else 0.0,
            scores.energy_score if scores else 0.0,
        )

    def _summarize_round(self, feedbacks: Sequence[ExpertFeedback], round_index: int) -> ExpertRoundSummary:
        recommendations = Counter(item.recommendation for item in feedbacks)
        key_actions = []
        for feedback in feedbacks:
            key_actions.extend(feedback.suggested_actions[:1])
        lead = max(feedbacks, key=lambda item: item.score * item.confidence).expert if feedbacks else "decision_expert"
        return ExpertRoundSummary(
            round_index=round_index,
            lead_expert=lead,
            mean_score=round(mean(item.score for item in feedbacks), 4) if feedbacks else 0.0,
            recommendations=dict(recommendations),
            key_actions=list(dict.fromkeys(action for action in key_actions if action))[:5],
        )

    def _inject_feedback(self, candidate: DesignCandidate, feedbacks: Sequence[ExpertFeedback], round_index: int) -> None:
        actions = list(candidate.metadata.get("feedback_actions", []))
        for feedback in feedbacks:
            actions.extend(feedback.suggested_actions)
        candidate.metadata["feedback_actions"] = list(dict.fromkeys(actions))[:12]
        candidate.metadata["last_feedback_round"] = round_index

    def _digest_feedback(self, feedbacks: Sequence[ExpertFeedback]) -> List[str]:
        lines = []
        for feedback in feedbacks[-len(self.experts) :]:
            lines.append(f"{feedback.expert}:{feedback.recommendation}:{feedback.score:.2f}")
        return lines
