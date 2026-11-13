"""Parser for JSON IPTV playlist feeds.

Supports ordinary JSON channel lists and the base64-encoded channel
fields used by Playlist Semar's endpoint. Parsed channels are normalized
into the domain model and can then be serialized as the project's M3U
output format.
"""

from __future__ import annotations

import base64
import json
import math
import re
from collections.abc import Mapping
from typing import Any

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.group_title import GroupTitle
from iptv_manager.domain.value_objects.stream_url import InvalidStreamUrlError, StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId
from iptv_manager.infrastructure.parsers.m3u_parser import M3UParser


class JSONPlaylistParser:
    """Convert common JSON IPTV feed structures into a Playlist."""

    def parse(self, raw_text: str, *, name: str, category: str | None = None) -> Playlist:
        playlist = Playlist(name=name, category=category)
        try:
            payload = json.loads(raw_text.lstrip("\ufeff"))
        except json.JSONDecodeError as exc:
            playlist.warnings.append(f"invalid JSON source: {exc}")
            return playlist

        category_names = self._category_names(payload)
        provider = payload.get("provider") if isinstance(payload, Mapping) else None
        if isinstance(provider, Mapping):
            epg = self._text(provider.get("epg"))
            if epg and epg.startswith(("http://", "https://")):
                playlist.epg_url = epg

        entries = self._channel_entries(payload)
        for index, item in enumerate(entries, start=1):
            if not isinstance(item, Mapping):
                playlist.warnings.append(f"JSON entry {index}: ignored non-object value")
                continue

            stream = self._decoded_text(self._first(item, "url", "stream_url", "streamUrl", "link"))
            if not stream:
                playlist.warnings.append(f"JSON entry {index}: missing stream URL, skipped")
                continue

            try:
                stream_url = StreamUrl.parse(stream)
            except InvalidStreamUrlError as exc:
                playlist.warnings.append(f"JSON entry {index}: invalid stream URL, skipped: {exc}")
                continue

            channel_name = self._decoded_text(
                self._first(item, "name", "title", "channel_name", "channelName")
            ) or "Unknown channel"
            raw_group = self._first(item, "group", "group_title", "groupTitle", "category")
            group = self._decoded_text(raw_group)
            if group in category_names:
                group = category_names[group]

            logo = self._decoded_text(
                self._first(item, "logo", "logo_url", "logoUrl", "tvg-logo", "tvg_logo")
            )
            tvg_id = self._decoded_text(self._first(item, "tvg-id", "tvg_id", "tvgId"))
            tvg_name = self._decoded_text(self._first(item, "tvg-name", "tvg_name", "tvgName"))
            duration = self._duration(item.get("duration"))

            playlist.add_channel(
                Channel(
                    name=channel_name,
                    url=stream_url,
                    tvg_id=TvgId.parse(tvg_id),
                    tvg_name=tvg_name,
                    logo_url=logo,
                    group_title=GroupTitle.parse(group),
                    duration=duration,
                    source_category=category,
                )
            )

        if not entries:
            playlist.warnings.append("JSON source contains no channel list")
        return playlist

    def serialize(self, playlist: Playlist, epg_url: str | None = None) -> str:
        """Serialize channels into the canonical M3U format used downstream."""
        return M3UParser().serialize(playlist, epg_url=epg_url or playlist.epg_url)

    @staticmethod
    def _channel_entries(payload: Any) -> list[Any]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, Mapping):
            return []
        for key in ("channels", "items", "streams", "entries", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        data = payload.get("data")
        if isinstance(data, list):
            return data
        if isinstance(data, Mapping):
            for key in ("channels", "items", "streams", "entries", "results"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    @classmethod
    def _category_names(cls, payload: Any) -> dict[str, str]:
        if not isinstance(payload, Mapping):
            return {}
        categories = payload.get("categories")
        if not isinstance(categories, Mapping):
            return {}
        names: dict[str, str] = {}
        for key, value in categories.items():
            if isinstance(value, Mapping):
                label = cls._decoded_text(value.get("name"))
                if label:
                    names[str(key)] = label
        return names

    @staticmethod
    def _first(item: Mapping[str, Any], *keys: str) -> Any:
        for key in keys:
            value = item.get(key)
            if value is not None and value != "":
                return value
        return None

    @staticmethod
    def _text(value: Any) -> str | None:
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        return None

    @classmethod
    def _decoded_text(cls, value: Any) -> str | None:
        text = cls._text(value)
        if not text:
            return None
        # Semar encodes channel name, URL, and category as standard
        # base64 strings. Decode only valid UTF-8 printable text; ordinary
        # unencoded provider fields are left unchanged.
        candidate = text.strip()
        if len(candidate) % 4 == 0 and re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", candidate):
            try:
                decoded = base64.b64decode(candidate, validate=True).decode("utf-8").strip()
            except (ValueError, UnicodeDecodeError):
                pass
            else:
                if decoded and all(ch.isprintable() for ch in decoded):
                    return decoded
        return text

    @classmethod
    def _duration(cls, value: Any) -> float:
        text = cls._text(value)
        if not text:
            return -1.0
        try:
            duration = float(text)
        except ValueError:
            return -1.0
        return duration if math.isfinite(duration) else -1.0
