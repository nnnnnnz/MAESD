from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class BackendConfig:
    provider: str = "mock"
    model_name: str | None = None
    executable: str | None = None
    checkpoint: str | None = None
    work_dir: str | None = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MAESDSettings:
    llm_provider: str = "heuristic"
    generation: BackendConfig = field(default_factory=lambda: BackendConfig(provider="auto", model_name="progen2"))
    refinement: BackendConfig = field(default_factory=lambda: BackendConfig(provider="auto", model_name="proteinmpnn"))
    structure: BackendConfig = field(default_factory=lambda: BackendConfig(provider="auto", model_name="alphafold2"))
    max_iterations: int = 5
    population_size: int = 24
    stagnation_limit: int = 3
    seed: int = 7

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "MAESDSettings":
        return cls(
            llm_provider=payload.get("llm_provider", "heuristic"),
            generation=BackendConfig(**payload.get("generation", {})),
            refinement=BackendConfig(**payload.get("refinement", {})),
            structure=BackendConfig(**payload.get("structure", {})),
            max_iterations=int(payload.get("max_iterations", 5)),
            population_size=int(payload.get("population_size", 24)),
            stagnation_limit=int(payload.get("stagnation_limit", 3)),
            seed=int(payload.get("seed", 7)),
        )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "MAESDSettings":
        payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.from_dict(payload)
