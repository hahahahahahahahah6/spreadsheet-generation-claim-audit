import ast
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from spreadsheet_generation_claim_audit.audit import audit, evidence, paragraphs, matches, normalize
from spreadsheet_generation_claim_audit import phrases
from spreadsheet_generation_claim_audit.__main__ import main

EXPECTED_YES = ('spreadsheet generation', 'generate spreadsheet', 'generates spreadsheet', 'generating spreadsheet', 'generate spreadsheets', 'generates spreadsheets', 'generating spreadsheets', 'create spreadsheet', 'creates spreadsheet', 'creating spreadsheet', 'create spreadsheets', 'creates spreadsheets', 'creating spreadsheets', 'export spreadsheet', 'exports spreadsheet', 'exporting spreadsheet', 'export to spreadsheet', 'exports to spreadsheet', 'exporting to spreadsheet', 'export as spreadsheet', 'exports as spreadsheet', 'exporting as spreadsheet', 'spreadsheet export', 'spreadsheet exports', 'spreadsheet exporter', 'spreadsheet report generation', 'generate spreadsheet report', 'generates spreadsheet report', 'generating spreadsheet report', 'generate spreadsheet reports', 'create spreadsheet report', 'creates spreadsheet report', 'write spreadsheet', 'writes spreadsheet', 'writing spreadsheet', 'save as spreadsheet', 'saves as spreadsheet', 'save to spreadsheet', 'saves to spreadsheet', 'spreadsheet writer', 'spreadsheet writing', 'build spreadsheet', 'builds spreadsheet', 'building spreadsheet', 'generate excel', 'generates excel', 'generating excel', 'create excel', 'creates excel', 'creating excel')
EXPECTED_NO = ('no spreadsheet generation', 'does not generate spreadsheet', 'does not generate spreadsheets', 'does not support spreadsheet generation', 'without spreadsheet generation', 'no spreadsheet export', 'does not export spreadsheet', 'does not export to spreadsheet', 'does not create spreadsheet', 'does not create spreadsheets', 'no spreadsheet writer', 'does not write spreadsheet', 'does not save as spreadsheet', 'no spreadsheet report generation', 'does not generate spreadsheet reports', 'does not build spreadsheet', 'does not generate excel', 'does not create excel', 'spreadsheet generation not supported', 'no spreadsheet generation support', 'without spreadsheet export', 'does not support spreadsheet export', 'no spreadsheet exporter', 'does not generate spreadsheet report')
EXPECTED_GENERIC = ('generate_spreadsheet', 'generate_spreadsheets', 'create_spreadsheet', 'create_spreadsheets', 'export_spreadsheet', 'export_to_spreadsheet', 'export_as_spreadsheet', 'write_spreadsheet', 'save_spreadsheet', 'save_as_spreadsheet', 'build_spreadsheet', 'render_spreadsheet', 'make_spreadsheet', 'generate_excel', 'create_excel', 'export_excel', 'export_to_excel', 'write_excel', 'save_excel', 'build_excel', 'generate_xlsx', 'create_xlsx', 'export_xlsx', 'generate_workbook')


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def cli(self, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            try:
                code = main(list(args))
            except SystemExit as error:
                code = error.code
        return code, output.getvalue()

    def test_phrase_oracle(self):
        parsed = ast.parse(Path(phrases.__file__).read_text())
        values = {n.targets[0].id: ast.literal_eval(n.value) for n in parsed.body if isinstance(n, ast.Assign)}
        for key, expected in [('SPREADSHEETGENERATION', EXPECTED_YES), ('NOSPREADSHEETGENERATION', EXPECTED_NO), ('GENERIC_NAMES', EXPECTED_GENERIC)]:
            self.assertEqual(values[key], expected)
            self.assertEqual(len(values[key]), len(set(values[key])))
        self.assertEqual(len(EXPECTED_YES), 50)
        self.assertEqual(len(EXPECTED_NO), 24)
        self.assertEqual(len(EXPECTED_GENERIC), 24)

    def test_good(self):
        self.put('README.md', 'We generate spreadsheets.')
        self.put('app.py', 'from openpyxl import Workbook\nw = Workbook()\nw.save("out.xlsx")')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')

    def test_bad(self):
        self.put('README.md', 'generate spreadsheet')
        code, output = self.cli('audit', str(self.root), '--json')
        self.assertEqual(code, 2)
        result = json.loads(output)
        self.assertEqual(result['verdict'], 'FAIL')
        finding = result['findings'][0]
        self.assertEqual(finding['rule'], 'documented-spreadsheet-generation-claim-false')
        self.assertEqual(finding['severity'], 'HIGH')
        self.assertTrue(finding['message'])

    def test_test_only(self):
        self.put('README.md', 'generate spreadsheet')
        self.put('tests/app.py', 'x.generate_spreadsheet()')
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'MEDIUM')
        self.assertEqual(self.cli('audit', str(self.root))[0], 0)
        self.assertEqual(self.cli('audit', str(self.root), '--fail-on', 'medium')[0], 2)

    def test_denial(self):
        self.put('README.md', 'does not generate spreadsheet')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')
        self.put('app.py', 'x.generate_spreadsheet()')
        result = audit(self.root)
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['findings'][0]['rule'], 'documented-no-spreadsheet-generation-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertEqual(self.cli('audit', str(self.root))[0], 2)

    def test_no_claim(self):
        self.put('README.md', 'Ordinary utility')
        self.put('app.py', 'x.generate_spreadsheet()')
        self.assertEqual(audit(self.root)['findings'], [])

    def test_fences_inline_and_paragraphs(self):
        self.put('README.md', '   ```text\ngenerate spreadsheet\n   ```\n\n~~~\ncreate excel\n~~~')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')
        self.put('README.md', '`generate spreadsheet`')
        self.assertEqual(audit(self.root)['verdict'], 'FAIL')
        self.put('README.md', 'generate\n\nspreadsheet')
        self.assertEqual(audit(self.root)['verdict'], 'PASS')
        self.assertEqual(paragraphs('````\ngenerate spreadsheet\n```\ncreate excel\n````'), [])

    def test_normalization_boundaries(self):
        self.assertEqual(normalize("DOESN'T generate-spreadsheet"), 'does not generate spreadsheet')
        self.assertFalse(matches('regenerate spreadsheetsx', EXPECTED_YES))
        self.put('README.md', "doesn't generate-spreadsheet")
        self.assertEqual(audit(self.root)['claims'], [])
        self.assertEqual(matches('generate spreadsheet report', EXPECTED_YES)[0].group(), 'generate spreadsheet report')

    def test_split_modules(self):
        self.put('README.md', 'generate spreadsheet')
        self.put('a.py', 'import openpyxl\nw = openpyxl.Workbook()')
        self.put('b.py', 'w.save("out.xlsx")')
        self.assertEqual(audit(self.root)['verdict'], 'FAIL')

    def test_docs_and_excluded_paths(self):
        self.put('nested/docs/claims.md', 'generate spreadsheet')
        for folder in ['fixtures', 'docs', 'examples']:
            self.put(folder + '/app.py', 'x.generate_spreadsheet()')
        self.put('other.md', 'does not generate spreadsheet')
        self.assertEqual(audit(self.root)['production_evidence'], [])
        self.assertEqual(audit(self.root)['denials'], [])
        self.assertEqual(audit(self.root)['verdict'], 'FAIL')

    def test_test_filename_patterns(self):
        for path in ['test_app.py', 'app_test.py', 'nested/tests/module.py']:
            self.put(path, 'x.generate_spreadsheet()')
        result = audit(self.root)
        self.assertEqual(len(result['test_evidence']), 3)
        self.assertEqual(result['production_evidence'], [])

    def test_symlinks(self):
        self.put('fixtures/real.py', 'x.generate_spreadsheet()')
        self.put('fixtures/README.md', 'generate spreadsheet')
        (self.root/'app.py').symlink_to(self.root/'fixtures/real.py')
        (self.root/'README.md').symlink_to(self.root/'fixtures/README.md')
        (self.root/'linked').symlink_to(self.root/'fixtures', target_is_directory=True)
        self.assertEqual(audit(self.root)['production_evidence'], [])
        self.assertEqual(audit(self.root)['claims'], [])

    def test_ignore(self):
        self.put('README.md', 'generate spreadsheet')
        self.put('vendor/app.py', 'x.generate_spreadsheet()')
        self.assertEqual(audit(self.root, ['vendor'])['verdict'], 'FAIL')
        self.assertEqual(self.cli('audit', str(self.root), '--ignore', 'vendor', '--ignore', 'README')[0], 0)

    def test_usage_errors_and_version(self):
        for args in [[], ['wrong'], ['audit', '--fail-on', 'HIGH'], ['audit', '--ignore', 'one', 'two', 'three'], ['audit', str(self.root/'missing')]]:
            self.assertEqual(self.cli(*args)[0], 1)
        self.assertEqual(self.cli('--version'), (0, '0.1.0\n'))
        self.assertEqual(subprocess.run([sys.executable, '-m', 'spreadsheet_generation_claim_audit', '--version'], capture_output=True, text=True).stdout, '0.1.0\n')

    def test_readme_self_audit(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(audit(root)['findings'], [])
        for paragraph in paragraphs((root/'README.md').read_text()):
            self.assertFalse(matches(paragraph, EXPECTED_YES + EXPECTED_NO))


def add_case(name, source, expected):
    def test(self):
        self.assertEqual(evidence(source), expected, source)
    setattr(AuditTests, 'test_' + name, test)

for index, phrase in enumerate(EXPECTED_YES):
    def positive(self, phrase=phrase):
        self.put('README.md', phrase)
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'HIGH')
    setattr(AuditTests, 'test_positive_phrase_%02d' % index, positive)
for index, phrase in enumerate(EXPECTED_NO):
    def negative(self, phrase=phrase):
        self.put('README.md', phrase)
        result = audit(self.root)
        self.assertEqual(result['claims'], [])
        self.assertEqual(result['verdict'], 'PASS')
        self.put('app.py', 'x.generate_spreadsheet()')
        self.assertEqual(len(audit(self.root)['findings']), 1)
    setattr(AuditTests, 'test_negative_phrase_%02d' % index, negative)
for name in EXPECTED_GENERIC:
    add_case('generic_attr_' + name, 'obj.' + name + '()', True)
    add_case('generic_import_' + name, 'from utility import ' + name + ' as call\ncall()', True)
    add_case('generic_bare_' + name, name + '()', False)
    add_case('generic_shadow_' + name, 'def ' + name + '(): pass\nobj.' + name + '()', False)

ROUTES = [('openpyxl', 'Workbook', 'save'), ('xlwt', 'Workbook', 'save'), ('pyexcelerate', 'Workbook', 'save'), ('xlsxwriter', 'Workbook', 'close'), ('odf.opendocument', 'OpenDocumentSpreadsheet', 'save'), ('pandas', 'DataFrame', 'to_excel')]
for library, constructor, method in ROUTES:
    key = library.replace('.', '_')
    forms = [
        'from {lib} import {ctor}\nw = {ctor}()',
        'from {lib} import {ctor} as C\nw = C()',
        'import {lib} as lib\nw = lib.{ctor}()',
        'import {lib}\nw = {lib}.{ctor}()',
    ]
    for i, form in enumerate(forms):
        source = form.format(lib=library, ctor=constructor)
        add_case(key + '_form_' + str(i), source + '\nw.' + method + '()', True)
        add_case(key + '_lone_' + str(i), source, False)
        wrong = 'save' if method == 'close' else 'close'
        add_case(key + '_wrong_write_' + str(i), source + '\nw.' + wrong + '()', False)
    for binding in ['lib = fake', 'lib: object = fake', 'with ctx() as lib: pass', 'async def f():\n async with ctx() as lib: pass']:
        add_case(key + '_binding_' + str(len(AuditTests.__dict__)), 'import ' + library + ' as lib\n' + binding + '\nlib.' + constructor + '()\nw.' + method + '()', False)
    add_case(key + '_local_def', 'from ' + library + ' import ' + constructor + '\nclass ' + constructor + ': pass\n' + constructor + '()\nw.' + method + '()', False)
    add_case(key + '_module_scoped_write', 'import ' + library + ' as lib\nlib.' + constructor + '()\ndef elsewhere():\n other.' + method + '()', True)

NOT_EVIDENCE = [
'import openpyxl', 'import xlwt', 'import pyexcelerate', 'import xlsxwriter', 'import odf', 'import pandas', 'import csv',
'import openpyxl\nopenpyxl.load_workbook("x.xlsx")', 'import xlrd\nxlrd.open_workbook("x.xls")',
'import pandas as pd\npd.read_excel("x.xlsx")', 'import pandas as pd\npd.read_csv("x.csv")', 'import pandas as pd\npd.ExcelWriter("x.xlsx")',
'import csv\ncsv.writer(f)', 'import csv\nw=csv.writer(f)\nw.writerow([1])', 'import tablib\ntablib.Dataset().export("xlsx")',
'import gspread\ngspread.open("book")', 'import pygsheets\npygsheets.authorize()',
'import subprocess\nsubprocess.run(["libreoffice", "--convert-to", "xlsx"])',
'open("x.txt", "w").write("text")', 'Path("x.md").write_text("text")', 'Image.save("x.png")',
'from reportlab.pdfgen.canvas import Canvas\nCanvas("x.pdf").save()', 'from fpdf import FPDF\nFPDF().output("x.pdf")',
'from weasyprint import HTML\nHTML("x").write_pdf("x.pdf")', 'from pypdf import PdfWriter\nPdfWriter().write("x.pdf")',
'"spreadsheet xlsx Excel"', '# generate spreadsheet', 'obj.generate_spreadsheet', 'def broken(',
'mindee.parse(InvoiceV4, f)', 'azure.begin_analyze_document("prebuilt-layout", f)', 'veryfi.Client()',
'documentai.process_document(request)', 'textract.analyze_document(Document=data)', 'eden.universal_ai(model="anything")',
'LlamaParse().load_data(f)', 'nanonets.OCR(model_id="opaque")', 'docsumo.upload(f)', 'abbyy.run(skill="opaque")',
'rossum.upload(queue="opaque")', 'klippa.parse(f)', 'parseur.upload(f)', 'extend.run(workflow="opaque")',
'from tools import generate_spreadsheet\ndef generate_spreadsheet(): pass\ngenerate_spreadsheet()',
'from tools import generate_spreadsheet as g\ng = other\ng()',
'import openpyxl as lib\nclass A:\n def Workbook(self): pass\nlib.Workbook()\nw.save()',
]
for index, source in enumerate(NOT_EVIDENCE):
    add_case('not_evidence_%02d' % index, source, False)

add_case('attribute_assignment_keeps_import', 'import openpyxl as lib\nlib.option = True\nlib.Workbook()\nw.save()', True)
add_case('tuple_binding_shadows', 'import openpyxl as lib\nlib, other = values\nlib.Workbook()\nw.save()', False)
add_case('odf_from_module', 'from odf import opendocument as od\nod.OpenDocumentSpreadsheet()\nx.save()', True)
add_case('invalid_from_library_path', 'from openpyxl.unrelated import Workbook\nWorkbook()\nx.save()', False)

if __name__ == '__main__':
    unittest.main()
