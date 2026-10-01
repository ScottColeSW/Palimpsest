"""Renders cases.json as CASES.md, a table to review labels in.

    python bench/render_cases.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).parent
ORDER = ["new", "reinforces", "coexists", "collides", "exception_of", "supersedes"]


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def render(cases: dict) -> str:
    lines = ["# Benchmark cases", "",
             "Generated from `cases.json` by `render_cases.py`; edit the JSON, not this file. "
             "Labeling rules are in [GUIDE.md](GUIDE.md).", ""]
    judge = cases["judge"]
    lines += [f"## Judge ({len(judge)} cases)", ""]
    for relation in ORDER:
        group = [c for c in judge if c["expected"]["relation"] == relation]
        lines += [f"### `{relation}` ({len(group)})", "",
                  "| id | split | claim | held claims | answer | why |", "|---|---|---|---|---|---|"]
        for c in group:
            held = "<br>".join(f"**{n['key']}** {_cell(n['text'])}" for n in c["neighbors"]) or "(none)"
            answer = relation + (f" ({c['expected']['related']})" if c["expected"]["related"] else "")
            flags = [c["kind"] if c["kind"] != "attribute" else "", "external" if c["source"] == "external" else ""]
            tag = " ".join(f"*{f}*" for f in flags if f)
            lines.append(f"| {c['id']} | {c['split']} | {_cell(c['claim'])} {tag} | {held} | {answer} | {_cell(c['rationale'])} |")
        lines.append("")
    frame = cases["frame"]
    lines += [f"## Frame ({len(frame)} cases)", "",
              "| id | split | text | already filed | worth keeping | scope | kind | reuse domain | why |",
              "|---|---|---|---|---|---|---|---|---|"]
    for c in frame:
        e = c["expected"]
        known = "; ".join(f"{k['domain']}/{k['referent']}" for k in c["known"]) or "-"
        lines.append(f"| {c['id']} | {c['split']} | {_cell(c['text'])} | {known} | {'yes' if e['worth_keeping'] else 'no'} | "
                     f"{e.get('scope', '-')} | {e.get('kind', '-')} | {e.get('domain') or '-'} | {_cell(c['rationale'])} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    (HERE / "CASES.md").write_text(render(cases), encoding="utf-8")
    print(f"wrote {HERE / 'CASES.md'}")
