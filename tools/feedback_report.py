"""Summarise anonymous thumbs up/down ratings until the admin report page exists.

Usage: python3 tools/feedback_report.py [path-to-feedback.jsonl]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'instance' / 'content-feedback.jsonl'
if not path.exists():
    sys.exit(f'No ratings yet ({path} not found).')
items = defaultdict(lambda: {'up': 0, 'down': 0, 'reasons': Counter()})
for line in path.read_text(encoding='utf-8').splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    key = (row['type'], row['id'], row['version'])
    items[key][row['rating']] += 1
    if row.get('reason'):
        items[key]['reasons'][row['reason']] += 1
print(f"{'type':8} {'id':22} {'v':>2} {'👍':>3} {'👎':>3}  reasons")
for (kind, item_id, version), s in sorted(items.items(), key=lambda kv: -kv[1]['down']):
    reasons = ', '.join(f'{k}×{v}' for k, v in s['reasons'].most_common())
    print(f"{kind:8} {item_id:22} {version:>2} {s['up']:>3} {s['down']:>3}  {reasons}")
