import pytest
from app.processing import parse, Unit
from app.extraction import extract_rules,merge_invoices
from app.models import Invoice

@pytest.mark.parametrize('name,count',[('invoice.pdf',1),('multipage.pdf',2),('ledger.csv',1),('ledger.xls',1),('ledger.xlsx',2)])
def test_digital_and_spreadsheets(fixtures,name,count):
    units=list(parse(fixtures/name))
    assert len(units)==count
    invoices=merge_invoices([inv for unit in units for inv in extract_rules(unit)])
    assert invoices[0].invoice_number=='INV-1042'
    assert str(invoices[0].total)=='275.00'
    assert len(invoices[0].line_items)==2

@pytest.mark.parametrize('name',['invoice.png','invoice.jpg','invoice.tiff','scanned.pdf','poor-scan.png'])
def test_real_ocr(fixtures,name):
    unit=next(parse(fixtures/name))
    assert unit.method=='ocr'
    assert '1042' in unit.text
    assert unit.confidence>0.5

def test_multipage_tiff(fixtures):
    assert len(list(parse(fixtures/'multipage.tiff')))==2

@pytest.mark.parametrize('name',['corrupt.pdf','corrupt.xlsx'])
def test_corrupt(fixtures,name):
    with pytest.raises(Exception):list(parse(fixtures/name))

def test_limits(fixtures):
    with pytest.raises(ValueError,match='limit'):list(parse(fixtures/'multipage.pdf',max_units=1))

def test_missing_and_ambiguous_values():
    inv=extract_rules(Unit('p1','Invoice number: X\nTotal: 1.234,56\nCurrency: $','digital'))[0]
    assert inv.total is None and inv.supplier_name is None
    assert 'total' in inv.uncertain_fields

def test_conflicts_within_document():
    a=Invoice(invoice_number='A',supplier_name='Vendor',total='10')
    b=Invoice(invoice_number='A',supplier_name='Vendor',total='20')
    inv=merge_invoices([a,b])[0]
    assert inv.total is None and 'total' in inv.uncertain_fields

def test_table_preserves_identical_purchased_lines():
    text='invoice_number,supplier,total,description,quantity,unit_price,amount\nA,V,20,Chair,1,10,10\nA,V,20,Chair,1,10,10'
    assert len(merge_invoices(extract_rules(Unit('CSV',text,'table')))[0].line_items)==2
