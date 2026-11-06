import json
import httpx
import pytest
from app.config import Settings
from app.processing import Unit
from app.extraction import extract_llm

def mock_client(monkeypatch,payload,status=200):
    original=httpx.Client
    transport=httpx.MockTransport(lambda req:httpx.Response(status,json={'choices':[{'message':{'content':json.dumps(payload)}}]}))
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=transport,**kw))

def test_ai_grounding(monkeypatch):
    mock_client(monkeypatch,{'invoices':[{'invoice_number':'A-1','total':'99','supplier_name':'Invented Ltd','evidence':{'invoice_number':'Invoice number: A-1','total':'Total: 99','supplier_name':'Invented Ltd'}}]})
    inv=extract_llm(Unit('p1','Invoice number: A-1\nTotal: 42','digital'),Settings())[0]
    assert inv.invoice_number=='A-1'
    assert inv.total is None and inv.supplier_name is None

def test_ai_schema_failure(monkeypatch):
    mock_client(monkeypatch,{'invoices':[{'total':'NaN','unexpected':'x'}]})
    with pytest.raises(ValueError):extract_llm(Unit('p1','Total: 10','digital'),Settings())

def test_ai_provider_failure(monkeypatch):
    mock_client(monkeypatch,{},503)
    with pytest.raises(httpx.HTTPStatusError):extract_llm(Unit('p1','test','digital'),Settings())

def test_optional_schema_contract(monkeypatch):
    original=httpx.Client
    def handler(request):
        body=json.loads(request.content)
        assert 'invoices' in body['response_format']['schema']['properties']
        assert body['max_tokens']==2048
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'invoices':[{'invoice_number':'A','evidence':{'invoice_number':'A'}}]})}}]})
    transport=httpx.MockTransport(handler)
    monkeypatch.setattr(httpx,'Client',lambda **kw:original(transport=transport,**kw))
    assert extract_llm(Unit('p1','Invoice number: A','digital'),Settings(llm_schema=True))[0].invoice_number=='A'
