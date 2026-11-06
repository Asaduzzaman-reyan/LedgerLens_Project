"""Bounded page/sheet iterators. Input content is data, never instructions."""
import csv
import io
import warnings
import zipfile
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, ImageSequence

Image.MAX_IMAGE_PIXELS = 40_000_000

@dataclass
class Unit:
    source: str
    text: str
    method: str
    confidence: float | None = None

_ocr = None

def ocr_image(image):
    global _ocr
    from rapidocr_onnxruntime import RapidOCR
    if _ocr is None:
        _ocr = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
    image = ImageOps.exif_transpose(image).convert('RGB')
    if image.width * image.height > Image.MAX_IMAGE_PIXELS:
        raise ValueError('Image exceeds pixel limit')
    image.thumbnail((2400, 2400))
    if max(image.size) < 1200:
        scale = min(2, 1200 / max(image.size))
        image = image.resize((int(image.width*scale), int(image.height*scale)))
    image = ImageOps.autocontrast(image)
    result, _ = _ocr(np.asarray(image))
    if not result:
        return '', 0.0
    # Preserve each detected line. Extraction handles label/value on adjacent lines.
    return '\n'.join(r[1] for r in result), float(sum(r[2] for r in result)/len(result))

def rows_to_units(rows, source, max_rows=100000):
    """500-row chunks bound memory and preserve a repeated header for flat ledgers."""
    header, chunk = None, []
    count = 0
    for row in rows:
        count += 1
        if count > max_rows:
            raise ValueError('Sheet row limit exceeded')
        values = [str(v).strip() if v is not None else '' for v in row]
        if len(values) > 100 or any(len(v) > 20000 for v in values):
            raise ValueError('Spreadsheet cell/column limit exceeded')
        if not any(values):
            continue
        if header is None:
            header = values
        chunk.append(values)
        if len(chunk) == 500:
            yield Unit(f'{source} rows {count-len(chunk)+1}-{count}', _csv(chunk), 'table')
            chunk = [header]
    if chunk and chunk != [header]:
        yield Unit(f'{source} rows ending {count}', _csv(chunk), 'table')
    elif chunk and count == 1:
        yield Unit(source, _csv(chunk), 'table')

def _csv(rows):
    s = io.StringIO()
    csv.writer(s).writerows(rows)
    return s.getvalue()

def parse(path: Path, max_units=1500):
    ext = path.suffix.lower()
    count = 0
    for unit in _parse(path, ext):
        count += 1
        if count > max_units:
            raise ValueError('Page/sheet chunk limit exceeded')
        if len(unit.text) > 500000:
            raise ValueError('Extracted unit text limit exceeded')
        yield unit
    if count == 0:
        raise ValueError('Document has no readable pages or rows')

def _parse(path, ext):
    if ext == '.pdf':
        import pymupdf as fitz
        with fitz.open(path) as pdf:
            if pdf.needs_pass:
                raise ValueError('Password-protected PDF is not supported')
            for index in range(len(pdf)):
                page = pdf[index]
                text = page.get_text(sort=True).strip()
                if len(text) >= 30:
                    yield Unit(f'page {index+1}', text, 'digital')
                else:
                    scale = min(2.0, 2400/max(page.rect.width,page.rect.height))
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale,scale), alpha=False)
                    text, confidence = ocr_image(Image.frombytes('RGB',(pix.width,pix.height),pix.samples))
                    yield Unit(f'page {index+1}', text, 'ocr', confidence)
    elif ext in {'.png','.jpg','.jpeg','.tif','.tiff'}:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(path) as image:
                for index, frame in enumerate(ImageSequence.Iterator(image)):
                    text, confidence = ocr_image(frame.copy())
                    yield Unit(f'frame {index+1}',text,'ocr',confidence)
    elif ext == '.csv':
        with open(path,encoding='utf-8-sig',newline='') as f:
            sample = f.read(8192)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t')
            except csv.Error:
                dialect = csv.excel
            yield from rows_to_units(csv.reader(f,dialect), 'CSV')
    elif ext == '.xlsx':
        import openpyxl
        with zipfile.ZipFile(path) as archive:
            if sum(i.file_size for i in archive.infolist()) > 200_000_000:
                raise ValueError('Expanded workbook exceeds size limit')
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            for sheet in workbook:
                yield from rows_to_units(sheet.iter_rows(values_only=True), f'sheet {sheet.title}')
        finally:
            workbook.close()
    elif ext == '.xls':
        import xlrd
        workbook = xlrd.open_workbook(path, on_demand=True)
        try:
            for sheet in workbook.sheets():
                yield from rows_to_units((sheet.row_values(i) for i in range(sheet.nrows)), f'sheet {sheet.name}')
        finally:
            workbook.release_resources()
    else:
        raise ValueError('Unsupported file format')
