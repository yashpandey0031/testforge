"""Turn mutation results (JSON dict) into one self-contained HTML page."""
import html
import json


def _row(r):
    cls = {"killed": "ok", "timeout": "ok", "survived": "bad"}[r["status"]]
    return (f"<tr class='{cls}'><td>{r['id']}</td><td>{r['line']}</td><td>{html.escape(r['operator'])}</td>"
            f"<td><code>{html.escape(r['original'])}</code></td><td><code>{html.escape(r['mutated'])}</code></td>"
            f"<td>{r['status']}</td></tr>")


def render(runs: dict) -> str:
    """runs: {label: result_dict}. Shows each run's score; survivors listed first."""
    cards, tables = [], []
    for label, res in runs.items():
        cards.append(f"<div class='card'><div class='score'>{res['score']}%</div>"
                     f"<div>{html.escape(label)}</div><small>{res['killed']}/{res['total']} bugs caught</small></div>")
        rows = sorted(res["results"], key=lambda r: r["status"] != "survived")
        tables.append(f"<h2>{html.escape(label)}</h2><table><tr><th>#</th><th>line</th><th>type</th>"
                      f"<th>original</th><th>mutated</th><th>result</th></tr>{''.join(_row(r) for r in rows)}</table>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TestForge report</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--mute:#666;--ok:#e7f6ec;--bad:#fdeaea;--line:#ddd}}
@media(prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#e8e8e8;--mute:#9aa;--ok:#173324;--bad:#40201f;--line:#333}}}}
body{{background:var(--bg);color:var(--fg);font-family:system-ui;max-width:900px;margin:2rem auto;padding:0 16px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap}}.card{{border:1px solid var(--line);border-radius:10px;padding:14px 18px;min-width:180px}}
.score{{font-size:2.2rem;font-weight:700}}small{{color:var(--mute)}}
table{{border-collapse:collapse;width:100%;font-size:.85rem}}td,th{{border-bottom:1px solid var(--line);padding:5px 8px;text-align:left}}
tr.ok{{background:var(--ok)}}tr.bad{{background:var(--bad)}}code{{font-size:.8rem;word-break:break-all}}
</style></head><body><h1>TestForge: mutation report</h1>
<p>Each row is a bug injected into the code. <b>killed</b> = a test failed (good). <b>survived</b> = every test still passed (a gap).</p>
<div class="cards">{''.join(cards)}</div>{''.join(tables)}</body></html>"""


def write(runs: dict, path: str):
    open(path, "w", encoding="utf-8").write(render(runs))
