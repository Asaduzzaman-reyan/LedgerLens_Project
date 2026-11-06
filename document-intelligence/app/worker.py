import json
import logging
import threading
import time
import uuid
from .processing import parse
from .extraction import extract_rules, extract_llm, merge_invoices
from .validation import validate
from .models import Invoice

logger = logging.getLogger(__name__)

class Worker:
    def __init__(self, db, settings, embeddings):
        self.db,self.settings,self.embeddings = db,settings,embeddings
        self.owner = uuid.uuid4().hex
        self.stop = threading.Event()
        self.thread = None
    def start(self):
        self.thread = threading.Thread(target=self.run,daemon=True,name='document-worker')
        self.thread.start()
    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=5)
    def claim(self):
        now = time.time()
        with self.db.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            stale = con.execute("SELECT id FROM documents WHERE status='processing' AND lease_until<?",(now,)).fetchall()
            for row in stale:
                con.execute("UPDATE documents SET status='queued',lease_owner=NULL WHERE id=?",(row['id'],))
                self.db.history(con,row['id'],'lease_recovered',{})
            row = con.execute("SELECT * FROM documents WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not row:
                return None
            con.execute("UPDATE documents SET status='processing',lease_owner=?,lease_until=?,attempts=attempts+1,updated=? WHERE id=?",(self.owner,now+180,now,row['id']))
            self.db.history(con,row['id'],'processing',{'extractor':self.settings.extractor})
            return dict(row)
    def run(self):
        while not self.stop.is_set():
            try:
                doc = self.claim()
                if doc:
                    self.process(doc)
                else:
                    self.stop.wait(0.5)
            except Exception:
                logger.exception('Worker loop failed')
                self.stop.wait(1)
    def process(self, doc):
        id,start = doc['id'],time.perf_counter()
        done = threading.Event()
        def heartbeat():
            while not done.wait(30):
                with self.db.connect() as con:
                    con.execute('UPDATE documents SET lease_until=? WHERE id=? AND lease_owner=?',(time.time()+180,id,self.owner))
        pulse = threading.Thread(target=heartbeat,daemon=True)
        pulse.start()
        try:
            with self.db.connect() as con:
                con.execute('DELETE FROM units WHERE document_id=?',(id,))
                con.execute('DELETE FROM unit_search WHERE document_id=?',(id,))
            invoices = []
            warnings = []
            readable = False
            for ordinal,unit in enumerate(parse(self.settings.data/'uploads'/(id+doc['extension']),self.settings.max_units)):
                if time.perf_counter()-start>self.settings.job_seconds:
                    raise ValueError('Job time budget exceeded')
                readable = readable or bool(unit.text.strip())
                if not unit.text.strip():
                    warnings.append({'invoice':None,'field':unit.source,'code':'empty_unit','message':'No readable text on this page/frame'})
                extracted = extract_llm(unit,self.settings) if self.settings.extractor=='llm' else extract_rules(unit)
                if unit.method=='ocr' and (unit.confidence or 0)<0.85:
                    for inv in extracted:
                        if 'ocr_quality' not in inv.uncertain_fields:
                            inv.uncertain_fields.append('ocr_quality')
                invoices.extend(extracted)
                vector = None
                if unit.text.strip():
                    try:
                        vector = self.embeddings.encode([unit.text[:16000]])[0]
                    except Exception as exc:
                        if not any(w['code']=='index_failure' for w in warnings):
                            warnings.append({'invoice':None,'field':'search','code':'index_failure','message':f'Semantic indexing unavailable ({type(exc).__name__}); keyword search remains available'})
                with self.db.connect() as con:
                    owner = con.execute('SELECT lease_owner FROM documents WHERE id=?',(id,)).fetchone()[0]
                    if owner != self.owner:
                        return
                    con.execute('INSERT INTO units VALUES(?,?,?,?,?,?,?)',(id,ordinal,unit.source,unit.text,unit.method,unit.confidence,json.dumps(vector) if vector else None))
                    con.execute('INSERT INTO unit_search(document_id,text) VALUES(?,?)',(id,unit.text))
                    con.execute('UPDATE documents SET progress=?,unit_count=?,updated=? WHERE id=?',(ordinal+1,ordinal+1,time.time(),id))
            if not readable:
                raise ValueError('No readable text; improve scan quality and retry')
            invoices = merge_invoices(invoices)
            with self.db.connect() as con:
                duplicate = con.execute('SELECT id FROM documents WHERE sha256=? AND id<>? AND created<=? LIMIT 1',(doc['sha256'],id,doc['created'])).fetchone() is not None
                issues = validate(invoices,duplicate)+warnings
                keys = {(i.invoice_number.casefold(),i.supplier_name.casefold()) for i in invoices if i.invoice_number and i.supplier_name}
                for other in con.execute("SELECT id,result FROM documents WHERE id<>? AND result IS NOT NULL",(id,)):
                    for raw in json.loads(other['result']):
                        key = ((raw.get('invoice_number') or '').casefold(),(raw.get('supplier_name') or '').casefold())
                        if key in keys:
                            issues.append({'invoice':None,'field':'invoice_number','code':'duplicate_invoice','message':f'Matching supplier/invoice in document {other["id"]}'})
                            break
                status = 'review' if issues else 'completed'
                result = [i.model_dump(mode='json') for i in invoices]
                con.execute('UPDATE documents SET status=?,result=?,errors=?,failure=NULL,elapsed=?,updated=?,lease_owner=NULL,lease_until=NULL WHERE id=? AND lease_owner=?',
                            (status,json.dumps(result),json.dumps(issues),time.perf_counter()-start,time.time(),id,self.owner))
                self.db.history(con,id,'processed',{'status':status,'units':ordinal+1,'invoices':len(result)})
        except Exception as exc:
            logger.exception('Document %s failed',id)
            with self.db.connect() as con:
                con.execute("UPDATE documents SET status='failed',failure=?,elapsed=?,updated=?,lease_owner=NULL,lease_until=NULL WHERE id=? AND lease_owner=?",
                            (f'{type(exc).__name__}: processing failed. Check format, scan quality, limits, and provider configuration.',time.perf_counter()-start,time.time(),id,self.owner))
                self.db.history(con,id,'failed',{'error_type':type(exc).__name__})
        finally:
            done.set()
            pulse.join(timeout=1)
