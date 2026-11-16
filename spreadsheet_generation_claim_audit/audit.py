"""Offline documentation and AST inspection; source is never executed."""
import ast
import os
import re
from pathlib import Path
from .phrases import SPREADSHEETGENERATION, NOSPREADSHEETGENERATION, GENERIC_NAMES


def normalize(text):
    return ' '.join(text.lower().replace('’', "'").replace("n't", ' not').replace('-', ' ').split())


def matches(text, phrases):
    pattern = r'\b(?:' + '|'.join(re.escape(p) for p in sorted(phrases, key=lambda p: (-len(p), p))) + r')\b'
    return list(re.finditer(pattern, text))


def paragraphs(text):
    lines = []
    fence = None
    for line in text.splitlines():
        opening = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if fence:
            if re.match(r'^ {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*$', line):
                fence = None
            lines.append('')
        elif opening:
            fence = opening.group(1)
            lines.append('')
        else:
            lines.append(line)
    return [normalize(p) for p in re.split(r'\n\s*\n', '\n'.join(lines)) if p.strip()]


def evidence(source):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return False
    nodes = list(ast.walk(tree))
    imports = {}
    shadows = set()
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split('.')[0]] = alias.name if alias.asname else alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            for alias in node.names:
                imports[alias.asname or alias.name] = (node.module or '') + '.' + alias.name
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            shadows.add(node.name)
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            targets = [item.optional_vars for item in node.items if item.optional_vars]
        def bound_names(target):
            if isinstance(target, ast.Name):
                return {target.id}
            if isinstance(target, (ast.Tuple, ast.List)):
                return set().union(*(bound_names(item) for item in target.elts))
            if isinstance(target, ast.Starred):
                return bound_names(target.value)
            return set()
        for target in targets:
            shadows.update(bound_names(target))
    def resolve(func):
        if isinstance(func, ast.Name):
            return imports.get(func.id, '') if func.id not in shadows else ''
        if isinstance(func, ast.Attribute):
            base = func.value
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name) and base.id not in shadows and base.id in imports:
                return imports[base.id] + '.' + func.attr
        return ''
    calls = [n.func for n in nodes if isinstance(n, ast.Call)]
    methods = {f.attr for f in calls if isinstance(f, ast.Attribute)}
    for func in calls:
        name = func.attr if isinstance(func, ast.Attribute) else (resolve(func).split('.')[-1])
        if name in GENERIC_NAMES and name not in shadows:
            return True
        resolved = resolve(func)
        leaf = resolved.split('.')[-1]
        if leaf in shadows:
            continue
        root = resolved.split('.')[0]
        is_name = isinstance(func, ast.Name)
        if leaf == 'Workbook' and (not is_name or resolved in {lib + '.Workbook' for lib in ('openpyxl', 'xlwt', 'pyexcelerate', 'xlsxwriter')}):
            if root in ('openpyxl', 'xlwt', 'pyexcelerate') and 'save' in methods:
                return True
            if root == 'xlsxwriter' and 'close' in methods:
                return True
        if leaf == 'OpenDocumentSpreadsheet' and resolved in ('odf.OpenDocumentSpreadsheet', 'odf.opendocument.OpenDocumentSpreadsheet') and (not is_name or resolved == 'odf.opendocument.OpenDocumentSpreadsheet') and 'save' in methods:
            return True
        if leaf == 'DataFrame' and root == 'pandas' and (not is_name or resolved == 'pandas.DataFrame') and 'to_excel' in methods:
            return True
    return False


def audit(repo='.', ignore=(), fail_on='high'):
    root = Path(repo)
    if not root.is_dir() or root.is_symlink():
        raise OSError('Repository must be a readable directory')
    claims, denials, production, tests = [], [], [], []
    def walk_error(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if not (Path(directory) / d).is_symlink())
        for filename in sorted(files):
            path = Path(directory) / filename
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or any(rel.startswith(prefix) for prefix in ignore):
                continue
            parts = path.relative_to(root).parts
            is_doc = rel == 'README.md' or (path.suffix == '.md' and 'docs' in parts[:-1])
            if is_doc:
                for paragraph in paragraphs(path.read_text(encoding='utf-8')):
                    negative = matches(paragraph, NOSPREADSHEETGENERATION)
                    if negative:
                        denials.append(rel)
                    remaining = list(paragraph)
                    for match in negative:
                        remaining[match.start():match.end()] = ' ' * (match.end() - match.start())
                    if matches(''.join(remaining), SPREADSHEETGENERATION):
                        claims.append(rel)
            if path.suffix == '.py' and not set(parts[:-1]) & {'fixtures', 'docs', 'examples'}:
                if evidence(path.read_text(encoding='utf-8')):
                    is_test = 'tests' in parts[:-1] or filename.startswith('test_') or filename.endswith('_test.py')
                    (tests if is_test else production).append(rel)
    findings = []
    if claims and not production:
        findings.append(dict(rule='documented-spreadsheet-generation-claim-false', severity='MEDIUM' if tests else 'HIGH', message='Evidence exists only in tests.' if tests else 'No production evidence supports the documented claim.', locations=sorted(set(claims))))
    if denials and production:
        findings.append(dict(rule='documented-no-spreadsheet-generation-claim-false', severity='HIGH', message='Production evidence contradicts the documented denial.', locations=sorted(set(denials))))
    failed = any(f['severity'] == 'HIGH' or fail_on == 'medium' for f in findings)
    return dict(verdict='FAIL' if failed else 'PASS', findings=findings, production_evidence=production, test_evidence=tests, claims=sorted(set(claims)), denials=sorted(set(denials)))
