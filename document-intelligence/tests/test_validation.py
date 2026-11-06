from app.models import Invoice,Item
from app.validation import validate,cross_compare
import pytest

def complete(**updates):
    return Invoice(invoice_number='A',invoice_date='2026-01-15',supplier_name='Vendor',customer_name='Buyer',subtotal='100',tax='10',total='110',currency='USD',line_items=[Item(description='Chair',quantity='2',unit_price='50',amount='100')],method='manual').model_copy(update=updates)

def test_valid_and_decimal_precision():assert validate(complete_list:= [complete()])==[]

def test_missing():assert any(x['code']=='missing' for x in validate([Invoice()]))

def test_empty_extraction_requires_review():assert validate([])[0]['code']=='no_invoices'

def test_arithmetic():
    from decimal import Decimal
    inv=complete(total=Decimal('120'))
    assert any(x['code']=='total_mismatch' for x in validate([inv]))
    inv.line_items[0].amount=Decimal('90')
    codes={x['code'] for x in validate([inv])}
    assert {'line_mismatch','items_mismatch'}<=codes

def test_duplicate_flag():assert any(e['code']=='duplicate_file' for e in validate([complete()],True))

def test_nonfinite_rejected():
    with pytest.raises(ValueError):Invoice(total='NaN')

def test_cross_verification():
    a=complete().model_dump(mode='json');b=dict(a,total='120')
    r=cross_compare([{'id':'pdf','result':[a]},{'id':'xlsx','result':[b]}])
    assert not r['comparisons'][0]['matches']
    assert r['comparisons'][0]['differences'][0]['field']=='total'

def test_no_false_match_without_identity():
    assert not cross_compare([{'id':'a','result':[Invoice().model_dump()]},{'id':'b','result':[Invoice().model_dump()]}])['comparisons']

def test_cross_compare_ignores_decimal_display_precision():
    a=complete().model_dump(mode='json');b=dict(a,total='110.00',subtotal='100.0')
    assert cross_compare([{'id':'a','result':[a]},{'id':'b','result':[b]}])['comparisons'][0]['matches']
