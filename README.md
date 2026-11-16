# Documentation claim auditor

An offline static auditor comparing documentation promises with listed source patterns. It reads root README.md and Markdown files under any docs path component. Source is parsed with the standard library and never executed. Audits use no network, telemetry, or writes.

## Usage

```sh
python3 -m pip install .
spreadsheet-generation-claim-audit audit . --json
python3 -m spreadsheet_generation_claim_audit audit . --verbose
spreadsheet-generation-claim-audit audit . --fail-on medium --ignore vendor --ignore generated
spreadsheet-generation-claim-audit --version
```

The audit subcommand defaults to the current directory. Each ignore option accepts one relative path prefix. The default threshold is high; medium also fails on test-only findings. Exit codes are 0 for PASS, 2 for findings meeting the threshold, and 1 for usage or I/O errors. A PASS can contain a medium finding. JSON contains verdict, findings (rule, severity, message, locations), production_evidence, test_evidence, claims and denials. Verbose output includes claim and evidence paths.

## Matching

Blank lines delimit paragraphs. Backtick and tilde fences with up to three leading spaces are excluded; inline code counts. Text is lowercased, contractions expanded, hyphens replaced with spaces, and whitespace collapsed. Exact phrases match at word boundaries, longest first with alphabetical ties. Denial spans are removed before positive matching. There is at most one finding per claim family.

Only listed calls within a single module count. Import aliases resolve; local function, method and class definitions shadow route names. Assignments, annotated assignments and context-manager bindings shadow imported names. Syntax-invalid files and symlinks provide no evidence. Files under fixtures, docs and examples are excluded; tests are tracked separately. A positive statement without source fails; a denial without source passes.

```text
documented-spreadsheet-generation-claim-false HIGH (MEDIUM when evidence is test-only)
documented-no-spreadsheet-generation-claim-false HIGH
```

## Evidence and vocabulary

The checked operation produces workbook files from code or data, including sheets, rows, cells and formulas. It differs from reading existing workbooks, plain text output and cloud sheet updates. The precise vocabulary and accepted calls follow.

```text
spreadsheet generation
generate spreadsheet
generates spreadsheet
generating spreadsheet
generate spreadsheets
generates spreadsheets
generating spreadsheets
create spreadsheet
creates spreadsheet
creating spreadsheet
create spreadsheets
creates spreadsheets
creating spreadsheets
export spreadsheet
exports spreadsheet
exporting spreadsheet
export to spreadsheet
exports to spreadsheet
exporting to spreadsheet
export as spreadsheet
exports as spreadsheet
exporting as spreadsheet
spreadsheet export
spreadsheet exports
spreadsheet exporter
spreadsheet report generation
generate spreadsheet report
generates spreadsheet report
generating spreadsheet report
generate spreadsheet reports
create spreadsheet report
creates spreadsheet report
write spreadsheet
writes spreadsheet
writing spreadsheet
save as spreadsheet
saves as spreadsheet
save to spreadsheet
saves to spreadsheet
spreadsheet writer
spreadsheet writing
build spreadsheet
builds spreadsheet
building spreadsheet
generate excel
generates excel
generating excel
create excel
creates excel
creating excel
no spreadsheet generation
does not generate spreadsheet
does not generate spreadsheets
does not support spreadsheet generation
without spreadsheet generation
no spreadsheet export
does not export spreadsheet
does not export to spreadsheet
does not create spreadsheet
does not create spreadsheets
no spreadsheet writer
does not write spreadsheet
does not save as spreadsheet
no spreadsheet report generation
does not generate spreadsheet reports
does not build spreadsheet
does not generate excel
does not create excel
spreadsheet generation not supported
no spreadsheet generation support
without spreadsheet export
does not support spreadsheet export
no spreadsheet exporter
does not generate spreadsheet report

Generic call names:
generate_spreadsheet, generate_spreadsheets, create_spreadsheet, create_spreadsheets, export_spreadsheet, export_to_spreadsheet, export_as_spreadsheet, write_spreadsheet, save_spreadsheet, save_as_spreadsheet, build_spreadsheet, render_spreadsheet, make_spreadsheet, generate_excel, create_excel, export_excel, export_to_excel, write_excel, save_excel, build_excel, generate_xlsx, create_xlsx, export_xlsx, generate_workbook

openpyxl / xlwt / pyexcelerate: Workbook construction + .save()
xlsxwriter: Workbook construction + .close()
odf.opendocument: OpenDocumentSpreadsheet() + .save()
pandas: DataFrame construction + .to_excel()

Each pair must be in one module. The write call may be on any object;
object identity and execution order are not checked. Imports and aliases
resolve; generic Attribute calls accept any base. Bare generic Names
require an import. No third-party dependency is needed by this auditor.
```

## Honest limitations

Static patterns are not semantic proof. Dead code counts. Unresolved alias chains are missed. Exact wording and the denial vocabulary limit coverage. Detailed limitations follow in a fenced block to avoid making claims about this auditor.

```text
- The bare phrases "spreadsheet generation" / "generate spreadsheet" /
  "create spreadsheet" / "export spreadsheet" are deliberately
  SPREADSHEETGENERATION phrases: in document-tool docs they almost
  always name spreadsheet generation. But "create spreadsheet" can
  also name creating an empty workbook shell with no content, and
  "export spreadsheet" can name a menu item that merely downloads an
  already-generated workbook: a doc that means download, not
  generation, is a false positive; the tool flags the claim, only
  the code decides.
- "spreadsheet report" phrases ("spreadsheet report generation",
  "generate spreadsheet report", "create spreadsheet report") are
  deliberately phrases: a doc can say "spreadsheet report" about a
  report that happens to be delivered as a spreadsheet generated
  elsewhere, with no generation code in the repo. The tool flags
  the claim; only the code decides.
- "generate excel" / "create excel" phrases are deliberately phrases:
  a doc can say "generate excel" about a tool that shells out to
  LibreOffice, which the tool deliberately does NOT detect
  (subprocess is NOT evidence). The tool flags the claim; only the
  code decides — and a subprocess-only codebase will be flagged
  HIGH, by design.
- "save as spreadsheet" / "save to spreadsheet" are deliberately
  phrases: a doc can say "save as spreadsheet" about a print
  dialog's save option in a GUI, with no spreadsheet-writing code
  in the repo. The tool flags the claim; only the code decides.
- "spreadsheet writer" / "spreadsheet writing" are deliberately
  phrases: "spreadsheet writer" can also name a class that only
  wraps a spreadsheet reader, or a job title in prose. The tool
  flags the claim; only the code decides.
- "build spreadsheet" / "building spreadsheet" are deliberately
  phrases: a doc can say "build spreadsheet" about a build step
  that assembles a workbook from already-rendered sheets, or about
  building the tool itself. The tool flags the claim; only the code
  decides.
- An openpyxl / xlwt / pyexcelerate Workbook construction with no
  .save() in the module is NOT detected: constructing a workbook
  without saving writes no file. Say so in the README.
- An XlsxWriter Workbook construction with no .close() in the
  module is NOT detected. Say so in the README.
- An OpenDocumentSpreadsheet call with no .save() in the module is
  NOT detected. Say so in the README.
- A DataFrame construction with no .to_excel() in the module is NOT
  detected. Say so in the README.
- An xlsxwriter.Workbook construction with only a .save() call (no
  .close()) is NOT detected: XlsxWriter workbooks have no save
  method; the write is close(). Say so in the README.
- An openpyxl / xlwt / pyexcelerate Workbook construction with only
  a .close() call (no .save()) is NOT detected: those workbooks
  write via save(), not close(). Say so in the README.
- openpyxl load_workbook, xlrd reads, pandas read_excel / read_csv
  are NOT detected: reading a spreadsheet is not generating one.
  Say so in the README.
- A pandas ExcelWriter construction with no .to_excel() call in the
  module is NOT detected: the write happens via df.to_excel(writer).
  Say so in the README.
- csv module writer / writerow calls are NOT detected: CSV is plain
  text, not a workbook. Say so in the README.
- tablib Dataset.export calls are NOT detected: they are not a
  listed route this round. Say so in the README.
- gspread / pygsheets calls are NOT detected: they write to cloud
  sheets, not files. Say so in the README.
- LibreOffice / UNO subprocess calls are NOT detected: shelling out
  to an external binary is NOT evidence by design. Say so in the
  README.
- Saving .txt / .html / .md / image files is NOT detected: writing
  a non-spreadsheet file is not generating a spreadsheet. Say so in
  the README.
- reportlab / fpdf / WeasyPrint / pypdf PDF writes are NOT detected:
  writing a PDF is not generating a spreadsheet. Say so in the
  README.
- Mindee parse with ANY product is NOT detected: mindee extracts
  from documents; it never writes spreadsheets. Say so in the
  README.
- Azure begin_analyze_document with ANY model id is NOT detected:
  Document Intelligence reads documents; it has no spreadsheet
  generation operation. Say so in the README.
- Veryfi calls of ANY kind are NOT detected: veryfi extracts fields
  from documents; it has no spreadsheet generation method. Say so
  in the README.
- Google Document AI process_document / batch_process_documents
  with ANY processor is NOT detected: Document AI has no
  spreadsheet generation processor. Say so in the README.
- Eden AI universal-ai calls with ANY model id are NOT detected:
  Eden AI documents no spreadsheet generation model. Say so in the
  README.
- Textract calls of ANY kind are NOT detected: Textract reads
  documents; it has no spreadsheet generation operation. Say so in
  the README.
- LlamaParse calls are NOT detected: its parsing API reads
  documents; it has no spreadsheet generation operation. Say so in
  the README.
- Nanonets / Docsumo / ABBYY Vantage / Rossum / Klippa / Parseur /
  Extend calls are NOT detected: opaque model / skill / queue /
  template / workflow IDs, or a generic upload endpoint with the
  document type configured outside the call — all extraction-side,
  no fixed fingerprint. Say so in the README.
- A hand-rolled spreadsheet writer built on raw OOXML / ZIP XML
  assembly (writing .xlsx bytes by hand, no listed call) is NOT
  detected: the tool requires a listed call. Say so in the README.
- PDF generation claims ("generate pdf", "pdf generation"), invoice
  extraction claims ("extract invoices", "invoice extraction"),
  receipt extraction claims ("extract receipts", "receipt
  extraction"), ID document extraction claims ("extract passports",
  "passport extraction"), bank check extraction claims ("extract
  bank checks", "check extraction"), bank statement extraction
  claims ("extract bank statements", "statement extraction"), tax
  form extraction claims ("extract tax forms", "extract w2 forms",
  "1099 extraction"), pay stub extraction claims ("extract pay
  stubs", "payslip extraction"), health insurance card extraction
  claims ("extract health insurance cards", "health insurance card
  extraction"), business card extraction claims ("extract business
  cards", "business card extraction"), credit card extraction
  claims ("extract credit cards", "credit card extraction"),
  contract extraction claims ("extract contracts", "contract
  extraction"), mortgage extraction claims ("extract mortgages",
  "mortgage extraction"), resume extraction claims ("extract
  resumes", "resume extraction"), bill of lading extraction claims
  ("extract bills of lading", "bill of lading extraction"), delivery
  note extraction claims ("extract delivery notes", "delivery note
  extraction"), carte grise extraction claims ("extract carte
  grises", "carte grise extraction"), energy bill extraction claims
  ("extract energy bills", "energy bill extraction"), marriage
  certificate extraction claims ("extract marriage certificates",
  "marriage certificate extraction"), bank account details
  extraction claims ("extract bank account details", "bank account
  details extraction"), nutrition facts label extraction claims
  ("extract nutrition facts labels", "nutrition facts label
  extraction"), material certificate extraction claims ("extract
  material certificates", "material certificate extraction"), US
  mail extraction claims ("extract us mail", "us mail extraction"),
  invoice splitter claims ("split invoices", "invoice splitting"),
  multi-receipts detection claims ("detect multiple receipts",
  "multi receipt detection"), French health card extraction claims
  ("extract carte vitales", "french health card extraction"),
  Indian passport extraction claims ("extract indian passports",
  "indian passport extraction"), driver license extraction claims
  ("extract driver licenses", "driver license extraction"),
  vaccination card extraction claims ("extract vaccination cards",
  "vaccination card extraction"), document cropping claims ("crop
  documents", "document cropping"), and PDF generation claims
  ("generate pdf", "pdf generation") are NOT in the phrase lists:
  this family covers spreadsheet generation only. Say so in the
  README.
- As with every family: static pattern matching, not semantic
  judgement; dead code counts; alias chains the tracer cannot follow
  are missed; exact phrases only, not semantics; denial handling
  depends on the denial phrase list; each route must sit in a single
  module.

```

## Development

```sh
python3 -m unittest discover
python3 -m build
```

Requires version 3.9 or later of the interpreter. Distributed under the MIT license.
