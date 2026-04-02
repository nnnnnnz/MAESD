#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Iterable, List

from agents.actions.action_bank.requirement import Requirement
from agents.roles.bio_role import BioExpert, DecisionExpertRole, ProtScreenExpert
from agents.roles.custom_role import CustomRole
from agents.roles.nl_role.goec_validator import GOECValidatorRole
from agents.roles.nl_role.intent_analyser import IntentAnalyser
from agents.roles.nl_role.pro_analysiser import ProAnalyser
from agents.roles.nl_role.term_translator import TermTranslatorRole
from agents.roles.role import Role
from agents.roles.role_bank import ROLES_MAPPING
from agents.schema import Message


GROUP_ROLE_MAPPING = {
    "IntentAnalyser": IntentAnalyser,
    "TermTranslator": TermTranslatorRole,
    "GOECValidator": GOECValidatorRole,
    "ProAnalyser": ProAnalyser,
    "BioExpert": BioExpert,
    "ProtScreenExpert": ProtScreenExpert,
    "DecisionExpert": DecisionExpertRole,
}


class Group(Role):
    """A lightweight role container that materializes the role roster selected by the manager."""

    def __init__(self, roles: list[dict], steps: list[str], watch_actions: Iterable[type[Requirement]] | None = None, **kwargs):
        super().__init__(
            name="Group",
            profile="Group",
            goal="Materialize and coordinate the selected roles",
            constraints="Instantiate roles in a MetaGPT-like way and keep the flow ordered",
            **kwargs,
        )
        self.role_specs = roles
        self.steps = steps
        if watch_actions:
            self._watch(watch_actions)

    async def _act(self) -> Message:
        if self.rc.env:
            for role in self._build_roles():
                if role.profile not in self.rc.env.roles:
                    self.rc.env.add_role(role)
        summary = {
            "created_roles": [spec.get("name") for spec in self.role_specs],
            "steps": self.steps,
        }
        return Message(content=str(summary), role=self.profile, cause_by=Requirement, sent_from=self.name)

    def _build_roles(self) -> List[Role]:
        built_roles: List[Role] = []
        for spec in self.role_specs:
            role_name = spec.get("name", "")
            role_cls = GROUP_ROLE_MAPPING.get(role_name) or ROLES_MAPPING.get(role_name)
            if role_cls:
                if role_name in {"ProductManager", "Architect", "ProjectManager"}:
                    built_roles.append(role_cls(watch_actions=[Requirement], proxy=getattr(self, "proxy", ""), llm_api_key=getattr(self, "llm_api_key", ""), serpapi_api_key=getattr(self, "serpapi_api_key", "")))
                elif role_name == "Engineer":
                    built_roles.append(role_cls(proxy=getattr(self, "proxy", ""), llm_api_key=getattr(self, "llm_api_key", ""), serpapi_api_key=getattr(self, "serpapi_api_key", "")))
                else:
                    built_roles.append(role_cls(proxy=getattr(self, "proxy", ""), llm_api_key=getattr(self, "llm_api_key", ""), serpapi_api_key=getattr(self, "serpapi_api_key", "")))
                continue

            built_roles.append(
                CustomRole(
                    name=role_name or "CustomRole",
                    profile=role_name or "CustomRole",
                    goal=spec.get("description", "Execute a custom role"),
                    role_prompt=spec.get("prompt", ""),
                    steps=spec.get("steps", []),
                    tool=spec.get("tools", []),
                    watch_actions=[Requirement],
                    proxy=getattr(self, "proxy", ""),
                    llm_api_key=getattr(self, "llm_api_key", ""),
                    serpapi_api_key=getattr(self, "serpapi_api_key", ""),
                )
            )
        return built_roles
