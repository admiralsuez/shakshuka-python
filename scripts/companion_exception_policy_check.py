import pathlib
import re
import sys


RULE_EMPTY_CATCH = (
    'EMPTY_CATCH',
    re.compile(r'\bcatch\s*\([^)]*\)\s*\{\s*\}\s*'),
    'Empty catch blocks are not allowed. Handle or log the error.',
)

RULE_BROAD_CATCH = (
    'BROAD_CATCH',
    re.compile(r'\bcatch\s*\('),
    'Broad catch should be avoided. Prefer specific `on SomeException` handlers; if unavoidable, add // noqa: broad-catch.',
)

RULE_SILENT_CATCH = (
    'SILENT_CATCH',
    re.compile(r'\bcatch\s*\('),
    'Catch blocks should not silently return defaults without logging. Add a log/print or handle explicitly; if unavoidable, add // noqa: silent-catch.',
)

_BROAD_TYPES = {'Exception', 'Error', 'Object', 'dynamic'}
_LOG_MARKERS = (
    'print(',
    'debugPrint(',
    'developer.log(',
    '.log(',
    'logger.',
    'Logger.',
)


def _iter_dart_files(root: pathlib.Path) -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for p in root.rglob('*.dart'):
        if p.name.endswith('.g.dart'):
            continue
        if any(part in ('.dart_tool', 'build') for part in p.parts):
            continue
        paths.append(p)
    return paths


def _strip_inline_comment(line: str) -> str:
    idx = line.find('//')
    if idx == -1:
        return line
    return line[:idx]


def _looks_like_logging(text: str) -> bool:
    return any(marker in text for marker in _LOG_MARKERS)


_RETURN_DEFAULT_RE = re.compile(
    r'^\s*return\s+(?:false|true|null|\[\s*\]|\{\s*\}|<[^>]+>\s*\[\s*\]|<[^>]+>\s*\{\s*\})\s*;\s*$'
)


def _find_catch_blocks(lines: list[str]) -> list[tuple[int, int]]:
    blocks: list[tuple[int, int]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if 'catch' not in line:
            i += 1
            continue

        if not RULE_BROAD_CATCH[1].search(line):
            i += 1
            continue

        if '{' not in line:
            i += 1
            continue

        brace_depth = line.count('{') - line.count('}')
        j = i + 1
        while j < len(lines) and brace_depth > 0:
            brace_depth += lines[j].count('{') - lines[j].count('}')
            j += 1

        if brace_depth == 0:
            blocks.append((i, j - 1))
            i = j
            continue

        i += 1

    return blocks


def _extract_on_type(line: str) -> str | None:
    m = re.search(r'\bon\s+([A-Za-z_][A-Za-z0-9_]*)\s+catch\b', line)
    if not m:
        return None
    return m.group(1)


def _is_empty_catch(lines: list[str], start: int, end: int) -> bool:
    combined = '\n'.join(lines[start : end + 1])
    if RULE_EMPTY_CATCH[1].search(combined):
        return True

    for k in range(start + 1, end):
        stripped = _strip_inline_comment(lines[k]).strip()
        if stripped and stripped not in ('{', '}'):
            return False
    return True


def _is_silent_default_return(lines: list[str], start: int, end: int) -> bool:
    block_text = '\n'.join(lines[start : end + 1])
    if _looks_like_logging(block_text):
        return False

    statements: list[str] = []
    for k in range(start + 1, end):
        stripped = _strip_inline_comment(lines[k]).strip()
        if not stripped or stripped in ('{', '}'):
            continue
        statements.append(stripped)

    if len(statements) != 1:
        return False

    return _RETURN_DEFAULT_RE.match(statements[0]) is not None


def main(argv: list[str]) -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    target = repo_root / 'shakshuka_companion' / 'lib'
    strict = '--strict' in argv

    if len(argv) >= 2 and argv[1] != '--strict':
        target = (repo_root / argv[1]).resolve()

    if not target.exists():
        print(f"Target path does not exist: {target}")
        return 2

    violations: list[tuple[str, str, int, str]] = []
    warnings: list[tuple[str, str, int, str]] = []

    for path in _iter_dart_files(target if target.is_dir() else target.parent):
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            continue

        lines = text.splitlines()
        blocks = _find_catch_blocks(lines)

        for start, end in blocks:
            line = lines[start]
            rel = str(path.relative_to(repo_root))
            line_no = start + 1

            if '// noqa: empty-catch' not in line and _is_empty_catch(lines, start, end):
                violations.append((RULE_EMPTY_CATCH[0], rel, line_no, RULE_EMPTY_CATCH[2]))
                continue

            if '// noqa: broad-catch' not in line:
                on_type = _extract_on_type(line)
                if on_type is None or on_type in _BROAD_TYPES:
                    bucket = violations if strict else warnings
                    bucket.append((RULE_BROAD_CATCH[0], rel, line_no, RULE_BROAD_CATCH[2]))

            if '// noqa: silent-catch' not in line and _is_silent_default_return(lines, start, end):
                bucket = violations if strict else warnings
                bucket.append((RULE_SILENT_CATCH[0], rel, line_no, RULE_SILENT_CATCH[2]))

    if warnings:
        for code, rel, line_no, msg in warnings:
            print(f"{rel}:{line_no}: WARNING {code}: {msg}")

    if violations:
        for code, rel, line_no, msg in violations:
            print(f"{rel}:{line_no}: {code}: {msg}")
        print(f"\nFound {len(violations)} companion exception-policy violation(s).")
        return 1

    print('No companion exception-policy violations found.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
