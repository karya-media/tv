"""Persist per-URL consecutive offline observations across scheduled runs.

Only definitive OFFLINE outcomes advance the counter. Transient/unknown
results are retained for recheck, and an ONLINE result clears quarantine.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from iptv_manager.application.use_cases.validate_streams import StreamValidationSummary
from iptv_manager.domain.entities.stream_validation_result import StreamStatus


class StreamValidationHistory:
    def __init__(self, path: Path, *, quarantine_after: int = 3) -> None:
        self.path = path
        self.quarantine_after = max(1, quarantine_after)

    def update(self, summary: StreamValidationSummary) -> set[str]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        history: dict[str, Any] = raw if isinstance(raw, dict) else {}
        checked_at = datetime.now(UTC).isoformat()
        excluded: set[str] = set()
        for result in summary.results:
            url = result.channel.url.raw
            previous = history.get(url, {})
            if not isinstance(previous, dict):
                previous = {}
            count = int(previous.get("consecutive_offline", 0))
            if result.status is StreamStatus.OFFLINE:
                count += 1
            elif result.status is StreamStatus.ONLINE:
                count = 0
            # Uncertain outcomes don't increase the counter or cause removal.
            record = {
                "channel": result.channel.name,
                "last_checked": checked_at,
                "last_status": result.status.value,
                "consecutive_offline": count,
                "last_http_status": result.http_status,
            }
            history[url] = record
            if count >= self.quarantine_after:
                excluded.add(url)
        summary.excluded_urls = excluded
        self._write_atomically(history)
        return excluded

    def _write_atomically(self, history: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(history, handle, indent=2, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
