#!/usr/bin/env python3
"""Create an HTML comparison from separate baseline and structured workflow JSON files."""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def escape(value: object) -> str:
    return html.escape(str(value))


def indexed(matches: list[dict]) -> dict[str, dict]:
    result = {}
    for match in matches:
        submission = str(match["submission_id"])
        if submission in result:
            raise ValueError("Duplicate submission ID in results")
        roles = {}
        for rank, role in enumerate(match["roles"], 1):
            role_id = str(role["role_id"])
            if role_id in roles:
                raise ValueError("Duplicate role ID in one candidate's results")
            roles[role_id] = {**role, "rank": rank}
        result[submission] = roles
    return result


def make_report(baseline: dict, structured: dict) -> str:
    left = indexed(baseline.get("baseline_role_matches", []))
    right = indexed(structured.get("structured_role_matches", []))
    if not left or not right:
        raise ValueError("Both files must contain completed results for their respective modes")
    if set(left) != set(right):
        raise ValueError("The files contain different submissions; compare runs for the same candidates")
    sections = []
    for index, submission in enumerate(left, 1):
        old, new = left[submission], right[submission]
        ids = sorted(set(old) | set(new), key=lambda key: (
            new.get(key, {}).get("rank", 10**6), old.get(key, {}).get("rank", 10**6), key))
        rows = []
        for role_id in ids:
            a, b = old.get(role_id), new.get(role_id)
            if a and b:
                change = a["rank"] - b["rank"]
                movement = f"+{change}" if change > 0 else str(change)
            else:
                movement = "New in top 10" if b else "Outside top 10"
            def score(role):
                return f'{float(role["cosine_similarity"]):.4f}' if role else "—"
            title = (b or a)["title"]
            rows.append("<tr>" + "".join(f"<td>{escape(v)}</td>" for v in (
                title, a["rank"] if a else "—", score(a), b["rank"] if b else "—",
                score(b), movement)) + "</tr>")
        sections.append(f'<section><div class="section-head"><div><p class="eyebrow">CANDIDATE {index:02d}</p>'
                        f'<h2>Role ranking comparison</h2></div><span class="tag">Submission {escape(submission)}</span></div>'
                        '<div class="table-wrap"><table><thead><tr><th>Occupation</th><th>Baseline rank</th>'
                        '<th>Baseline cosine</th><th>Structured rank</th><th>Structured cosine</th>'
                        '<th>Rank change</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div></section>')
    return '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Retrieval comparison</title><style>
*{box-sizing:border-box}body{margin:0;background:#f3f6f9;color:#17283d;font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1200px;margin:auto;padding:48px 24px 70px}.eyebrow{font-size:11px;letter-spacing:.16em;font-weight:700;color:#167f7a;margin:0 0 8px}h1{font-size:clamp(30px,5vw,42px);line-height:1.15;margin:0 0 12px;letter-spacing:-.035em}header p{max-width:740px;color:#576a7d;margin:0}section{margin-top:30px;background:white;border:1px solid #dbe4eb;border-radius:16px;overflow:hidden;box-shadow:0 10px 30px #1b35420b}.section-head{padding:24px 26px;display:flex;align-items:center;justify-content:space-between;gap:15px;flex-wrap:wrap}h2{font-size:20px;margin:0}.tag{font-size:12px;color:#516679;background:#f1f5f7;border-radius:20px;padding:7px 11px}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;text-align:left;min-width:760px}th{background:#eff5f7;color:#526b7b;font-size:11px;letter-spacing:.055em;text-transform:uppercase}th,td{padding:13px 18px;border-top:1px solid #e7eef2}td:first-child{font-weight:600;color:#1b3b50}td:not(:first-child){font-variant-numeric:tabular-nums}tr:hover td{background:#f8fbfb}.note{margin-top:18px;color:#627486;font-size:13px}footer{margin-top:24px;color:#667889;font-size:12px}
</style></head><body><main><header><p class="eyebrow">RETRIEVAL EVALUATION</p><h1>Baseline vs. structured query</h1><p>A side-by-side view of the occupations returned for the same candidate. Roles are matched using their ESCO occupation IDs.</p></header>''' + "".join(sections) + '''<p class="note">Rank change = baseline rank minus structured rank; positive means the role moved up. A dash means the role was not returned in that run's top 10. Cosine similarity is a retrieval signal, not a probability or proof of a better match.</p><footer>Candidate documents and query vectors are not included in this report. Submission IDs are retained to identify matching runs.</footer></main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("structured", type=Path)
    parser.add_argument("--output", type=Path, default=Path("output/retrieval-comparison.html"))
    args = parser.parse_args()
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    structured = json.loads(args.structured.read_text(encoding="utf-8"))
    report = make_report(baseline, structured)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file:
        file.write(report)
    print(f"Saved comparison to {args.output}")


if __name__ == "__main__":
    main()
