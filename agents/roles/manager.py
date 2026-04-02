#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from typing import List

from agents.actions.action_bank.requirement import Requirement
from agents.roles.role import Role
from agents.schema import Message


class Manager(Role):
    """MetaGPT-style top-level coordinator that proposes a plan and a role roster."""

    def __init__(
        self,
        name: str = "Mike",
        profile: str = "Manager",
        goal: str = "Break the user request into a collaborative multi-role workflow",
        constraints: str = "Keep the team compact and choose roles with clear responsibilities",
        **kwargs,
    ):
        super().__init__(name=name, profile=profile, goal=goal, constraints=constraints, **kwargs)
        self._watch([Requirement])

    async def _act(self) -> Message:
        latest = self.rc.news[-1] if self.rc.news else Message(content="")
        idea = latest.content.strip()

        roles = self._select_roles(idea)
        plan = self._build_plan(idea)
        content = self._format_manager_output(plan, roles)
        msg = Message(content=content, role=self.profile, cause_by=Requirement, sent_from=self.name)
        self.rc.memory.add(msg)
        return msg

    def _select_roles(self, idea: str) -> List[dict]:
        lowered = idea.lower()
        roles = [
            {
                "name": "IntentAnalyser",
                "description": "Parse the natural-language request into biological intents and constraints.",
                "prompt": "Analyze user intent and extract protein-design-relevant semantics.",
                "steps": ["segment intent", "normalize terminology", "deliver structured intents"],
                "tools": ["llm"],
            },
            {
                "name": "TermTranslator",
                "description": "Translate biological terms into GO and EC level constraints.",
                "prompt": "Map intent terms to GO/EC style structured annotations.",
                "steps": ["extract terms", "align ontology labels", "return structured annotations"],
                "tools": ["go", "ec"],
            },
            {
                "name": "GOECValidator",
                "description": "Validate GO and EC annotations against biological knowledge.",
                "prompt": "Validate ontology and enzyme annotations for consistency.",
                "steps": ["validate go", "validate ec", "report mismatches"],
                "tools": ["go", "ec"],
            },
            {
                "name": "BioExpert",
                "description": "Integrate translated constraints into an executable MAESD design brief.",
                "prompt": "Build a coherent protein design brief from validated constraints.",
                "steps": ["merge annotations", "derive motifs/domains", "summarize design brief"],
                "tools": ["maesd"],
            },
            {
                "name": "ProtScreenExpert",
                "description": "Run SGHFS-like screening and summarize candidate quality.",
                "prompt": "Screen candidate sequences with structural, energetic, and functional metrics.",
                "steps": ["score sequences", "filter candidates", "summarize failures"],
                "tools": ["maesd"],
            },
            {
                "name": "DecisionExpert",
                "description": "Perform Pareto-style selection and decide the next optimization step.",
                "prompt": "Rank candidate sequences and decide which survive the loop.",
                "steps": ["identify elite set", "measure improvement", "decide continue or stop"],
                "tools": ["maesd"],
            },
        ]
        if "code" in lowered or "api" in lowered:
            roles.extend(
                [
                    {"name": "ProductManager", "description": "Write the PRD", "prompt": "Write PRD", "steps": [], "tools": ["llm"]},
                    {"name": "Architect", "description": "Write design", "prompt": "Write design", "steps": [], "tools": ["llm"]},
                    {"name": "ProjectManager", "description": "Write tasks", "prompt": "Write tasks", "steps": [], "tools": ["llm"]},
                    {"name": "Engineer", "description": "Implement code", "prompt": "Write code", "steps": [], "tools": ["llm"]},
                ]
            )
        return roles

    def _build_plan(self, idea: str) -> List[str]:
        return [
            "Translate natural language requirements into biological constraints.",
            "Validate GO/EC annotations and extract domain or motif level requirements.",
            "Synthesize a protein design brief that can drive sequence generation.",
            "Screen candidate sequences with SGHFS-style metrics.",
            "Apply Pareto-style selection and return the best candidates.",
        ]

    def _format_manager_output(self, plan: List[str], roles: List[dict]) -> str:
        plan_block = "\n".join(f"{idx}. {step}" for idx, step in enumerate(plan, start=1))
        roles_block = "\n".join(json.dumps(role, ensure_ascii=False) for role in roles)
        return f"## Execution Plan\n{plan_block}\n## Roles\n{roles_block}\n## End"
