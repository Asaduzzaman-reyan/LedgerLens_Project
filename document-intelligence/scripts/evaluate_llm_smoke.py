"""Small live-provider check, separate from the rules evaluation."""
import json
import sys
import time
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.processing import parse
from app.extraction import extract_llm,merge_invoices
from app.validation import validate

root=Path(__file__).resolve().parents[1]
settings=Settings()
labels=json.loads((root/'fixtures/labels.json').read_text())
selected={'invoice.pdf','missing-fields.pdf','poor-scan.png'}
rows=[]
for case in labels:
    if case['file'] not in selected:continue
    start=time.perf_counter();correct=0;error=None;invoices=[]
    try:
        invoices=merge_invoices([inv for unit in parse(root/'fixtures'/case['file']) for inv in extract_llm(unit,settings)])
        actual=invoices[0].model_dump(mode='json') if invoices else {}
        for key,expected in case['expected'].items():
            value=actual.get(key)
            equal=Decimal(value)==Decimal(expected) if key in {'subtotal','tax','total'} and value is not None and expected is not None else value==expected
            correct+=int(equal)
    except Exception as exc:
        error=f'{type(exc).__name__}: {str(exc)[:500]}'
    row={'file':case['file'],'seconds':round(time.perf_counter()-start,4),'error':error,'fields_correct':correct,'fields_total':len(case['expected']),'invoices':[i.model_dump(mode='json') for i in invoices],'validation':validate(invoices)}
    rows.append(row)
    print(case['file'],row['seconds'],correct,row['error'],flush=True)
report={'provider':settings.llm_url,'model_alias':settings.llm_model,'schema_constraint':settings.llm_schema,'model':'Qwen2.5-0.5B-Instruct Q4_K_M','runtime':'llama.cpp b6000, CPU, 2 threads, 4096 context','scope':'Three synthetic fixture variants; first-invoice header fields only; local live LLM plus grounding validation. Smoke evaluation, not a representative benchmark. OCR included for poor-scan.png.','fields_correct':sum(r['fields_correct'] for r in rows),'fields_total':sum(r['fields_total'] for r in rows),'successful_responses':sum(r['error'] is None for r in rows),'files':len(rows),'results':rows}
(root/'reports/live-llm-evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
