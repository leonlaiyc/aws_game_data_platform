# Two-minute operation demo video

The public video is a subtitle-first walkthrough of the four product
interfaces. Architecture views stay on the website and are intentionally not
repeated in the recording.

The recording uses deterministic browser fixtures that mirror responses
verified against the deployed IAM-signed APIs. This keeps the two-minute video
repeatable without claiming that every rendered frame makes a fresh paid AWS
request.

## Timeline

| Time | Chapter | Operation shown |
|---|---|---|
| 00:00–00:25 | M1 anomaly monitoring | Compare the current cumulative value with the previous 30 complete same-cutoff dates, then mark the incident as investigating |
| 00:25–00:53 | M2 experiment governance | Review concurrent experiments and show separate SRM and hourly guardrail outcomes |
| 00:53–01:28 | M3 analytics assistant | Ask why usage fell, then ask for an unsupported next-day prediction |
| 01:28–02:00 | M4 integration support | Paste a redacted OAuth request packet, then ask an out-of-scope exhibition question |

## Verified source and AWS evidence

- Source commit: `1ab3682`.
- Verification date: 2026-08-03.
- CloudFormation: Anomaly stack `UPDATE_COMPLETE` at 07:59 UTC, Analytics
  Assistant stack at 08:07 UTC, and Partner Support stack at 08:21 UTC.
- M1 replay: `site_b/2026-06-15T03:00Z`, 30 baseline dates, actual 13 versus
  baseline 36.5, deviation -64.38%. The IAM API moved incident
  `site_b#2026-06-15T03` to `INVESTIGATING`.
- M3 replay clock: `2026-06-15T05:00Z` (13:00 in the business timezone), all
  authorised sites, 124 active users versus a 177 thirty-day average (-30%).
  The next-day forecast question returns the deterministic unsupported boundary.
- M4: the redacted OAuth packet returns `ANSWERED`; the exhibition question
  returns `OUT_OF_SCOPE`. Both report `model_invoked=false`.
- S3 evidence: `gold/anomaly_alerts/site_b_2026-06-15T03.json`, 346 bytes,
  ETag `94eb09ac08a3415723e4b2739404b073`.
- Validation: 168 automated tests passed. The USD 5 budget guard passed, no
  project Kinesis streams remained, and no hourly-billed demo resource was
  created.

## Capture and render

Start the console with the infrastructure virtual environment:

```powershell
.\infra\.venv\Scripts\python.exe .\demo_console\server.py --no-open
```

Use a 1280 × 720 browser viewport. The recording routes are reproducible, for
example `/?recording&capture=m1-initial` and
`/?recording&capture=m4-out-of-scope`. Store the resulting PNGs under
`demo_console/recording`.

One command generates the MP4, poster, WebVTT, and SRT together:

```powershell
python -m pip install -r requirements-video.txt
python scripts/render_operation_demo.py
```

The MP4 is silent by design. Chinese subtitles are burned into the lower
caption rail and duplicated in WebVTT/SRT for accessibility. The operation UI
remains visible above the caption rail throughout all four chapters.
