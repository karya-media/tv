"""Infrastructure layer: concrete adapters.

Implements domain ports using real libraries: lxml/regex M3U parsing,
aiohttp/httpx stream validation, FFprobe subprocess analysis,
SQLAlchemy persistence, GitHub publishing (git commit + push, or the
GitHub REST API). Nothing outside this layer should import aiohttp,
SQLAlchemy, or subprocess directly.
"""
