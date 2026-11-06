"""End-to-end local API/queue benchmark for a supplied digital PDF, embeddings off."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import create_app
from app.config import Settings

source=Path(sys.argv[1])
data=Path(sys.argv[2])
started=time.perf_counter()
with TestClient(create_app(Settings(data=data,embeddings='off'))) as client:
    response=client.post('/api/documents',files={'files':(source.name,source.read_bytes())})
    response.raise_for_status()
    id=response.json()['accepted'][0]['id']
    while time.perf_counter()-started<180:
        doc=client.get('/api/documents/'+id).json()
        if doc['status'] not in {'queued','processing'}:break
        time.sleep(.1)
    assert doc['status']=='review',doc
    assert doc['unit_count']==1000 and len(doc['result'])==1000
    seconds=time.perf_counter()-started
    report={'pages':doc['unit_count'],'invoices':len(doc['result']),'status':doc['status'],'wall_seconds':round(seconds,4),'worker_seconds':round(doc['elapsed'],4),'scope':'In-process FastAPI TestClient upload, durable queue, digital parsing, rules extraction, validation and SQLite writes. No browser/network transit, OCR, LLM or semantic indexing.'}
    Path('reports/large-pdf-api.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
