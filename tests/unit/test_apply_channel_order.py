"""Unit tests for application.use_cases.apply_channel_order."""

from iptv_manager.application.use_cases.apply_channel_order import (
    ApplyChannelOrderUseCase,
)
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.stream_url import StreamUrl
from iptv_manager.domain.value_objects.tvg_id import TvgId


def _channel(name: str, tvg_id: str | None = None) -> Channel:
    return Channel(
        name=name,
        url=StreamUrl.parse(f"http://example.com/{name}.m3u8"),
        tvg_id=TvgId.parse(tvg_id),
    )


def _names(playlist: Playlist) -> list[str]:
    return [c.name for c in playlist]


def _run(priority_slots: list[list[str]], *names: str) -> Playlist:
    playlist = Playlist(name="test", channels=[_channel(n) for n in names])
    return ApplyChannelOrderUseCase().execute(priority_slots, playlist)


def test_no_priority_slots_returns_playlist_unchanged():
    result = _run([], "B", "A")
    assert _names(result) == ["B", "A"]


def test_pins_exact_matches_to_the_front_in_slot_order():
    result = _run([["MNCTV"], ["RCTI"]], "Other", "MNCTV", "RCTI")
    assert _names(result) == ["MNCTV", "RCTI", "Other"]


def test_pipe_separated_alternatives_are_grouped_together():
    result = _run(
        [["RCTI", "RCTI HD", "RCTI 2"]],
        "Other",
        "RCTI 2",
        "RCTI HD",
        "RCTI",
    )
    # Grouped together, in their original relative order within the group.
    assert _names(result) == ["RCTI 2", "RCTI HD", "RCTI", "Other"]


def test_unplaced_channels_keep_original_relative_order_at_the_end():
    result = _run([["RCTI"]], "Zebra", "RCTI", "Apple")
    assert _names(result) == ["RCTI", "Zebra", "Apple"]


class TestPrefixFallback:
    """Pass 2: variant spellings not explicitly listed in
    channel_order.txt still get grouped, via a word-boundary prefix
    match against the slot's primary (first-listed) name."""

    def test_unlisted_variant_is_grouped_with_its_slot(self):
        result = _run([["RCTI"]], "Other", "RCTI Prime", "RCTI")
        assert set(_names(result)[:2]) == {"RCTI Prime", "RCTI"}
        assert _names(result)[2] == "Other"

    def test_digit_directly_after_name_is_not_a_boundary(self):
        # Confirmed real-world case: Vietnam's "SCTV11".."SCTV19" are
        # a *different* broadcaster from Indonesia's "SCTV" (different
        # tvg-id country suffix) that happens to share the brand
        # prefix with no separator. Must not be grouped together.
        result = _run([["SCTV"]], "SCTV11 (720p)", "SCTV", "Other")
        assert _names(result) == ["SCTV", "SCTV11 (720p)", "Other"]

    def test_digit_after_a_separator_still_matches(self):
        result = _run([["RCTI"]], "RCTI 2", "Other", "RCTI")
        assert set(_names(result)[:2]) == {"RCTI 2", "RCTI"}
        assert _names(result)[2] == "Other"

    def test_unrelated_channel_sharing_a_letter_prefix_is_not_matched(self):
        # "RCTINews" has no word boundary after "RCTI" - must not be
        # swallowed into the RCTI slot.
        result = _run([["RCTI"]], "RCTINews", "Other")
        assert _names(result) == ["RCTINews", "Other"]

    def test_explicitly_slotted_channel_is_not_stolen_by_another_slots_prefix(self):
        # "RCTI World" is a genuinely different channel with its own
        # explicit slot - pass 1 must place it there before pass 2's
        # "RCTI" prefix rule gets a chance to grab it.
        result = _run(
            [["RCTI"], ["RCTI World"]],
            "RCTI World",
            "RCTI",
        )
        assert _names(result) == ["RCTI", "RCTI World"]

    def test_exact_and_prefix_matches_together_stay_grouped(self):
        result = _run(
            [["RCTI", "RCTI HD"]],
            "Other",
            "RCTI Prime",  # only matched via prefix fallback
            "RCTI HD",  # matched via exact alternative
            "RCTI",  # matched via exact primary name
        )
        assert set(_names(result)[:3]) == {"RCTI Prime", "RCTI HD", "RCTI"}
        assert _names(result)[3] == "Other"

    def test_unlisted_variant_stays_adjacent_even_with_a_later_slot_between(self):
        # "RCTI Prime" (unlisted) must land right next to "RCTI"/
        # "RCTI 2", not get pushed after "MNCTV"/"RCTI World" just
        # because those have their own slots later in the file.
        result = _run(
            [["RCTI", "RCTI 2"], ["MNCTV"], ["RCTI World"]],
            "Other",
            "RCTI Prime",
            "MNCTV",
            "RCTI 2",
            "RCTI",
            "RCTI World",
        )
        assert set(_names(result)[:3]) == {"RCTI Prime", "RCTI 2", "RCTI"}
        assert _names(result)[3] == "MNCTV"
        assert _names(result)[4] == "RCTI World"


class TestCountryGuard:
    """A textual word-boundary match alone isn't enough evidence: a
    channel whose tvg-id confirms it's from a specific, different
    country must never be pulled into another country's slot just
    because it happens to share a common word as a name prefix."""

    def test_foreign_channel_with_word_boundary_is_not_swept_in(self):
        # Real case: India's "INews (720p)" and Iraq's "iNEWS TV" both
        # satisfy the plain textual prefix rule against Indonesia's
        # "iNews" slot.
        playlist = Playlist(
            name="test",
            channels=[
                _channel("Other"),
                _channel("INews (720p)", tvg_id="INews.inSD"),
                _channel("iNEWS TV (1080p)", tvg_id="INews.iqSD"),
                _channel("iNews", tvg_id="iNews.id"),
            ],
        )
        result = ApplyChannelOrderUseCase().execute([["iNews"]], playlist)
        assert _names(result)[0] == "iNews"
        assert set(_names(result)[1:]) == {"Other", "INews (720p)", "iNEWS TV (1080p)"}

    def test_channel_with_no_derivable_country_still_matches(self):
        # No tvg-id at all - still allowed through, since this is
        # exactly the "genuinely new, unlisted Indonesian variant"
        # case the prefix fallback exists for.
        playlist = Playlist(
            name="test",
            channels=[
                _channel("Other"),
                _channel("iNews Prime"),
                _channel("iNews", tvg_id="iNews.id"),
            ],
        )
        result = ApplyChannelOrderUseCase().execute([["iNews"]], playlist)
        assert set(_names(result)[:2]) == {"iNews Prime", "iNews"}
        assert _names(result)[2] == "Other"

    def test_channel_confirmed_indonesian_still_matches(self):
        playlist = Playlist(
            name="test",
            channels=[
                _channel("Other"),
                _channel("iNews Prime", tvg_id="iNewsPrime.id"),
                _channel("iNews", tvg_id="iNews.id"),
            ],
        )
        result = ApplyChannelOrderUseCase().execute([["iNews"]], playlist)
        assert set(_names(result)[:2]) == {"iNews Prime", "iNews"}
        assert _names(result)[2] == "Other"

    def test_exact_match_is_never_blocked_by_the_country_guard(self):
        # The guard only applies to the *prefix fallback* (pass 2) -
        # an exact listed alternative always wins regardless of
        # tvg-id, since the user explicitly named it.
        playlist = Playlist(
            name="test",
            channels=[_channel("Other"), _channel("TV One", tvg_id="TVOne.ukSD")],
        )
        result = ApplyChannelOrderUseCase().execute([["TV One"]], playlist)
        assert _names(result) == ["TV One", "Other"]
