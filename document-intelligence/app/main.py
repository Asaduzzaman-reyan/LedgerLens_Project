import hashlib
import hmac
import json
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings
from .database import Database
from .models import Correction, CompareRequest
from .search import Embeddings
from .validation import validate, cross_compare
from .worker import Worker

ALLOWED = {'.pdf','.png','.jpg','.jpeg','.tif','.tiff','.xlsx','.xls','.csv'}

def create_app(settings=None):
    settings = settings or Settings()
    settings.data.mkdir(parents=True,exist_ok=True)
    (settings.data/'uploads').mkdir(exist_ok=True)
    db = Database(settings.data/'documents.sqlite3')
    embeddings = Embeddings(settings)
    worker = Worker(db,settings,embeddings)
    @asynccontextmanager
    async def lifespan(app):
        if settings.worker:
            worker.start()
        yield
        worker.close()
    api = FastAPI(title='LedgerLens Document Intelligence',version='1.0.0',lifespan=lifespan)
    api.state.db,api.state.worker = db,worker
    def auth(authorization: str | None = Header(default=None)):
        if settings.token and not hmac.compare_digest(authorization or '',f'Bearer {settings.token}'):
            raise HTTPException(401,'Valid bearer token required')
    def get_doc(id):
        doc = db.get(id)
        if not doc:
            raise HTTPException(404,'Document not found')
        return doc
    @api.middleware('http')
    async def guard(request,call_next):
        # Reject cross-origin browser writes; API is same-origin by design.
        origin = request.headers.get('origin')
        if request.method in {'POST','PUT','PATCH','DELETE'} and origin and origin != str(request.base_url).rstrip('/'):
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Cross-origin writes are not allowed'},status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'"
        if request.url.path in {'/docs','/redoc','/docs/oauth2-redirect'}:
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'"
        return response
    @api.get('/api/health')
    def health():
        return {'status':'ok','extractor':settings.extractor,'embeddings':settings.embeddings,'authentication':bool(settings.token)}
    @api.post('/api/documents',dependencies=[Depends(auth)],status_code=202)
    async def upload(files: list[UploadFile] = File(...)):
        if not 1<=len(files)<=20:
            raise HTTPException(400,'Upload between 1 and 20 files')
        accepted,rejected = [],[]
        for file in files:
            filename = (file.filename or 'unnamed').replace('\\','/').split('/')[-1][:200]
            ext = Path(filename).suffix.lower()
            if ext not in ALLOWED:
                rejected.append({'filename':filename,'error':'Unsupported extension'})
                await file.close()
                continue
            id = uuid.uuid4().hex
            path = settings.data/'uploads'/(id+ext)
            digest,size = hashlib.sha256(),0
            try:
                with path.open('wb') as stream:
                    while chunk := await file.read(1024*1024):
                        size += len(chunk)
                        if size>settings.max_mb*1024*1024:
                            raise ValueError('File exceeds upload size limit')
                        digest.update(chunk)
                        stream.write(chunk)
                if size==0:
                    raise ValueError('Empty file')
                now = time.time()
                with db.connect() as con:
                    con.execute('INSERT INTO documents(id,filename,extension,sha256,size,status,created,updated) VALUES(?,?,?,?,?,?,?,?)',
                                (id,filename,ext,digest.hexdigest(),size,'queued',now,now))
                    db.history(con,id,'uploaded',{'size':size})
                accepted.append({'id':id,'filename':filename,'status':'queued'})
            except ValueError as exc:
                path.unlink(missing_ok=True)
                rejected.append({'filename':filename,'error':str(exc)})
            finally:
                await file.close()
        return {'accepted':accepted,'rejected':rejected}
    @api.get('/api/documents',dependencies=[Depends(auth)])
    def documents(q: str = Query('',max_length=200), status: str = '', limit: int = Query(50,ge=1,le=200), offset: int = Query(0,ge=0)):
        conditions,args = [],[]
        if q:
            conditions.append("(filename LIKE ? ESCAPE '\\' OR result LIKE ? ESCAPE '\\' OR id IN (SELECT document_id FROM unit_search WHERE unit_search MATCH ?))")
            pattern = '%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
            args.extend([pattern,pattern,'"'+q.replace('"','""')+'"'])
        if status:
            if status not in {'queued','processing','review','completed','failed'}:
                raise HTTPException(400,'Invalid status')
            conditions.append('status=?')
            args.append(status)
        where = ' WHERE '+' AND '.join(conditions) if conditions else ''
        with db.connect() as con:
            total = con.execute('SELECT count(*) FROM documents'+where,args).fetchone()[0]
            rows = con.execute('SELECT id,filename,status,progress,unit_count,created,elapsed,version,errors FROM documents'+where+' ORDER BY created DESC LIMIT ? OFFSET ?',args+[limit,offset]).fetchall()
        return {'total':total,'items':[dict(r)|{'errors':json.loads(r['errors'])} for r in rows]}
    @api.get('/api/search',dependencies=[Depends(auth)])
    def semantic(q: str = Query(min_length=2,max_length=500),limit: int = Query(20,ge=1,le=50)):
        try:
            hits = embeddings.search(db,q,limit)
            return {'items':[hit|{'filename':get_doc(hit['id'])['filename']} for hit in hits],'model':'BAAI/bge-small-en-v1.5'}
        except Exception as exc:
            raise HTTPException(503,f'Semantic search unavailable ({type(exc).__name__}); verify model download or enable embeddings') from exc
    @api.post('/api/compare',dependencies=[Depends(auth)])
    def compare(body: CompareRequest):
        ids = list(dict.fromkeys(body.document_ids))
        if len(ids)<2:
            raise HTTPException(400,'Select at least two distinct documents')
        docs = [get_doc(id) for id in ids]
        if any(d['status'] not in {'review','completed'} for d in docs):
            raise HTTPException(409,'All compared documents must finish processing')
        return cross_compare(docs)
    @api.get('/api/documents/{id}',dependencies=[Depends(auth)])
    def detail(id: str):
        return get_doc(id)
    @api.get('/api/documents/{id}/units',dependencies=[Depends(auth)])
    def units(id: str,offset: int = Query(0,ge=0),limit: int = Query(20,ge=1,le=100)):
        get_doc(id)
        with db.connect() as con:
            return {'items':[dict(r) for r in con.execute('SELECT ordinal,source,text,method,confidence FROM units WHERE document_id=? ORDER BY ordinal LIMIT ? OFFSET ?',(id,limit,offset))]}
    @api.get('/api/documents/{id}/original',dependencies=[Depends(auth)])
    def original(id: str):
        doc = get_doc(id)
        return FileResponse(settings.data/'uploads'/(id+doc['extension']),filename=doc['filename'],media_type='application/octet-stream')
    @api.patch('/api/documents/{id}',dependencies=[Depends(auth)])
    def correct(id: str,body: Correction):
        with db.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            row = con.execute('SELECT * FROM documents WHERE id=?',(id,)).fetchone()
            if not row:
                raise HTTPException(404,'Document not found')
            if row['status'] not in {'review','completed'}:
                raise HTTPException(409,'Only processed documents can be corrected')
            if body.version!=row['version']:
                raise HTTPException(409,'Record changed; refresh before saving')
            # Provenance stays immutable; edits cannot masquerade as source evidence.
            before = json.loads(row['result'])
            if len(body.invoices)!=len(before):
                raise HTTPException(400,'Correction must preserve invoice count')
            for inv,old in zip(body.invoices,before):
                inv.method = 'manual'
                inv.sources = old.get('sources',[])
                inv.evidence = old.get('evidence',{})
            persistent = [e for e in json.loads(row['errors']) if e['code'] in {'duplicate_file','index_failure','empty_unit'}]
            keys = {(inv.invoice_number.casefold(),inv.supplier_name.casefold()) for inv in body.invoices if inv.invoice_number and inv.supplier_name}
            for other in con.execute('SELECT id,result FROM documents WHERE id<>? AND result IS NOT NULL',(id,)):
                if any(((r.get('invoice_number') or '').casefold(),(r.get('supplier_name') or '').casefold()) in keys for r in json.loads(other['result'])):
                    persistent.append({'invoice':None,'field':'invoice_number','code':'duplicate_invoice','message':f'Matching supplier/invoice in document {other["id"]}'})
            issues = validate(body.invoices)+persistent
            result = [i.model_dump(mode='json') for i in body.invoices]
            con.execute('UPDATE documents SET result=?,errors=?,status=?,version=version+1,updated=? WHERE id=?',
                        (json.dumps(result),json.dumps(issues),'review' if issues else 'completed',time.time(),id))
            db.history(con,id,'corrected',{'reason':body.reason,'before':before,'after':result})
        return get_doc(id)
    @api.post('/api/documents/{id}/retry',dependencies=[Depends(auth)],status_code=202)
    def retry(id: str):
        with db.connect() as con:
            changed = con.execute("UPDATE documents SET status='queued',progress=0,failure=NULL,result=NULL,errors='[]',version=version+1,updated=? WHERE id=? AND status='failed'",(time.time(),id)).rowcount
            if not changed:
                get_doc(id)
                raise HTTPException(409,'Only failed jobs can be retried')
            db.history(con,id,'retry_requested',{})
        return {'id':id,'status':'queued'}
    static = Path(__file__).resolve().parents[1]/'frontend'/'dist'
    if static.exists():
        api.mount('/',StaticFiles(directory=static,html=True),name='frontend')
    return api

app = create_app()
