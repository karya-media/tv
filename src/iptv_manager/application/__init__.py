"""Application layer: use cases and DTOs.

Orchestrates domain entities via ports. Contains no I/O code itself:
it calls ports, and infrastructure supplies the concrete implementation
via dependency injection wired at the interfaces layer.
"""
