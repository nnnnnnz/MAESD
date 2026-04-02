from __future__ import annotations

import asyncio
import json
from typing import List

from agents.maesd.config import MAESDSettings


class EnvironmentPipelineRole:
    """A lightweight environment-compatible role adapter for the MAESD pipeline."""

    def __init__(
        self,
        settings: MAESDSettings | None = None,
        seed: int | None = None,
        connector_config_path: str | None = None,
        max_iterations: int | None = None,
        population_size: int | None = None,
        stagnation_limit: int | None = None,
        reference_structure_path: str | None = None,
        name: str = "Mira",
        profile: str = "MAESDDesigner",
    ):
        self.settings = settings or MAESDSettings()
        if seed is not None:
            self.settings.seed = seed
        self.connector_config_path = connector_config_path
        self.max_iterations = max_iterations
        self.population_size = population_size
        self.stagnation_limit = stagnation_limit
        self.reference_structure_path = reference_structure_path
        self.name = name
        self.profile = profile
        self.addresses = {self.profile, self.name}
        self.env = None
        self._buffer: List[object] = []
        self._memory: List[object] = []

    def set_env(self, env):
        self.env = env

    def put_message(self, message):
        if message:
            self._buffer.append(message)

    async def run(self):
        if not self._buffer:
            return None
        latest = self._buffer.pop(0)
        from agents.maesd import MAESDPipeline
        from agents.maesd.ira import IntentRecognitionAgent
        from agents.system.schema import Message

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
        response = Message(content=report.to_json(), role=self.profile, sent_from=self.name)
        self._memory.append(response)
        if self.env:
            self.env.publish_message(response)
        return response

    def get_memories(self):
        return list(self._memory)


async def run_maesd_in_environment_async(
    prompt: str,
    settings: MAESDSettings | None = None,
    seed: int | None = None,
    connector_config_path: str | None = None,
    max_iterations: int | None = None,
    population_size: int | None = None,
    stagnation_limit: int | None = None,
    reference_structure_path: str | None = None,
) -> dict:
    from agents.environment import Environment
    from agents.system.schema import Message

    env = Environment(desc="MAESD environment-driven protein design workflow")
    role = EnvironmentPipelineRole(
        settings=settings,
        seed=seed,
        connector_config_path=connector_config_path,
        max_iterations=max_iterations,
        population_size=population_size,
        stagnation_limit=stagnation_limit,
        reference_structure_path=reference_structure_path,
    )
    env.add_role(role)
    role.put_message(Message(content=prompt, role="user", sent_from="user", send_to=role.profile))
    await env.run(k=1)
    outputs = role.get_memories()
    return json.loads(outputs[-1].content) if outputs else {}


def run_maesd_in_environment(
    prompt: str,
    settings: MAESDSettings | None = None,
    seed: int | None = None,
    connector_config_path: str | None = None,
    max_iterations: int | None = None,
    population_size: int | None = None,
    stagnation_limit: int | None = None,
    reference_structure_path: str | None = None,
) -> dict:
    return asyncio.run(
        run_maesd_in_environment_async(
            prompt=prompt,
            settings=settings,
            seed=seed,
            connector_config_path=connector_config_path,
            max_iterations=max_iterations,
            population_size=population_size,
            stagnation_limit=stagnation_limit,
            reference_structure_path=reference_structure_path,
        )
    )
