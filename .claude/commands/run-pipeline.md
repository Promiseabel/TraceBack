---
description: Run the Traceback pipeline against a video clip and print per-segment source attribution results.
allowed-tools: Bash, Read
argument-hint: <path_to_clip>
---

Run the Traceback pipeline against the provided clip and display per-segment attribution.

```bash
python -m tb.pipeline $ARGUMENTS
```

If `$ARGUMENTS` is empty, print usage:
```
Usage: /run-pipeline <path_to_clip>
Example: /run-pipeline /tmp/clips/sample.mp4
```

Ensure `ACOUSTID_API_KEY` is set in your environment or `.env` file before running.
