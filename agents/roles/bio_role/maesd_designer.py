#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from agents.actions.action_bank.requirement import Requirement
from agents.maesd import MAESDPipeline, MAESDSettings
from agents.maesd.ira import IntentRecognitionAgent
from agents.roles.role import Role
from agents.schema import Message


class MAESDDesignerRole(Role):
    """Environment-compatible role that runs the current MAESD pipeline end to end."""

    def __init__(
        self,
        name: str = "Mira",
        profile: str = "MAESDDesigner",
        goal: str = "Turn natural-language protein requirements into screened candidate sequences",
        constraints: str = "Use the MAESD pipeline and return structured sequence design results",
        settings: MAESDSettings | None = None,
        seed: int | None = None,
        connector_config_path: str | None = None,
        max_iterations: int | None = None,
        population_size: int | None = None,
        stagnation_limit: int | None = None,
        reference_structure_path: str | None = None,
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints, **kwargs)
        self.settings = settings or MAESDSettings()
        if seed is not None:
            self.settings.seed = seed
        self.connector_config_path = connector_config_path
        self.max_iterations = max_iterations
        self.population_size = population_size
        self.stagnation_limit = stagnation_limit
        self.reference_structure_path = reference_structure_path
        self._watch([Requirement])

    async def _act(self) -> Message:
        latest = self.rc.news[-1] if self.rc.news else Message(content="")
        pipeline = MAESDPipeline(settings=self.settings, seed=self.settings.seed)
        if self.connector_config_path:
            pipeline.ira = IntentRecognitionAgent(connector_config_path=self.connector_config_path)
        report = pipeline.run(
            latest.content,
            max_iterations=self.max_iterations,
            population_size=self.population_size,
            stagnation_limit=self.stagnation_limit,
            reference_structure_path=self.reference_structure_path,
        )
        msg = Message(
            content=report.to_json(),
            role=self.profile,
            cause_by=Requirement,
            sent_from=self.name,
        )
        self.rc.memory.add(msg)
        return msg
