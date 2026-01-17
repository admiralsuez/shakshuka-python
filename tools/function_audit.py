import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


EXCLUDE_DIR_PARTS = {
    '.git',
    '__pycache__',
    'dist',
    'build',
    'build_reports',
    'node_modules',
    'venv',
    '.venv',
}


@dataclass
class Finding:
    language: str
    path: str
    symbol: str
    kind: str
    line: int
    possible_bugs: List[str]
    mitigations_seen: List[str]
    suggestions: List[str]


def _should_skip(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    for disallowed in EXCLUDE_DIR_PARTS:
        if disallowed.lower() in parts:
            return True
    return False


def iter_files(root: Path, exts: Iterable[str]) -> Iterable[Path]:
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        if _should_skip(p):
            continue
        if p.suffix.lower() in exts:
            yield p


def _rel_path(root: Path, path: Path) -> str:
    try:
        rel = path.relative_to(root)
    except Exception:
        rel = path
    return str(rel).replace('\\', '/')


def _slice_lines(src_lines: List[str], start_line: int, end_line: int) -> str:
    if start_line < 1:
        start_line = 1
    if end_line < start_line:
        end_line = start_line
    start_i = start_line - 1
    end_i = end_line
    return ''.join(src_lines[start_i:end_i])


# ----------------------------
# Python extraction
# ----------------------------

def extract_python_defs(path: Path) -> List[Tuple[str, str, int, str]]:
    # returns (qualified_name, kind, lineno, source)
    try:
        src = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    src_lines = src.splitlines(keepends=True)
    out: List[Tuple[str, str, int, str]] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.stack: List[str] = []

        def visit_ClassDef(self, node: ast.ClassDef) -> Any:
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
            qn = '.'.join(self.stack + [node.name]) if self.stack else node.name
            kind = 'method' if self.stack else 'function'
            lineno = int(getattr(node, 'lineno', 1))
            start_line = lineno
            if getattr(node, 'decorator_list', None):
                try:
                    start_line = min(start_line, *(int(getattr(d, 'lineno', start_line)) for d in node.decorator_list))
                except Exception:
                    start_line = lineno
            end_line = int(getattr(node, 'end_lineno', lineno))
            source = _slice_lines(src_lines, start_line, end_line)
            out.append((qn, kind, lineno, source))
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
            qn = '.'.join(self.stack + [node.name]) if self.stack else node.name
            kind = 'async_method' if self.stack else 'async_function'
            lineno = int(getattr(node, 'lineno', 1))
            start_line = lineno
            if getattr(node, 'decorator_list', None):
                try:
                    start_line = min(start_line, *(int(getattr(d, 'lineno', start_line)) for d in node.decorator_list))
                except Exception:
                    start_line = lineno
            end_line = int(getattr(node, 'end_lineno', lineno))
            source = _slice_lines(src_lines, start_line, end_line)
            out.append((qn, kind, lineno, source))
            self.stack.append(node.name)
            self.generic_visit(node)
            self.stack.pop()

    Visitor().visit(tree)
    return out


# ----------------------------
# JS extraction (lightweight)
# ----------------------------

def extract_js_defs(path: Path) -> List[Tuple[str, str, int, str]]:
    # returns (name, kind, line, source)
    try:
        src = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return []

    out: List[Tuple[str, str, int, str]] = []


    def find_matching_brace(open_index: int) -> Optional[int]:
        depth = 0
        i = open_index
        in_str: Optional[str] = None
        escape = False
        while i < len(src):
            ch = src[i]
            if in_str is not None:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == in_str:
                    in_str = None
                i += 1
                continue

            if ch in ('\"', "'", '`'):
                in_str = ch
                i += 1
                continue

            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return None


    def slice_function_source(start_index: int, after_sig_index: int) -> str:
        brace_index = src.find('{', after_sig_index)
        if brace_index == -1:
            end = src.find('\n', after_sig_index)
            if end == -1:
                end = len(src)
            return src[start_index:end]
        end_brace = find_matching_brace(brace_index)
        if end_brace is None:
            end = src.find('\n', brace_index)
            if end == -1:
                end = len(src)
            return src[start_index:end]
        return src[start_index : end_brace + 1]

    # function foo(...) { }
    for m in re.finditer(r'(^|\n)\s*function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\(', src):
        name = m.group('name')
        line = src[: m.start()].count('\n') + 1
        source = slice_function_source(m.start(), m.end())
        out.append((name, 'function', line, source))

    # const foo = (...) =>
    for m in re.finditer(r'(^|\n)\s*(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^\n;]*\)\s*=>', src):
        name = m.group('name')
        line = src[: m.start()].count('\n') + 1
        source = slice_function_source(m.start(), m.end())
        out.append((name, 'arrow_function', line, source))

    # const foo = function(...) {}
    for m in re.finditer(r'(^|\n)\s*(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?function\s*\(', src):
        name = m.group('name')
        line = src[: m.start()].count('\n') + 1
        source = slice_function_source(m.start(), m.end())
        out.append((name, 'function_expr', line, source))

    return out


# ----------------------------
# Heuristic bug suggester
# ----------------------------

def suggest_for_symbol(language: str, source: str, symbol: str, kind: str) -> Tuple[List[str], List[str], List[str]]:
    s = source or ''
    possible: List[str] = []
    mitigations: List[str] = []
    suggestions: List[str] = []

    lowered = s.lower()

    # Generic mitigations
    if 'try:' in s or 'except' in s:
        mitigations.append('has try/except blocks')
    if 'validate' in lowered:
        mitigations.append('has validation helpers')
    if 'logger.' in lowered:
        mitigations.append('has logging')

    if language == 'python':
        is_route = ('route' in lowered and '@' in s) or ('jsonify' in lowered) or ('request.' in lowered)
        is_db = 'execute(' in lowered or 'sqlite3' in lowered or 'begin' in lowered or 'commit' in lowered
        has_bare_except = re.search(r'\n\s*except\s*:\s*(?:pass|return|continue|break)', s) is not None
        has_broad_except = re.search(r'\n\s*except\s+Exception\b', s) is not None
        swallows_errors = re.search(r'\n\s*except\b[^:]*:\s*\n\s*(?:pass|return\s+None|return\s+\[\]|return\s+\{\})', s) is not None

        if is_route:
            possible.extend([
                'Input validation gaps (missing type/length checks) can cause 500s or bad data.',
                'Database/service dependency may be None or uninitialized, causing runtime errors.',
                'Exception handling may hide root cause or return 200 on failures.',
            ])
            suggestions.extend([
                'Validate request.json shape and types; cap payload sizes.',
                'Return 503 on DB/service unavailable; log exception with context.',
                'Add tests for invalid payloads and missing dependencies.',
            ])
        elif is_db:
            possible.extend([
                'Transaction mode may block readers/writers unexpectedly (BEGIN IMMEDIATE vs deferred).',
                'Connection leaks can exhaust pool and deadlock under load.',
                'Silent fallbacks (returning empty list/defaults) can mask DB corruption/outages.',
            ])
            suggestions.extend([
                'Prefer deferred reads; use context managers for pooled connections.',
                'Expose pool metrics and alert on timeouts/high watermark usage.',
                'Return structured errors (None/Exception) and let APIs return 503.',
            ])
        else:
            possible.extend([
                'Edge cases not handled (None/empty inputs).',
                'Concurrency issues if shared state is mutated across threads.',
                'Error handling may be inconsistent (exceptions swallowed vs raised).',
            ])
            suggestions.extend([
                'Add input guards and unit tests for None/empty.',
                'Use locks or avoid shared mutable globals.',
                'Standardize error handling + logging patterns.',
            ])

        if has_bare_except:
            possible[2] = 'Bare except blocks can hide critical errors and make debugging impossible.'
        elif has_broad_except:
            possible[2] = 'Broad exception catching may hide root causes or improperly handle expected error types.'

        if swallows_errors:
            possible[1] = 'Exception handling appears to swallow errors (pass/return default), masking failures.'
            suggestions.append('Avoid silent fallbacks; return structured errors or re-raise with context.')

    else:
        uses_fetch = 'fetch(' in lowered
        uses_dom = 'queryselector' in lowered or 'getelementbyid' in lowered
        uses_html_injection = 'innerhtml' in lowered or 'insertadjacenthtml' in lowered
        missing_ok_check = uses_fetch and ('response.ok' not in lowered) and ('.ok' not in lowered)

        possible.extend([
            'Global state coupling can cause race conditions or overwritten functions.',
            'Fetch/API calls may not include correct headers/credentials, causing auth/CSRF issues.',
            'DOM queries may assume elements exist, causing null dereference errors.',
        ])
        suggestions.extend([
            'Move to ES modules; remove duplicate function names; centralize state.',
            'Centralize API wrapper with consistent headers/credentials and error handling.',
            'Guard DOM lookups and add runtime checks/logging.',
        ])

        if uses_fetch:
            mitigations.append('uses fetch')
        if uses_html_injection:
            possible[0] = 'Direct HTML injection (innerHTML/insertAdjacentHTML) can enable XSS if content is not sanitized.'
            suggestions.append('Prefer DOM node creation or sanitize content at the boundary before injecting HTML.')
        if missing_ok_check:
            possible[1] = 'Fetch calls may not check response.ok / handle non-2xx responses consistently.'
            suggestions.append('Always check response.ok and surface structured errors to the UI layer.')
        if uses_dom:
            mitigations.append('touches DOM')

    # ensure exactly 3 possible bugs
    possible = possible[:3] if len(possible) >= 3 else possible + ['(not enough heuristics yet)'] * (3 - len(possible))
    return possible, mitigations, suggestions


def audit_repo(root: Path) -> List[Finding]:
    findings: List[Finding] = []

    for p in iter_files(root, {'.py'}):
        for qn, kind, line, source in extract_python_defs(p):
            possible, mitigations, suggestions = suggest_for_symbol('python', source, qn, kind)
            findings.append(
                Finding(
                    language='python',
                    path=_rel_path(root, p),
                    symbol=qn,
                    kind=kind,
                    line=line,
                    possible_bugs=possible,
                    mitigations_seen=sorted(set(mitigations)),
                    suggestions=sorted(set(suggestions)),
                )
            )

    for p in iter_files(root, {'.js'}):
        for name, kind, line, source in extract_js_defs(p):
            possible, mitigations, suggestions = suggest_for_symbol('javascript', source, name, kind)
            findings.append(
                Finding(
                    language='javascript',
                    path=_rel_path(root, p),
                    symbol=name,
                    kind=kind,
                    line=line,
                    possible_bugs=possible,
                    mitigations_seen=sorted(set(mitigations)),
                    suggestions=sorted(set(suggestions)),
                )
            )

    return findings


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    findings = audit_repo(root)

    out_path = root / 'build_reports' / 'function_audit.json'
    out_path.parent.mkdir(parents=True, exist_ok=True)

    payload: List[Dict[str, Any]] = []
    for f in findings:
        payload.append(
            {
                'language': f.language,
                'path': f.path,
                'symbol': f.symbol,
                'kind': f.kind,
                'line': f.line,
                'possible_bugs': f.possible_bugs,
                'mitigations_seen': f.mitigations_seen,
                'suggestions': f.suggestions,
            }
        )

    out_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(f"Wrote {len(payload)} findings to {out_path}")


if __name__ == '__main__':
    main()
