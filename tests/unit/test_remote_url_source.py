"""Unit tests for infrastructure.sources.remote_url_source.

Focused on _decode(), the pure (network-free) part of
RemoteUrlPlaylistSource - this is what silently broke for
gzip-compressed EPG sources (e.g. the default epgshare01.online EPG
URL, which is served as a literal .xml.gz file, not as a plain-text
response with a "Content-Encoding: gzip" transport header that httpx
would auto-decompress). Before the fix, raw gzip bytes were force-
decoded as latin-1 (which never raises, since every byte value is
valid in that encoding), silently producing garbage text instead of
an error - which then caused lxml's error-tolerant XML parser to find
zero <channel> elements without anyone noticing.
"""

import gzip

from iptv_manager.infrastructure.sources.remote_url_source import RemoteUrlPlaylistSource


def _source() -> RemoteUrlPlaylistSource:
    return RemoteUrlPlaylistSource("http://example.com/epg.xml.gz")


def test_decodes_plain_utf8_text_unchanged():
    result = _source()._decode(b"<tv><channel id=\"x\"/></tv>")
    assert result == '<tv><channel id="x"/></tv>'


def test_decompresses_gzip_content_before_decoding():
    original = '<tv><channel id="rt.uk"><display-name>RT</display-name></channel></tv>'
    compressed = gzip.compress(original.encode("utf-8"))
    result = _source()._decode(compressed)
    assert result == original


def test_gzip_detection_does_not_misfire_on_plain_text():
    # Plain text that happens to start with unrelated bytes must not
    # be mistaken for gzip and mangled.
    result = _source()._decode(b"hello world")
    assert result == "hello world"
