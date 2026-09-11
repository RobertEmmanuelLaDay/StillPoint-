from __future__ import annotations
import json
from pathlib import Path
from .models import AgentSpec
class AgentRegistry:
    def __init__(self,config_path:Path):
        raw=json.loads(config_path.read_text());self._agents={}
        for item in raw["agents"]:
            spec=AgentSpec(**item)
            if spec.id in self._agents:raise ValueError("duplicate agent id")
            self._agents[spec.id]=spec
        if "orchestra" not in self._agents or "stillpoint" not in self._agents:raise ValueError("registry missing required agents")
    def get(self,agent_id):return self._agents[agent_id]
    def enabled(self):return [a for a in self._agents.values() if a.enabled]
    def ids(self):return [a.id for a in self.enabled()]
