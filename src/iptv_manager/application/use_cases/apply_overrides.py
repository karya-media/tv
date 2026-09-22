"""Use case: apply manually-specified tvg-id/group-title corrections
(see domain.entities.channel_override.ChannelOverride) to a merged
Playlist, keyed by stream URL.

Runs *after* CategorizeByCountryUseCase in the pipeline (see
_build_everything_result in interfaces.cli.main) so a human's explicit
correction always has the final say over anything derived
automatically - the exact fix the TV9-tagged-as-India case needed:
override its group-title back to "Indonesia;..." regardless of what
its (possibly wrong) tvg-id would otherwise derive.

A URL with no matching override, or an override row with both
correction columns left blank, leaves the channel completely
untouched.
"""

from __future__ import annotations

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.channel_override import ChannelOverride
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.group_title import GroupTitle
from iptv_manager.domain.value_objects.tvg_id import TvgId


class ApplyOverridesUseCase:
    """Pure domain logic, no I/O - the caller reads the overrides
    spreadsheet (see infrastructure.parsers.overrides_excel_reader)
    and passes in the parsed list."""

    def execute(self, playlist: Playlist, overrides: list[ChannelOverride]) -> Playlist:
        overrides_by_url = {
            override.url: override for override in overrides if not override.is_empty
        }
        if not overrides_by_url:
            return playlist

        return Playlist(
            name=playlist.name,
            channels=[self._apply(channel, overrides_by_url) for channel in playlist],
            category=playlist.category,
            warnings=list(playlist.warnings),
        )

    def _apply(self, channel: Channel, overrides_by_url: dict[str, ChannelOverride]) -> Channel:
        override = overrides_by_url.get(channel.url.raw)
        if override is None:
            return channel

        if override.new_tvg_id:
            channel = channel.with_tvg_id(TvgId.parse(override.new_tvg_id))
        if override.new_group_title:
            channel = channel.with_group_title(GroupTitle.parse(override.new_group_title))
        return channel
