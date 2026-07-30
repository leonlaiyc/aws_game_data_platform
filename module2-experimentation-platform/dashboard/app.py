"""Local, auto-refreshing central experiment operations view.

Hosting stays at $0: the browser talks only to this localhost process, and the
process makes SigV4-signed GET requests to the existing IAM-protected API.
Architecture and business context belong in the slide deck; this surface is
for the short operation demo.
"""
import argparse
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / "demo"))
sys.path.insert(0, str(Path(__file__).parent))

import demo_lib as lib  # noqa: E402
from view_model import build_view_model  # noqa: E402


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Aurora Experiment Operations</title>
  <style>
    :root { color-scheme: dark; --bg:#07111f; --panel:#0e1b2d; --line:#20334d;
      --text:#edf5ff; --muted:#8ba3bf; --cyan:#4fd1c5; --amber:#f6c453;
      --red:#ff6b6b; --blue:#69a7ff; }
    * { box-sizing:border-box } body { margin:0; background:radial-gradient(circle at 10% 0,
      #132a42 0,var(--bg) 38%); color:var(--text); font:14px/1.45 Inter,Segoe UI,sans-serif }
    main { max-width:1400px; margin:auto; padding:32px }
    header { display:flex; justify-content:space-between; align-items:end; gap:24px }
    h1 { margin:0; font-size:28px; letter-spacing:-.02em } .sub { color:var(--muted); margin-top:5px }
    .live { display:flex; align-items:center; gap:8px; color:var(--muted) }
    .dot { width:9px;height:9px;border-radius:50%;background:var(--cyan);box-shadow:0 0 12px var(--cyan) }
    .cards { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:24px 0 }
    .card,.table-wrap { background:rgba(14,27,45,.92); border:1px solid var(--line);
      border-radius:14px; box-shadow:0 16px 45px rgba(0,0,0,.18) }
    .card { padding:17px 19px }.label { color:var(--muted); text-transform:uppercase;
      letter-spacing:.11em;font-size:11px }.value { font-size:28px;font-weight:700;margin-top:4px }
    .table-wrap { overflow:hidden } table { width:100%; border-collapse:collapse }
    th { color:var(--muted);text-align:left;font-size:11px;text-transform:uppercase;
      letter-spacing:.08em;background:#0b1728 } th,td { padding:13px 14px;border-bottom:1px solid var(--line) }
    tr:last-child td {border-bottom:0} tr:hover td {background:#102139}
    .name {font-weight:650}.id,.dim {color:var(--muted);font-size:12px}.pill {
      display:inline-flex;align-items:center;border-radius:999px;padding:4px 8px;font-size:12px;
      border:1px solid var(--line);white-space:nowrap}.healthy {color:var(--cyan);border-color:#27655f}
    .watch {color:var(--amber);border-color:#6b5729}.action {color:var(--red);border-color:#6a3037}
    .neutral {color:var(--blue)} .on {color:var(--cyan)} .off {color:var(--red)}
    #error {display:none;margin:18px 0;padding:12px;border:1px solid #6a3037;border-radius:10px;color:var(--red)}
    @media(max-width:900px){main{padding:18px}.cards{grid-template-columns:repeat(2,1fr)}
      .table-wrap{overflow:auto}header{align-items:start;flex-direction:column}}
  </style>
</head>
<body><main>
  <header><div><h1>Experiment operations</h1>
    <div class="sub">All client sites · exposure health · allocation control</div></div>
    <div class="live"><span class="dot"></span><span id="refreshed">Connecting…</span></div>
  </header>
  <div id="error"></div>
  <section class="cards">
    <div class="card"><div class="label">Total experiments</div><div class="value" id="total">–</div></div>
    <div class="card"><div class="label">Running now</div><div class="value" id="running">–</div></div>
    <div class="card"><div class="label">Needs action</div><div class="value" id="action">–</div></div>
    <div class="card"><div class="label">Draft queue</div><div class="value" id="draft">–</div></div>
  </section>
  <div class="table-wrap"><table><thead><tr>
    <th>Experiment</th><th>Owner</th><th>Site / Game</th><th>State</th><th>Health</th>
    <th>Allocation</th><th>Exposure SRM</th><th>Last check / End</th>
  </tr></thead><tbody id="rows"></tbody></table></div>
</main><script>
const esc=s=>String(s??"—").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",
  '"':"&quot;","'":"&#39;"}[c]));
async function refresh(){
  try{
    const r=await fetch("/api/experiments",{cache:"no-store"}); const d=await r.json();
    if(!r.ok) throw new Error(d.error||"request failed");
    total.textContent=d.summary.total; running.textContent=d.summary.running;
    action.textContent=d.summary.needs_action; draft.textContent=d.summary.draft;
    rows.innerHTML=d.experiments.map(x=>`<tr>
      <td><div class="name">${esc(x.name)}</div><div class="id">${esc(x.experiment_id)}</div></td>
      <td><div class="name">${esc(x.owner)}</div><div class="dim">${esc(x.created_by)}</div></td>
      <td>${esc(x.client_site_id)}<div class="dim">${esc(x.game_id)} · ${esc(x.execution_mode)}</div></td>
      <td><span class="pill neutral">${esc(x.state)}</span></td>
      <td><span class="pill ${esc(x.health)}">${esc(x.health)}</span>
        <div class="dim">${esc(x.health_detail)}</div></td>
      <td class="${x.allocation_enabled?"on":"off"}">${x.allocation_enabled?"ENABLED":"CONTROL ONLY"}</td>
      <td>${esc(x.srm_status)}<div class="dim">n=${esc(x.total_exposed)}</div></td>
      <td><div>${esc(x.last_checked_at)}</div><div class="dim">${esc(x.planned_end_at)}</div></td>
    </tr>`).join("") || `<tr><td colspan="8" class="dim">No experiments found.</td></tr>`;
    error.style.display="none"; refreshed.textContent="Updated "+new Date().toLocaleTimeString();
  }catch(e){error.textContent=e.message;error.style.display="block";refreshed.textContent="Refresh failed"}
}
refresh(); setInterval(refresh,15000);
</script></body></html>"""


def _fetch(api_url: str) -> dict:
    response = lib.api_request(api_url, "GET", "/experiments")
    return build_view_model(response.get("experiments", []))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Print the signed API snapshot and exit (preflight/CI mode).",
    )
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()

    outputs = lib.stack_outputs("AuroraGamesRegistryStack")
    api_url = outputs["ExperimentsApiUrl"]
    if args.snapshot:
        print(json.dumps(_fetch(api_url), indent=2, default=str))
        print("RESULT: PASS — central registry snapshot fetched")
        return 0

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                payload, content_type, status = (
                    PAGE.encode("utf-8"),
                    "text/html; charset=utf-8",
                    200,
                )
            elif self.path.startswith("/api/experiments"):
                try:
                    payload = json.dumps(
                        _fetch(api_url), default=str
                    ).encode("utf-8")
                    status = 200
                except Exception as error:
                    payload = json.dumps(
                        {"error": f"{type(error).__name__}: {error}"}
                    ).encode("utf-8")
                    status = 502
                content_type = "application/json"
            else:
                payload, content_type, status = b"not found", "text/plain", 404
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *values):
            print(f"[dashboard] {fmt % values}")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Dashboard: {url}")
    print("Refresh interval: 15 seconds. Press Ctrl+C to stop.")
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
