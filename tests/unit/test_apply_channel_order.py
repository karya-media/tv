"""Unit tests for application.use_cases.apply_channel_order."""

from iptv_manager.application.use_cases.apply_channel_order import (
    ApplyChannelOrderUseCase,
)
from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.playlist import Playlist
from iptv_manager.domain.value_objects.stream_url import StreamUrl


def _channel(name: str) -> Channel:
    return Channel(name=name, url=StreamUrl.parse(f"http://example.com/{name}.m3u8"))


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

    def test_digit_suffix_with_no_separator_counts_as_a_boundary(self):
        result = _run([["RCTI"]], "RCTI3", "Other")
        assert _names(result) == ["RCTI3", "Other"]

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
