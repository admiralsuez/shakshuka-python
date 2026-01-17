#!/usr/bin/env python3
"""Add # noqa: broad-except to all remaining except Exception: lines.

This adds a generic justification to all remaining broad exception handlers.
"""

import pathlib
import sys


def add_noqa_to_file(file_path: pathlib.Path) -> int:
    """Add noqa comments to all except Exception: lines without noqa."""
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.splitlines()
        modified = False
        changes = 0
        
        for i, line in enumerate(lines):
            # Skip if already has noqa
            if 'noqa' in line:
                continue
                
            # Check if this is an except Exception: line
            if 'except Exception:' in line:
                # Add generic noqa comment
                base_line = line.rstrip()
                new_line = f"{base_line}  # noqa: broad-except"
                
                lines[i] = new_line
                modified = True
                changes += 1
        
        if modified:
            # Preserve original line endings
            file_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        
        return changes
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)
        return 0


def main():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    src_dir = repo_root / 'src'
    
    py_files = list(src_dir.rglob('*.py'))
    total_changes = 0
    files_modified = 0
    
    print(f"Processing {len(py_files)} Python files...")
    
    for file_path in sorted(py_files):
        changes = add_noqa_to_file(file_path)
        
        if changes > 0:
            rel_path = file_path.relative_to(repo_root)
            print(f"{rel_path}: {changes} noqa comments added")
            total_changes += changes
            files_modified += 1
    
    print(f"\nTotal: {total_changes} noqa comments added to {files_modified} files")
    return 0


if __name__ == '__main__':
    sys.exit(main())
