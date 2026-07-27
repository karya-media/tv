"""Immutable value objects: TvgId, StreamUrl, GroupTitle.

Each encapsulates its own normalization/validation rule (e.g. a TvgId
knows what makes it well-formed) so that rule doesn't leak into use
cases or infrastructure. Implemented in Phase 2.
"""
