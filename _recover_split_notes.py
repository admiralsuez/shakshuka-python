"""
Best-effort recovery for notes whose split-encoded content was truncated to
1000 characters (corrupting the base64 so it cannot be fully decoded).

Strategy:
  * Decode the largest valid base64 prefix (trim to a multiple of 4 chars).
  * Extract the JSON "primary" string value up to the truncation point.
  * Unescape standard JSON escapes.
  * Store the recovered plain text back into the note and flag was_split_encoded.

The trailing portion of "primary" and the entire "secondary" editor content
are unrecoverable (they were never stored). This restores readability.

A timestamped backup of the database is created before any writes.
"""

import base64
import os
import shutil
import sqlite3
import sys
from datetime import datetime

DRY_RUN = "--apply" not in sys.argv

DB = os.path.join(os.environ.get("APPDATA", ""), "Shakshuka", "data", "shakshuka.db")
PREFIX = "__SHAKSHUKA_SPLIT_B64_V1__"


def unescape_json_fragment(s: str) -> str:
    """Unescape a (possibly truncated) JSON string fragment."""
    out = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "\\" and i + 1 < n:
            nxt = s[i + 1]
            mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f"}
            if nxt in mapping:
                out.append(mapping[nxt])
                i += 2
                continue
            if nxt == "u" and i + 5 < n:
                try:
                    out.append(chr(int(s[i + 2 : i + 6], 16)))
                    i += 6
                    continue
                except ValueError:
                    pass
            # Unknown escape or truncated escape; drop the backslash
            out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def extract_primary(partial_json: str):
    """Extract the primary string value from a (truncated) JSON object string."""
    marker = '"primary":"'
    # Allow optional whitespace variations
    idx = partial_json.find(marker)
    if idx == -1:
        # try with spaces
        marker = '"primary": "'
        idx = partial_json.find(marker)
        if idx == -1:
            return None, None
    start = idx + len(marker)

    # Scan for the unescaped closing quote of the primary value.
    i = start
    n = len(partial_json)
    while i < n:
        if partial_json[i] == "\\":
            i += 2
            continue
        if partial_json[i] == '"':
            break
        i += 1
    primary_raw = partial_json[start:i]
    truncated = i >= n  # ran off the end without finding closing quote

    # Best-effort secondary extraction (usually lost due to truncation).
    secondary_raw = None
    if not truncated:
        rest = partial_json[i + 1 :]
        smarker = '"secondary":"'
        sidx = rest.find(smarker)
        if sidx == -1:
            smarker = '"secondary": "'
            sidx = rest.find(smarker)
        if sidx != -1:
            sstart = sidx + len(smarker)
            j = sstart
            m = len(rest)
            while j < m:
                if rest[j] == "\\":
                    j += 2
                    continue
                if rest[j] == '"':
                    break
                j += 1
            secondary_raw = rest[sstart:j]

    primary = unescape_json_fragment(primary_raw)
    secondary = unescape_json_fragment(secondary_raw) if secondary_raw else ""
    return primary, secondary


def recover():
    if not os.path.exists(DB):
        print("DB not found:", DB)
        return

    if DRY_RUN:
        print("*** DRY RUN (no changes will be written). Re-run with --apply to commit. ***")
    else:
        backup = DB + ".pre_recover_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(DB, backup)
        print("Backup created:", backup)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, title, content FROM notes WHERE content LIKE '__SHAKSHUKA_SPLIT_B64_V1__%'"
    ).fetchall()
    print("Encoded notes found:", len(rows))

    for r in rows:
        note_id = r["id"]
        content = r["content"]
        payload = content[len(PREFIX):]
        usable = payload[: len(payload) - (len(payload) % 4)]
        try:
            decoded_bytes = base64.b64decode(usable, validate=False)
        except Exception as e:
            print(f"[{note_id}] base64 decode failed entirely: {e}")
            continue
        partial_json = decoded_bytes.decode("utf-8", errors="ignore")

        primary, secondary = extract_primary(partial_json)
        if primary is None:
            print(f"[{note_id}] could not locate primary content; skipping")
            continue

        combined = primary
        if secondary and secondary.strip():
            combined = f"{primary}\n\n--- Split Editor ---\n\n{secondary}"

        if not DRY_RUN:
            conn.execute(
                "UPDATE notes SET content = ?, was_split_encoded = 1 WHERE id = ?",
                (combined, note_id),
            )
        print("-" * 60)
        print(f"[{note_id}] title={r['title']!r}")
        print(f"  recovered {len(primary)} chars of primary"
              + (f", {len(secondary)} chars of secondary" if secondary else ", secondary lost"))
        print(f"  preview: {primary[:120]!r}")

    if not DRY_RUN:
        conn.commit()
    conn.close()
    print("=" * 60)
    if DRY_RUN:
        print("DRY RUN complete. No changes written. Re-run with --apply to commit.")
    else:
        print("Recovery complete. Backup at:", backup)


if __name__ == "__main__":
    recover()
