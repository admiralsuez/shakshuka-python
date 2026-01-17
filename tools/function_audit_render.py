import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


EXCLUDE_PREFIXES = (
    'tests/',
    'tests\\',
    'debug_scripts/',
    'debug_scripts\\',
)


TARGET_FILES = [
    'src/sqlite_data_manager.py',
    'src/app.py',
    'assets/static/js/app/app.js',
    'assets/static/js/pages/notes.js',
    'assets/static/js/pages/tasks.js',
]


def _norm_path(p: str) -> str:
    return p.replace('\\', '/').lstrip('./')


def _is_excluded(p: str) -> bool:
    np = _norm_path(p)
    return np.startswith(EXCLUDE_PREFIXES)


def _load_findings(json_path: Path) -> List[Dict[str, Any]]:
    raw = json.loads(json_path.read_text(encoding='utf-8'))
    if not isinstance(raw, list):
        raise ValueError('function_audit.json expected a list')
    return [x for x in raw if isinstance(x, dict)]


def _group_by_file(findings: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for f in findings:
        path = _norm_path(str(f.get('path', '')))
        if not path or _is_excluded(path):
            continue
        grouped.setdefault(path, []).append(f)

    for path, items in grouped.items():
        items.sort(key=lambda x: (int(x.get('line', 0) or 0), str(x.get('symbol', ''))))

    return grouped


def _md_escape_inline(s: str) -> str:
    return s.replace('`', '\\`')


def _render_function_block(f: Dict[str, Any]) -> str:
    symbol = _md_escape_inline(str(f.get('symbol', '')))
    kind = _md_escape_inline(str(f.get('kind', '')))
    line = int(f.get('line', 0) or 0)

    possible = f.get('possible_bugs', [])
    if not isinstance(possible, list):
        possible = []

    mitigations = f.get('mitigations_seen', [])
    if not isinstance(mitigations, list):
        mitigations = []

    suggestions = f.get('suggestions', [])
    if not isinstance(suggestions, list):
        suggestions = []

    out: List[str] = []
    out.append(f"### `{symbol}` ({kind}, line {line})")

    out.append('')
    out.append('**Possible bugs (3):**')
    for i, b in enumerate(possible[:3], start=1):
        out.append(f"- **{i}.** {_md_escape_inline(str(b))}")

    out.append('')
    out.append('**Mitigations seen:**')
    if mitigations:
        for m in mitigations:
            out.append(f"- **[seen]** {_md_escape_inline(str(m))}")
    else:
        out.append('- **[seen]** (none detected)')

    out.append('')
    out.append('**Suggestions:**')
    if suggestions:
        for s in suggestions:
            out.append(f"- **[suggest]** {_md_escape_inline(str(s))}")
    else:
        out.append('- **[suggest]** (none generated)')

    out.append('')
    return '\n'.join(out)


def render_markdown(grouped: Dict[str, List[Dict[str, Any]]], target_files: List[str], title: str) -> str:
    lines: List[str] = []
    lines.append(f'# {title}')
    lines.append('')
    lines.append('## Scope')
    lines.append('')
    lines.append('- **Included files:**')
    for tf in target_files:
        lines.append(f"- **[file]** `{_norm_path(tf)}`")
    lines.append('')
    lines.append('- **Excluded prefixes:**')
    seen_excludes = set()
    for p in EXCLUDE_PREFIXES:
        np = _norm_path(p)
        if np in seen_excludes:
            continue
        seen_excludes.add(np)
        lines.append(f"- **[exclude]** `{np}`")
    lines.append('')

    for tf in target_files:
        tf_norm = _norm_path(tf)
        items = grouped.get(tf_norm, [])
        lines.append(f"## `{tf_norm}`")
        lines.append('')
        lines.append(f"- **[count]** {len(items)} functions/methods")
        lines.append('')

        if not items:
            lines.append('- **[note]** No findings found for this file (path mismatch or file not scanned).')
            lines.append('')
            continue

        # group by language for clarity
        langs: Dict[str, List[Dict[str, Any]]] = {}
        for it in items:
            langs.setdefault(str(it.get('language', 'unknown')), []).append(it)

        for lang, lang_items in sorted(langs.items(), key=lambda x: x[0]):
            lines.append(f"### Language: `{lang}`")
            lines.append('')
            for it in lang_items:
                lines.append(_render_function_block(it))

    return '\n'.join(lines)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    json_path = root / 'build_reports' / 'function_audit.json'
    if not json_path.exists():
        raise SystemExit(f"Missing: {json_path} (run tools/function_audit.py first)")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--file',
        action='append',
        dest='files',
        default=[],
        help='Target file (relative path). Can be specified multiple times.',
    )
    parser.add_argument(
        '--out',
        default='build_reports/function_audit_batch1.md',
        help='Output markdown path (relative).',
    )
    parser.add_argument(
        '--title',
        default='Function Bug Audit — Batch 1 (Largest Files)',
        help='Markdown H1 title for the report.',
    )
    args = parser.parse_args()

    findings = _load_findings(json_path)
    grouped = _group_by_file(findings)

    target_files = args.files if args.files else TARGET_FILES
    out_md = render_markdown(grouped, target_files, args.title)

    out_path = root / args.out
    out_path.write_text(out_md, encoding='utf-8')
    print(f"Wrote {out_path}")


if __name__ == '__main__':
    main()
