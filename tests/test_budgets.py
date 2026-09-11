import tempfile
import unittest
from pathlib import Path

from stillpoint.budgets import BudgetExceeded, BudgetLimits
from stillpoint.db import CompanyDB
from stillpoint.providers.base import ProviderResult
from stillpoint.registry import AgentRegistry
from stillpoint.runtime import CompanyRuntime

ROOT=Path(__file__).resolve().parents[1]

class CountProvider:
    default_model='count'
    def __init__(self):self.calls=0
    def generate(self,**kwargs):
        self.calls+=1
        if kwargs.get('json_schema_name')=='authority_assessment':
            return ProviderResult(text='{"action_family":"none","mode":"unknown","target":"unknown","confidence":0.5,"reason":"none"}',model='count',usage={'total_tokens':2})
        return ProviderResult(text='ok',model='count',usage={'total_tokens':3})

class BudgetTests(unittest.TestCase):
    def make(self,tmp,p,budget):
        return CompanyRuntime(root=tmp,db=CompanyDB(tmp/'db.sqlite'),registry=AgentRegistry(ROOT/'config'/'agents.json'),provider=p,default_model='count',smart_routing=False,default_budget=budget)
    def test_model_call_budget_stops_future_call(self):
        with tempfile.TemporaryDirectory() as d:
            p=CountProvider();rt=self.make(Path(d),p,BudgetLimits(max_model_calls=1))
            with self.assertRaises(BudgetExceeded):rt.submit('Rewrite chapter 3 in my voice.')
            task=rt.db.list_tasks(1)[0]
            self.assertEqual(task['status'],'blocked')
            self.assertEqual(p.calls,1)
            self.assertEqual(rt.db.get_task_usage(task['id'])['model_calls'],1)
            rt.db.close()
    def test_token_usage_accumulates(self):
        with tempfile.TemporaryDirectory() as d:
            p=CountProvider();rt=self.make(Path(d),p,BudgetLimits(max_model_calls=5,max_total_tokens=20))
            out=rt.submit('Rewrite chapter 3 in my voice.')
            usage=rt.db.get_task_usage(out.task_id)
            self.assertGreaterEqual(usage['model_calls'],2)
            self.assertGreaterEqual(usage['total_tokens'],5)
            rt.db.close()

if __name__=='__main__':unittest.main()
