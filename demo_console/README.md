# Live AWS operation demo console

This is the presentation surface for the four-module interface walkthrough.
Each module opens on an architecture flow and then switches to its operation
view. M1 uses a deterministic synthetic hourly snapshot to demonstrate the
production design without leaving a schedule running. M4 provides two explicit
demo paths: an in-scope integration question that receives a governed answer,
and an out-of-scope question that is refused before model invocation. The other
operation views can read from or execute against the deployed AWS stacks. The
localhost server keeps SigV4 credentials out of the browser.

On Windows, double-click `START_DEMO.cmd` in the repository root. It starts the
local signing server and opens the console automatically.

The equivalent command is:

```powershell
.\infra\.venv\Scripts\python.exe .\demo_console\server.py
```

Open `http://127.0.0.1:8787`, then follow the four numbered chapters. For a
clean 16:9 recording, use a 1600 × 900 browser viewport.
