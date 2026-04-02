from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence

from ..config import BackendConfig
from ..schema import DesignCandidate, DesignConstraints, StructureEvaluation


@dataclass
class GenerationRequest:
    constraints: DesignConstraints
    population_size: int
    seed: int


@dataclass
class RefinementRequest:
    constraints: DesignConstraints
    parents: Sequence[DesignCandidate]
    population_size: int
    iteration: int
    seed: int


@dataclass
class StructurePredictionRequest:
    constraints: DesignConstraints
    candidate: DesignCandidate
    iteration: int


@dataclass
class BackendResult:
    backend_name: str
    metadata: Dict[str, str] = field(default_factory=dict)


class BaseBackendAdapter:
    backend_kind = "base"

    def __init__(self, config: BackendConfig):
        self.config = config

    @property
    def name(self) -> str:
        return self.config.model_name or self.__class__.__name__


class SequenceGenerationBackend(BaseBackendAdapter):
    backend_kind = "generation"

    def generate(self, request: GenerationRequest) -> List[DesignCandidate]:
        raise NotImplementedError


class SequenceRefinementBackend(BaseBackendAdapter):
    backend_kind = "refinement"

    def refine(self, request: RefinementRequest) -> List[DesignCandidate]:
        raise NotImplementedError


class StructurePredictionBackend(BaseBackendAdapter):
    backend_kind = "structure"

    def predict(self, request: StructurePredictionRequest) -> StructureEvaluation:
        raise NotImplementedError
