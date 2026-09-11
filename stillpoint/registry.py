from __future__ import annotations

from pathlib import Path

from .config import load_json
from .models import AgentSpec


class AgentRegistry:
    def __init__(self, config_path: Path):
        raw = load_json(config_path)
        self._agents: dict[str, AgentSpec] = {}
        for item in raw["agents"]:
            spec = AgentSpec(**item)
            if spec.id in self._agents:
                raise ValueError(f"duplicate agent id: {spec.id}")
            self._agents[spec.id] = spec
        if "orchestra" not in self._agents:
            raise ValueError("agent registry must contain orchestra")
        if "stillpoint" not in self._agents:
            raise ValueError("agent registry must contain stillpoint")

    def get(self, agent_id: str) -> AgentSpec:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise KeyError(f"unknown agent: {agent_id}") from exc

    def enabled(self) -> list[AgentSpec]:
        return [a for a in self._agents.values() if a.enabled]

    def ids(self) -> list[str]:
        return [a.id for a in self.enabled()]
