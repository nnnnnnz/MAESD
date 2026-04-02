from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class BiologicalAnnotation:
    label: str
    identifier: str
    description: str


@dataclass
class DomainConstraint:
    name: str
    accession: str
    evidence: str


@dataclass
class DesignConstraints:
    original_prompt: str
    intents: List[str]
    go_terms: List[BiologicalAnnotation]
    ec_numbers: List[BiologicalAnnotation]
    domains: List[DomainConstraint]
    motifs: List[str]
    target_length: int
    optimization_goals: List[str]
    reference_structure_path: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructureEvaluation:
    source: str
    confidence: float
    ptm: float
    iptm: float
    rmsd_hint: float
    notes: List[str] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExpertFeedback:
    expert: str
    round_index: int
    score: float
    confidence: float
    recommendation: str
    rationale: str
    suggested_actions: List[str] = field(default_factory=list)
    focus_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class ScreeningScores:
    structural_score: float
    energy_score: float
    functional_score: float
    fsm: float
    smr: float
    gci: float
    structure_confidence: float = 0.0
    backend_metrics: Dict[str, float] = field(default_factory=dict)
    detailed_metrics: Dict[str, float] = field(default_factory=dict)

    @property
    def fcs(self) -> float:
        return (self.fsm + self.smr + self.gci) / 3.0


@dataclass
class DesignCandidate:
    sequence: str
    origin: str
    iteration: int
    parent: str | None = None
    notes: List[str] = field(default_factory=list)
    scores: ScreeningScores | None = None
    structure: StructureEvaluation | None = None
    expert_feedback: List[ExpertFeedback] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExpertRoundSummary:
    round_index: int
    lead_expert: str
    mean_score: float
    recommendations: Dict[str, int] = field(default_factory=dict)
    key_actions: List[str] = field(default_factory=list)


@dataclass
class IterationRecord:
    iteration: int
    population: int
    passed: int
    elite: int
    mean_structural_score: float
    mean_energy_score: float
    mean_functional_score: float
    generation_backend: str
    refinement_backend: str
    structure_backend: str
    consensus_score: float = 0.0
    expert_rounds: List[ExpertRoundSummary] = field(default_factory=list)
    feedback_digest: List[str] = field(default_factory=list)


@dataclass
class DesignReport:
    constraints: DesignConstraints
    best_candidates: List[DesignCandidate]
    all_iterations: List[IterationRecord]
    stopped_reason: str
    backend_summary: Dict[str, str]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)
