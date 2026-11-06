"""Synthetic, labeled test data. No private or customer documents."""
import csv
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from reportlab.pdfgen import canvas
from openpyxl import Workbook
import xlwt

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT/'fixtures'
BASE = {'invoice_number':'INV-1042','invoice_date':'2026-10-15','supplier_name':'Northstar Office Supply','customer_name':'Acme Studio','subtotal':'250.00','tax':'25.00','total':'275.00','currency':'USD'}
LABELS = {'invoice_number':'Invoice number','invoice_date':'Invoice date','supplier_name':'Supplier','customer_name':'Customer','subtotal':'Subtotal','tax':'Tax','total':'Total','currency':'Currency'}

def lines(values):
    return ['INVOICE']+[f'{LABELS[k]}: {v}' for k,v in values.items()]+['Item: Desk lamp | 2 | 50.00 | 100.00','Item: Office chair | 1 | 150.00 | 150.00']

def pdf(path, values, pages=1):
    c=canvas.Canvas(str(path))
    for n in range(pages):
        c.setFont('Helvetica',14)
        for j,line in enumerate(lines(values)):
            c.drawString(50,790-j*30,line)
        c.showPage()
    c.save()

def generate():
    FIXTURES.mkdir(exist_ok=True)
    labels=[]
    def record(name,values=BASE,status='success'):
        labels.append({'file':name,'expected':values,'expected_outcome':status})
    pdf(FIXTURES/'invoice.pdf',BASE);record('invoice.pdf')
    alt=BASE|{'invoice_number':'INV-1043','supplier_name':'Harbor Technology','subtotal':'250.00','tax':'25.00','total':'290.00'}
    pdf(FIXTURES/'incorrect-total.pdf',alt);record('incorrect-total.pdf',alt)
    missing={k:v for k,v in BASE.items() if k not in {'tax','customer_name'}}
    missing['invoice_number']='INV-1044'
    pdf(FIXTURES/'missing-fields.pdf',missing);record('missing-fields.pdf',missing|{'tax':None,'customer_name':None})
    # Multi-page continuation, without repeating line items / totals.
    c=canvas.Canvas(str(FIXTURES/'multipage.pdf'))
    for page_lines in [lines(BASE)[:6],['Invoice number: INV-1042','Supplier: Northstar Office Supply']+lines(BASE)[6:]]:
        c.setFont('Helvetica',14)
        for j,line in enumerate(page_lines):c.drawString(50,790-j*30,line)
        c.showPage()
    c.save();record('multipage.pdf')
    font_path=Path('C:/Windows/Fonts/arial.ttf')
    if not font_path.exists():font_path=Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    font=ImageFont.truetype(str(font_path),32) if font_path.exists() else ImageFont.load_default(size=32)
    im=Image.new('RGB',(1500,1000),'white');d=ImageDraw.Draw(im)
    for j,line in enumerate(lines(BASE)):d.text((70,50+j*70),line,font=font,fill='black')
    for name in ['invoice.png','invoice.jpg','invoice.tiff']:
        im.save(FIXTURES/name);record(name)
    im.save(FIXTURES/'scanned.pdf','PDF',resolution=144);record('scanned.pdf')
    im.filter(ImageFilter.GaussianBlur(1.3)).resize((1050,700)).save(FIXTURES/'poor-scan.png');record('poor-scan.png')
    im.save(FIXTURES/'multipage.tiff',save_all=True,append_images=[im]);record('multipage.tiff')
    headers=list(BASE)+['description','quantity','unit_price','amount']
    rows=[list(BASE.values())+['Desk lamp','2','50.00','100.00'],list(BASE.values())+['Office chair','1','150.00','150.00']]
    with (FIXTURES/'ledger.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(headers);w.writerows(rows)
    record('ledger.csv')
    wb=Workbook();ws=wb.active;ws.title='Invoices';ws.append(headers)
    for row in rows:ws.append(row)
    notes=wb.create_sheet('Second invoice');notes.append(headers)
    for row in rows:notes.append(['INV-2042']+row[1:])
    wb.save(FIXTURES/'ledger.xlsx');record('ledger.xlsx')
    legacy=xlwt.Workbook();sheet=legacy.add_sheet('Invoices')
    for i,row in enumerate([headers]+rows):
        for j,value in enumerate(row):sheet.write(i,j,value)
    legacy.save(str(FIXTURES/'ledger.xls'));record('ledger.xls')
    (FIXTURES/'corrupt.pdf').write_bytes(b'%PDF-1.4\ninvalid file');record('corrupt.pdf',{},'failure')
    (FIXTURES/'corrupt.xlsx').write_bytes(b'not a zip archive');record('corrupt.xlsx',{},'failure')
    (FIXTURES/'labels.json').write_text(json.dumps(labels,indent=2),encoding='utf-8')
    print(f'Generated {len(labels)} labeled fixtures in {FIXTURES}')

if __name__=='__main__':generate()
