"""Use case: merge multiple category playlists into one master
playlist.

Two distinct duplicate concepts are handled differently, deliberately:

- Duplicate stream URL: the same URL appearing more than once is
  always a literal redundant entry (e.g. the same channel present in
  two category files, or accidentally imported twice). It is removed
  from the merged master, and every removal is recorded so it can be
  reported.
- Duplicate tvg-id across *different* URLs: this can be a legitimate
  situation (the same channel offered via multiple backup streams), so
  entries are kept, but the group is flagged for the report generator
  (Phase 4) and the XMLTV validator (Phase 3) to surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist


@dataclass(slots=True)
class DuplicateUrlGroup:
    """One stream URL that appeared more than once across the merged
    playlists. `kept` is the entry that stayed in the master
    (first-seen wins); `removed` are the ones dropped."""

    key: str
    kept: Channel
    removed: list[Channel] = field(default_factory=list)


@dataclass(slots=True)
class DuplicateTvgIdGroup:
    """One tvg-id shared by two or more channels with distinct URLs.
    All channels are kept in the master; this is informational."""

    tvg_id: str
    channels: list[Channel]


@dataclass(slots=True)
class MergeResult:
    master: Playlist
    total_channels_before: int
    total_channels_after: int
    duplicate_urls: list[DuplicateUrlGroup] = field(default_factory=list)
    duplicate_tvg_ids: list[DuplicateTvgIdGroup] = field(default_factory=list)

    @property
    def removed_duplicate_url_count(self) -> int:
        return sum(len(group.removed) for group in self.duplicate_urls)


class MergePlaylistsUseCase:
    """Pure domain logic, no I/O - depends on nothing but entities, so
    it's trivial to unit test without touching the filesystem."""

    def execute(self, playlists: list[Playlist], *, master_name: str = "master") -> MergeResult:
        master = Playlist(name=master_name)
        total_before = sum(len(p) for p in playlists)

        seen_urls: dict[str, Channel] = {}
        duplicate_url_groups: dict[str, DuplicateUrlGroup] = {}
        tvg_id_map: dict[str, list[Channel]] = {}

        for playlist in playlists:
            for channel in playlist:
                url_key = channel.duplicate_url_key

                if url_key in seen_urls:
                    group = duplicate_url_groups.setdefault(
                        url_key,
                        DuplicateUrlGroup(key=url_key, kept=seen_urls[url_key]),
                    )
                    group.removed.append(channel)
                    continue  # exact duplicate URL: drop from the master

                seen_urls[url_key] = channel
                master.add_channel(channel)

                if channel.has_tvg_id:
                    tvg_id_map.setdefault(str(channel.tvg_id), []).append(channel)

        duplicate_tvg_ids = [
            DuplicateTvgIdGroup(tvg_id=tvg_id, channels=channels)
            for tvg_id, channels in tvg_id_map.items()
            if len(channels) > 1
        ]

        # Carry every source playlist's parser warnings forward so
        # nothing gets silently lost at merge time.
        for playlist in playlists:
            label = playlist.category or playlist.name
            master.warnings.extend(f"[{label}] {warning}" for warning in playlist.warnings)

        return MergeResult(
            master=master,
            total_channels_before=total_before,
            total_channels_after=len(master),
            duplicate_urls=list(duplicate_url_groups.values()),
            duplicate_tvg_ids=duplicate_tvg_ids,
        )
