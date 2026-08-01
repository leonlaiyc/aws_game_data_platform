# Two-minute operation demo video

The public video is a subtitle-first walkthrough of the actual product
interfaces. Its screenshots are captured while the localhost console invokes
or reads the deployed AWS stacks; they are not mock response cards.

## Timeline

| Time | Chapter | Verified operation shown |
|---|---|---|
| 00:00–00:05 | Opening | Four live AWS operating workflows |
| 00:05–00:28 | M1 Detect | Click scan; DAU 91 vs EWMA 204.5; SNS/S3 evidence |
| 00:28–00:50 | M3 Investigate | Open the S3 first-look report created from the anomaly |
| 00:50–01:22 | M2 Experiment Ops | Refresh Registry; filter six experiments that need action |
| 01:22–01:49 | M4 Support | Type a partner question; show IAM-scoped clarification response |
| 01:49–02:00 | Closing | Serverless governance and verification summary |

## Capture and render

Start the console with the infrastructure virtual environment:

```powershell
.\infra\.venv\Scripts\python.exe .\demo_console\server.py
```

Use a 1280 × 720 browser viewport and operate the four chapters. Store the
named evidence states under `demo_console/recording`. The browser talks only to
localhost; SigV4 signing remains in the Python process.

One command generates the MP4, poster, WebVTT and SRT together:

```powershell
python -m pip install -r requirements-video.txt
python scripts/render_operation_demo.py
```

The resulting MP4 is silent by design. Chinese subtitles are burned into the
lower caption rail and duplicated in WebVTT/SRT for accessibility. The real UI
remains visible above the caption rail throughout the operation chapters.
