"""Measure extraction independently of search/model download and API overhead."""
import json
import statistics
import sys
import time
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.processing import parse
from app.extraction import extract_rules,extract_llm,merge_invoices
from scripts.generate_fixtures import FIXTURES,generate

def evaluate():
    if not (FIXTURES/'labels.json').exists():generate()
    settings=Settings()
    labels=json.loads((FIXTURES/'labels.json').read_text())
    rows=[];correct=slots=0
    for case in labels:
        started=time.perf_counter();outcome='success';error=None;field_correct=0;field_count=0
        try:
            invs=merge_invoices([inv for unit in parse(FIXTURES/case['file']) for inv in (extract_llm(unit,settings) if settings.extractor=='llm' else extract_rules(unit))])
            actual=invs[0].model_dump(mode='json') if invs else {}
            for key,expected in case['expected'].items():
                field_count+=1;a=actual.get(key)
                if key in {'subtotal','tax','total'} and a is not None and expected is not None:
                    equal=Decimal(a)==Decimal(expected)
                else:equal=a==expected
                field_correct+=int(equal)
        except Exception as exc:
            outcome='failure';error=type(exc).__name__
            field_count=len(case['expected'])
        elapsed=time.perf_counter()-started
        correct+=field_correct;slots+=field_count
        rows.append({'file':case['file'],'expected_outcome':case['expected_outcome'],'actual_outcome':outcome,'seconds':round(elapsed,4),'fields_correct':field_correct,'fields_total':field_count,'error':error})
        print(case['file'],outcome,f'{elapsed:.3f}s',f'{field_correct}/{field_count}',flush=True)
    successes=sum(r['actual_outcome']=='success' for r in rows)
    valid=[r for r in rows if r['expected_outcome']=='success']
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'extractor':settings.extractor,'dataset':'15 synthetic labeled files; one shared invoice template, format variants, missing fields, wrong total, two corrupt files. Not representative of real-world accuracy.','scope':'First invoice, eight header fields; does not score line items or second-sheet invoice. Timing includes cold OCR startup; excludes embeddings, network, uploads, queue waits.','documents':len(rows),'field_accuracy':correct/slots,'correct_fields':correct,'total_fields':slots,'success_rate_all_inputs':successes/len(rows),'failure_rate_all_inputs':1-successes/len(rows),'success_rate_valid_inputs':sum(r['actual_outcome']=='success' for r in valid)/len(valid),'expected_outcome_accuracy':sum(r['actual_outcome']==r['expected_outcome'] for r in rows)/len(rows),'mean_seconds':statistics.mean(r['seconds'] for r in rows),'median_seconds':statistics.median(r['seconds'] for r in rows),'total_seconds':sum(r['seconds'] for r in rows),'results':rows}
    out=Path(__file__).resolve().parents[1]/'reports';out.mkdir(exist_ok=True)
    (out/'evaluation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report

if __name__=='__main__':evaluate()
