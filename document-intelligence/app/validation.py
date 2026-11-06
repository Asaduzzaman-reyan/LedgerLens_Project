from datetime import date
from decimal import Decimal
from .models import FIELDS, Invoice

def validate(invoices, duplicate=False):
    issues = []
    if not invoices:
        issues.append({'invoice':None,'field':'document','code':'no_invoices','message':'No invoice records extracted; source review required'})
    def add(index,field,code,message):
        issues.append({'invoice':index,'field':field,'code':code,'message':message})
    for index,inv in enumerate(invoices):
        for field in FIELDS:
            value = getattr(inv,field)
            if value is None or value == '':
                add(index,field,'missing','Required value is missing or unresolved')
        for field in inv.uncertain_fields:
            add(index,field,'uncertain','Extraction requires source verification')
        if inv.method == 'rules':
            add(index,'extraction','rules_review','Rule-based demo extraction requires human verification')
        if inv.invoice_date:
            try:
                date.fromisoformat(inv.invoice_date)
            except ValueError:
                add(index,'invoice_date','date_format','Review date; expected unambiguous YYYY-MM-DD')
        if inv.currency and (len(inv.currency)!=3 or not inv.currency.isalpha() or inv.currency!=inv.currency.upper()):
            add(index,'currency','currency_format','Expected explicit uppercase three-letter currency code')
        tolerance = Decimal('1') if inv.currency in {'JPY','KRW','VND'} else Decimal('0.001') if inv.currency in {'BHD','KWD','OMR'} else Decimal('0.01')
        for field in ('subtotal','tax','total'):
            value = getattr(inv,field)
            if value is not None and value<0:
                add(index,field,'negative','Negative value requires credit-note review')
        if all(getattr(inv,k) is not None for k in ('subtotal','tax','total')):
            if abs(inv.subtotal+inv.tax-inv.total)>tolerance:
                add(index,'total','total_mismatch','Subtotal + tax does not equal total')
        if not inv.line_items:
            add(index,'line_items','missing_items','No line items extracted')
        for j,item in enumerate(inv.line_items):
            for key in ('description','quantity','unit_price','amount'):
                if getattr(item,key) is None:
                    add(index,f'line_items.{j}.{key}','missing','Line-item value is missing')
            if any(getattr(item,k) is not None and getattr(item,k)<0 for k in ('quantity','unit_price','amount')):
                add(index,f'line_items.{j}','negative','Negative line value requires review')
            if all(getattr(item,k) is not None for k in ('quantity','unit_price','amount')) and abs(item.quantity*item.unit_price-item.amount)>tolerance:
                add(index,f'line_items.{j}','line_mismatch','Quantity x unit price does not equal line amount')
        if inv.line_items and inv.subtotal is not None and all(x.amount is not None for x in inv.line_items):
            if abs(sum(x.amount for x in inv.line_items)-inv.subtotal)>tolerance:
                add(index,'subtotal','items_mismatch','Sum of line amounts does not equal subtotal')
    if duplicate:
        add(None,'document','duplicate_file','An identical file was uploaded previously')
    return issues

def cross_compare(documents):
    groups = {}
    unmatched = []
    for doc in documents:
        for index,raw in enumerate(doc.get('result') or []):
            inv = Invoice.model_validate(raw)
            if not inv.invoice_number or not inv.supplier_name:
                unmatched.append({'document_id':doc['id'],'invoice':index,'reason':'Missing invoice number or supplier'})
                continue
            key = (inv.invoice_number.strip().casefold(),inv.supplier_name.strip().casefold())
            groups.setdefault(key,[]).append((doc['id'],index,inv))
    comparisons = []
    for key, group in groups.items():
        if len({x[0] for x in group})<2:
            unmatched.extend({'document_id':x[0],'invoice':x[1],'reason':'No matching invoice in selected documents'} for x in group)
            continue
        differences = []
        for field in FIELDS+['line_items']:
            values = [x[2].model_dump(mode='json')[field] for x in group]
            typed = [getattr(x[2],field) for x in group]
            if any(v is None or v==[] for v in typed) or any(v!=typed[0] for v in typed[1:]):
                differences.append({'field':field,'values':[{'document_id':x[0],'value':v} for x,v in zip(group,values)]})
        comparisons.append({'invoice_number':group[0][2].invoice_number,'supplier':group[0][2].supplier_name,'matches':not differences,'differences':differences})
    return {'comparisons':comparisons,'unmatched':unmatched}
