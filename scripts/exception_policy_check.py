import pathlib
import re
import sys


RULE_BARE_EXCEPT = (
    'BARE_EXCEPT',
    re.compile(r'^\s*except\s*:\s*(#.*)?$'),
    'Bare except is not allowed. Catch specific exceptions and log with logger.exception.',
)

RULE_EXCEPT_EXCEPTION = (
    'EXCEPT_EXCEPTION',
    re.compile(r'^\s*except\s+Exception\s*:\s*(#.*)?$'),
    'except Exception should be avoided. Prefer specific exceptions; if unavoidable, add # noqa: broad-except.',
)

RULE_EXCEPT_PASS = (
    'EXCEPT_PASS',
    re.compile(r'^\s*except\b[^:]*:\s*$'),
    'Exception handler must not silently pass; log with logger.exception or handle explicitly.',
)


def _iter_py_files(root: pathlib.Path) -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for p in root.rglob('*.py'):
        if any(part in ('.venv', 'venv', '__pycache__') for part in p.parts):
            continue
        paths.append(p)
    return paths


def main(argv: list[str]) -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    target = repo_root / 'src'
    strict = False
    if '--strict' in argv:
        strict = True
    if len(argv) >= 2:
        if argv[1] != '--strict':
            target = (repo_root / argv[1]).resolve()

    if not target.exists():
        print(f"Target path does not exist: {target}")
        return 2

    violations: list[tuple[str, str, int, str]] = []
    warnings: list[tuple[str, str, int, str]] = []

    for path in _iter_py_files(target if target.is_dir() else target.parent):
        try:
            text = path.read_text(encoding='utf-8')
        except Exception:
            continue

        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if RULE_BARE_EXCEPT[1].match(line):
                violations.append((RULE_BARE_EXCEPT[0], str(path.relative_to(repo_root)), i + 1, RULE_BARE_EXCEPT[2]))

            if RULE_EXCEPT_EXCEPTION[1].match(line) and '# noqa: broad-except' not in line:
                bucket = violations if strict else warnings
                bucket.append((RULE_EXCEPT_EXCEPTION[0], str(path.relative_to(repo_root)), i + 1, RULE_EXCEPT_EXCEPTION[2]))

            if RULE_EXCEPT_PASS[1].match(line):
                j = i + 1
                while j < len(lines) and (lines[j].strip() == '' or lines[j].lstrip().startswith('#')):
                    j += 1
                if j < len(lines) and lines[j].strip() == 'pass':
                    violations.append((RULE_EXCEPT_PASS[0], str(path.relative_to(repo_root)), i + 1, RULE_EXCEPT_PASS[2]))
            i += 1

    if warnings:
        for code, rel, line_no, msg in warnings:
            print(f"{rel}:{line_no}: WARNING {code}: {msg}")

    if violations:
        for code, rel, line_no, msg in violations:
            print(f"{rel}:{line_no}: {code}: {msg}")
        print(f"\nFound {len(violations)} exception-policy violation(s).")
        return 1

    print('No exception-policy violations found.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
