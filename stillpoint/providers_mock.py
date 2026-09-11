class ProviderResult:
    def __init__(self,text,model="mock",citations=None,provider_response_id=None,usage=None):self.text=text;self.model=model;self.citations=citations or [];self.provider_response_id=provider_response_id;self.usage=usage
class MockProvider:
    default_model="mock"
    def generate(self,*,system,prompt,model,tools=None,**kwargs):
        if "Begin with exactly one judgment word" in prompt:return ProviderResult("PASS\nMock review",model)
        # semantic authority calls should fail closed to deterministic by returning invalid schema.
        if kwargs.get("json_schema_name")=="authority_assessment":return ProviderResult("{}",model)
        role="unknown"
        for line in system.splitlines():
            if line.startswith("ROLE:"):role=line.split(":",1)[1].strip();break
        return ProviderResult(f"[MOCK]\nRole: {role}\n{prompt[:80]}",model)
