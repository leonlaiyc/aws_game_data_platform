# Two-minute demo video

The public video is a subtitle-first, operation-only walkthrough. Architecture
and service-selection rationale remain in the surrounding portfolio page.

## Timeline

| Time | Chapter | Verified evidence shown |
|---|---|---|
| 00:00–00:05 | Opening | Four governed operating workflows |
| 00:05–00:30 | M1 Detect | DAU 91 vs EWMA 204.4541; SNS/S3 evidence; 6/6 review candidates |
| 00:30–00:55 | M3 Investigate | GGR 891.83 USD direct match; first-look DAU −55.73% |
| 00:55–01:30 | M2 Experiment Ops | analyzed result with caveats; guardrail reason; live 99/1 SRM stop and control-only fallback |
| 01:30–01:55 | M4 Support | clarification, durable escalation and code-owned leakage fallback |
| 01:55–02:00 | Closing | Repository, architecture, cost and validation evidence |

The source cues live in `scripts/render_demo_video.py`. One command generates
the MP4, poster, WebVTT and SRT together:

```powershell
python -m pip install -r requirements-video.txt
python scripts/render_demo_video.py
```

The resulting MP4 is silent by design. The burned-in presentation copy carries
the full story, while the WebVTT track provides accessible captions and a later
voice-over can be added without reworking the visual sequence.
