import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app

def wait(client,id):
    for _ in range(100):
        d=client.get('/api/documents/'+id).json()
        if d['status'] not in {'queued','processing'}:return d
        time.sleep(.05)
    raise AssertionError('Job timed out')

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(data=tmp_path,embeddings='off'))) as c:yield c

def upload(client,path):
    r=client.post('/api/documents',files={'files':(path.name,path.read_bytes())})
    assert r.status_code==202
    return r.json()['accepted'][0]['id']

def test_upload_process_search_correct_compare(client,fixtures):
    id=upload(client,fixtures/'invoice.pdf');d=wait(client,id)
    assert d['status']=='review' and d['result'][0]['total']=='275.00'
    assert client.get('/api/documents?q=Northstar').json()['total']==1
    assert client.get('/api/documents/'+id+'/units').json()['items'][0]['method']=='digital'
    assert client.get('/api/documents/'+id+'/original').content.startswith(b'%PDF')
    result=d['result'];result[0]['total']='290.00'
    body={'version':d['version'],'invoices':result,'reason':'Checked source total'}
    changed=client.patch('/api/documents/'+id,json=body)
    assert changed.status_code==200
    assert any(e['code']=='total_mismatch' for e in changed.json()['errors'])
    assert client.patch('/api/documents/'+id,json=body).status_code==409
    ledger=upload(client,fixtures/'ledger.xlsx');wait(client,ledger)
    r=client.post('/api/compare',json={'document_ids':[id,ledger]})
    assert r.status_code==200 and not r.json()['comparisons'][0]['matches']
    assert client.post('/api/documents/'+id+'/retry').status_code==409

def test_failed_job_retry(client,fixtures):
    id=upload(client,fixtures/'corrupt.pdf');assert wait(client,id)['status']=='failed'
    assert client.post('/api/documents/'+id+'/retry').status_code==202
    d=wait(client,id)
    assert d['status']=='failed' and d['attempts']==2

def test_duplicate_invoice(client,fixtures):
    id=upload(client,fixtures/'invoice.pdf');wait(client,id)
    second=upload(client,fixtures/'invoice.pdf');d=wait(client,second)
    assert {'duplicate_file','duplicate_invoice'}<={e['code'] for e in d['errors']}
    d['result'][0]['invoice_number']='UNIQUE-CORRECTED'
    corrected=client.patch('/api/documents/'+second,json={'version':d['version'],'invoices':d['result'],'reason':'Correct invoice identity'}).json()
    assert 'duplicate_invoice' not in {e['code'] for e in corrected['errors']}

def test_rejected_and_not_found(client):
    r=client.post('/api/documents',files=[('files',('bad.exe',b'x')),('files',('empty.pdf',b''))]).json()
    assert len(r['rejected'])==2 and not r['accepted']
    assert client.get('/api/documents/missing').status_code==404
    assert client.get('/api/search?q=chairs').status_code==503
    assert client.get('/api/documents?status=oops').status_code==400

def test_auth_and_cross_origin(tmp_path):
    with TestClient(create_app(Settings(data=tmp_path,worker=False,token='secret',embeddings='off'))) as c:
        assert c.get('/api/documents').status_code==401
        assert c.get('/api/documents',headers={'Authorization':'Bearer secret'}).status_code==200
        assert c.post('/api/documents',headers={'Origin':'https://attacker.example'}).status_code==403

def test_durable_queue_and_lease_recovery(tmp_path,fixtures):
    settings=Settings(data=tmp_path,worker=False,embeddings='off')
    app=create_app(settings)
    with TestClient(app) as c:id=upload(c,fixtures/'invoice.pdf')
    with app.state.db.connect() as con:
        con.execute("UPDATE documents SET status='processing',lease_owner='dead',lease_until=0 WHERE id=?",(id,))
    settings.worker=True
    with TestClient(create_app(settings)) as c:
        d=wait(c,id)
        assert d['status']=='review'
        assert 'lease_recovered' in [h['event'] for h in d['history']]

def test_size_limit(tmp_path):
    with TestClient(create_app(Settings(data=tmp_path,worker=False,embeddings='off',max_mb=1))) as c:
        r=c.post('/api/documents',files={'files':('large.pdf',b'x'*1048577)}).json()
        assert not r['accepted'] and 'size limit' in r['rejected'][0]['error']
