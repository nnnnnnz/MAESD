#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
from typing import Iterable

from pydantic import BaseModel, Field

from agents.system.schema import Message
from agents.system.memory.memory import Memory


class Environment(BaseModel):
    """Minimal message-driven environment compatible with the current Role runtime."""

    roles: dict[str, object] = Field(default_factory=dict)
    memory: Memory = Field(default_factory=Memory)
    history: str = Field(default="")
    desc: str = Field(default="MAESD collaborative environment")
    address_book: dict[str, set[str]] = Field(default_factory=dict)
    task_id: str = Field(default="")
    proxy: str = Field(default="")
    llm_api_key: str = Field(default="")
    serpapi_key: str = Field(default="")
    alg_msg_queue: object = Field(default=None)

    class Config:
        arbitrary_types_allowed = True

    def add_role(self, role):
        role.set_env(self)
        self.roles[role.profile] = role
        self.address_book[role.profile] = set(getattr(role, "addresses", set()) or {role.profile, role.name})

    def add_roles(self, roles: Iterable[object]):
        for role in roles:
            self.add_role(role)

    def set_addresses(self, role, addresses: set[str]):
        key = getattr(role, "profile", "") or getattr(role, "name", "")
        self.address_book[key] = set(addresses or set())

    def role_names(self) -> list[str]:
        return list(self.roles.keys())

    def publish_message(self, message: Message):
        if not message:
            return
        self.memory.add(message)
        self.history += f"\n{message}"
        targets = getattr(message, "send_to", None) or set()
        route_all = not targets or "__all__" in targets
        sender = getattr(message, "role", "")
        for profile, role in self.roles.items():
            if profile == sender:
                continue
            addresses = self.address_book.get(profile, {profile})
            if route_all or addresses.intersection(set(targets)):
                role.put_message(message)

    async def run(self, k: int = 1):
        for _ in range(k):
            futures = [role.run() for role in self.roles.values()]
            if futures:
                await asyncio.gather(*futures)

    def get_roles(self) -> dict[str, object]:
        return self.roles

    def get_role(self, name: str):
        return self.roles.get(name, None)
