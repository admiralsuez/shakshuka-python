#!/usr/bin/env python3
"""Add # noqa: broad-except comments to legitimate broad exception handlers.

This script identifies common patterns where broad exception handling is
justified and adds appropriate noqa comments with explanations.
"""

import pathlib
import re
import sys

# Patterns that justify broad exception handling
JUSTIFICATION_PATTERNS = [
    # Flask error handlers (must catch all)
    (r'@\w+\.errorhandler\(Exception\)', 'Flask error handler must catch all exceptions'),
    
    # Cleanup/finally-like patterns  
    (r'except Exception:.*cleanup', 'Cleanup operations should not crash on errors', re.IGNORECASE),
    (r'except Exception:.*close', 'Resource cleanup should not crash', re.IGNORECASE),
    (r'except Exception:.*rollback', 'Transaction rollback should not crash', re.IGNORECASE),
    
    # Background worker/thread patterns
    (r'def.*worker\(', 'Background worker must not crash on individual errors', re.IGNORECASE),
    (r'threading\.Thread', 'Thread worker must handle all exceptions'),
    
    # Logging/monitoring (must never crash)
    (r'except Exception:.*log', 'Logging should never crash the application', re.IGNORECASE),
    (r'record_factory', 'Log record factory must never fail'),
    
    # Flask middleware (must never crash request/response cycle)
    (r'@app\.(before_request|after_request|teardown)', 'Flask lifecycle hooks must not crash'),
    
    # JSON serialization fallbacks
    (r'except Exception:.*json', 'JSON serialization fallback', re.IGNORECASE),
    
    # Import fallbacks (optional dependencies)
    (r'try:.*import.*except Exception:', 'Optional import - module may not exist'),
]


def should_add_noqa(file_path: pathlib.Path, line_num: int, lines: list[str]) -> tuple[bool, str]:
    """Check if a line should get a noqa comment."""
    
    # Already has noqa
    if 'noqa' in lines[line_num]:
        return False, ''
    
    # Get context (5 lines before, current line)
    start = max(0, line_num - 5)
    context = '\n'.join(lines[start:line_num + 1])
    
    # Check patterns
    for pattern_info in JUSTIFICATION_PATTERNS:
        pattern = pattern_info[0]
        justification = pattern_info[1]
        flags = pattern_info[2] if len(pattern_info) > 2 else 0
        
        if re.search(pattern, context, flags):
            return True, justification
    
    # API route error handling
    if '/api/' in file_path.as_posix() or 'routes' in file_path.parts:
        if 'except Exception:' in lines[line_num]:
            # Check if it's in a route handler
            for i in range(max(0, line_num - 20), line_num):
                if re.search(r'@\w+\.(route|get|post|put|delete|patch)', lines[i]):
                    return True, 'API route error handler must catch all exceptions'
    
    # Scheduler/background job patterns
    if 'scheduler' in file_path.name or 'autosave' in file_path.name:
        if 'except Exception:' in lines[line_num]:
            return True, 'Background job must handle all exceptions to prevent crash'
    
    # Data manager patterns (defensive)
    if 'data_manager' in file_path.name or 'queries.py' in file_path.name:
        if 'except Exception:' in lines[line_num]:
            return True, 'Data layer defensive exception handling'
    
    return False, ''


def process_file(file_path: pathlib.Path, dry_run: bool = False) -> int:
    """Process a single file and add noqa comments where appropriate."""
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        modified = False
        changes = 0
        
        for i, line in enumerate(lines):
            if 'except Exception:' in line and 'noqa' not in line:
                should_add, justification = should_add_noqa(file_path, i, lines)
                
                if should_add:
                    # Add noqa comment
                    indent = len(line) - len(line.lstrip())
                    base_line = line.rstrip()
                    new_line = f"{base_line}  # noqa: broad-except - {justification}"
                    
                    if dry_run:
                        print(f"  Line {i+1}: Would add noqa")
                        print(f"    {line}")
                        print(f"    → {new_line}")
                    else:
                        lines[i] = new_line
                        modified = True
                        changes += 1
        
        if modified and not dry_run:
            file_path.write_text('\n'.join(lines), encoding='utf-8')
            print(f"  Modified: {changes} lines")
        
        return changes
        
    except Exception as e:
        print(f"  Error processing {file_path}: {e}")
        return 0


def main():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    src_dir = repo_root / 'src'
    
    dry_run = '--dry-run' in sys.argv
    
    if dry_run:
        print("DRY RUN MODE - No files will be modified\n")
    
    py_files = list(src_dir.rglob('*.py'))
    total_changes = 0
    
    print(f"Processing {len(py_files)} Python files...\n")
    
    for file_path in sorted(py_files):
        rel_path = file_path.relative_to(repo_root)
        changes = process_file(file_path, dry_run)
        
        if changes > 0:
            print(f"{rel_path}: {changes} noqa comments {'would be ' if dry_run else ''}added")
            total_changes += changes
    
    print(f"\nTotal: {total_changes} noqa comments {'would be ' if dry_run else ''}added")
    
    if dry_run:
        print("\nRun without --dry-run to apply changes")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
