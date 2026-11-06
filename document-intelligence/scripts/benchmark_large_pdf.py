"""Digital-only 1000-page streaming benchmark, not an OCR scalability claim."""
import json
import os
import sys
import threading
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pymupdf
import psutil
from app.processing import parse
from app.extraction import extract_rules

def main():
    path=Path(sys.argv[1] if len(sys.argv)>1 else 'data/benchmark-1000.pdf')
    path.parent.mkdir(parents=True,exist_ok=True)
    doc=pymupdf.open()
    for n in range(1000):
        page=doc.new_page()
        page.insert_text((50,60),f'Invoice number: LARGE-{n+1}\nInvoice date: 2026-10-15\nSupplier: Northstar\nCustomer: Acme\nSubtotal: 100.00\nTax: 10.00\nTotal: 110.00\nCurrency: USD\nItem: Equipment | 1 | 100.00 | 100.00')
    doc.save(path);doc.close()
    stop=threading.Event();process=psutil.Process(os.getpid());memory=[]
    def sample():
        while not stop.wait(.01):memory.append(process.memory_info().rss)
    thread=threading.Thread(target=sample);thread.start()
    started=time.perf_counter();count=0
    for unit in parse(path):
        assert extract_rules(unit)[0].total==110
        count+=1
    seconds=time.perf_counter()-started;stop.set();thread.join()
    report={'pages':count,'seconds':round(seconds,4),'pages_per_second':round(count/seconds,2),'peak_rss_mb':round(max(memory or [process.memory_info().rss])/1024/1024,2),'file_bytes':path.stat().st_size,'scope':'Digital PDF page reading and rules extraction only; excludes database, queue, embeddings, API, OCR and LLM. Single run, warm process. RSS includes libraries and prior PDF creation.'}
    Path('reports/large-pdf.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
