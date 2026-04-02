from __future__ import annotations

from typing import Dict, Type

from ..config import BackendConfig
from .base import BaseBackendAdapter, SequenceGenerationBackend, SequenceRefinementBackend, StructurePredictionBackend
from .external import ExternalAlphaFold2Adapter, ExternalProGen2Adapter, ExternalProteinMPNNAdapter
from .mock import MockAlphaFold2Adapter, MockProGen2Adapter, MockProteinMPNNAdapter


GENERATION_BACKENDS: Dict[str, Type[SequenceGenerationBackend]] = {
    "mock": MockProGen2Adapter,
    "progen2": ExternalProGen2Adapter,
}

REFINEMENT_BACKENDS: Dict[str, Type[SequenceRefinementBackend]] = {
    "mock": MockProteinMPNNAdapter,
    "proteinmpnn": ExternalProteinMPNNAdapter,
}

STRUCTURE_BACKENDS: Dict[str, Type[StructurePredictionBackend]] = {
    "mock": MockAlphaFold2Adapter,
    "alphafold2": ExternalAlphaFold2Adapter,
}


def build_generation_backend(config: BackendConfig) -> SequenceGenerationBackend:
    return _build_backend(config, GENERATION_BACKENDS)


def build_refinement_backend(config: BackendConfig) -> SequenceRefinementBackend:
    return _build_backend(config, REFINEMENT_BACKENDS)


def build_structure_backend(config: BackendConfig) -> StructurePredictionBackend:
    return _build_backend(config, STRUCTURE_BACKENDS)


def _build_backend(config: BackendConfig, registry: Dict[str, Type[BaseBackendAdapter]]):
    provider = config.provider.lower()
    if provider == "auto":
        provider = _resolve_auto_provider(config, registry)
    if provider not in registry:
        supported = ", ".join(sorted(registry))
        raise ValueError(f"Unsupported backend provider '{provider}'. Supported providers: {supported}")
    config.provider = provider
    return registry[provider](config)


def _resolve_auto_provider(config: BackendConfig, registry: Dict[str, Type[BaseBackendAdapter]]) -> str:
    if config.executable or config.checkpoint or config.work_dir or config.extra.get("command") or config.extra.get("script_path"):
        for preferred in ("progen2", "proteinmpnn", "alphafold2"):
            if preferred in registry:
                return preferred
    return "mock"
