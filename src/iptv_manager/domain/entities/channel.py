"""Channel entity.

Represents a single playable entry from an M3U/M3U8 playlist, after
parsing and normalization. Immutable: any "fix" to a channel (e.g.
applying a repaired group title) produces a new Channel via `with_*`
methods rather than mutating the original in place.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

from iptv_manager.domain.value_objects.group_title import GroupTitle
from iptv_manager.domain.value_objects.stream_url import StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId


@dataclass(frozen=True, slots=True)
class Channel:
    """A single channel entry.

    `name` is the display name from #EXTINF (the text after the last
    comma) - what players show. It's kept distinct from `tvg_name`
    (an EPG lookup hint that may differ from, or be absent alongside,
    the display name).
    """

    name: str
    url: StreamUrl
    tvg_id: TvgId = field(default_factory=lambda: TvgId.EMPTY)
    tvg_name: str | None = None
    logo_url: str | None = None
    group_title: GroupTitle = field(default_factory=lambda: GroupTitle.parse(None))
    duration: float = -1.0
    source_category: str | None = None
    extra_attrs: Mapping[str, str] = field(default_factory=dict)

    def with_group_title(self, group_title: GroupTitle) -> Channel:
        return replace(self, group_title=group_title)

    def with_source_category(self, category: str) -> Channel:
        return replace(self, source_category=category)

    @property
    def duplicate_url_key(self) -> str:
        """Key used by MergePlaylistsUseCase to detect duplicate URLs."""
        return self.url.normalized_key

    @property
    def has_tvg_id(self) -> bool:
        return self.tvg_id.is_present

    @property
    def has_logo(self) -> bool:
        return bool(self.logo_url and self.logo_url.strip())
