"""Domain layer.

Pure business rules and contracts. MUST NOT import from application,
infrastructure, or interfaces, and MUST NOT depend on any third-party
I/O library (no aiohttp, no SQLAlchemy, no FastAPI). This is what keeps
the system portable: every adapter downstream can be swapped without
touching anything in this package.
"""
