import unittest
from pathlib import Path

from stillpoint.policy import CompanyPolicy
from stillpoint.registry import AgentRegistry
from stillpoint.router import Router
from stillpoint.capabilities import capabilities_for_call, to_xai_tools

ROOT=Path(__file__).resolve().parents[1]


class ToolScopePlanTests(unittest.TestCase):
    def router(self):
        return Router(AgentRegistry(ROOT/'config'/'agents.json'), CompanyPolicy())

    def test_explicit_historical_x_dates_survive(self):
        plan=self.router().plan('Scan X posts from 2024-01-01 to 2024-02-01 about book talks.')
        reqs=capabilities_for_call(agent_id=plan.primary, plan_capabilities=plan.capabilities, agent_capabilities=plan.primary_capabilities, scoped_requests=plan.primary_tool_requests)
        specs=to_xai_tools(reqs)
        self.assertEqual(specs[0]['type'],'x_search')
        self.assertEqual(specs[0]['from_date'],'2024-01-01')
        self.assertEqual(specs[0]['to_date'],'2024-02-01')


if __name__ == '__main__': unittest.main()
