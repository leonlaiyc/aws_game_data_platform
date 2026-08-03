# Live AWS operation demo console

This is the presentation surface for the four-module interface walkthrough.
Each module keeps an architecture and operation view, while the final video
records only the four operation views. M1 shows cumulative usage through the
latest hour against a 30-day same-cutoff baseline and updates an incident to
`INVESTIGATING`. M3 answers one historical diagnosis and refuses one future
prediction. M4 diagnoses a pasted API request packet, then declines a company
event question that is absent from the integration corpus. The localhost
server keeps SigV4 credentials out of the browser.

On Windows, double-click `START_DEMO.cmd` in the repository root. It starts the
local signing server and opens the console automatically.

The equivalent command is:

```powershell
.\infra\.venv\Scripts\python.exe .\demo_console\server.py
```

Open `http://127.0.0.1:8787`, then follow the four numbered chapters. For a
clean 16:9 recording, use a 1280 × 720 browser viewport.
