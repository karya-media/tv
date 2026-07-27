"""Ports (abstract interfaces) that application use cases depend on.

To be defined in Phase 2/3:
- PlaylistRepository  (persistence contract)
- StreamValidator     (protocol for checking a stream's liveness/quality)
- EPGProvider         (protocol for XMLTV access)
- PlaylistPublisher   (protocol for pushing master.m3u to GitHub)

Infrastructure implements these; application only imports the
interface, never the concrete class, so use cases stay testable with
in-memory fakes and swappable without touching business logic.
"""
