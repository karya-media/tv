"""Port: checking whether a channel's stream is reachable.

infrastructure.validators.HttpStreamValidator is the concrete
implementation. Kept as a Protocol so validate_streams use case can be
unit tested with a fake validator, and so the underlying HTTP client
could be swapped later without touching application code.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from iptv_manager.domain.entities.channel import Channel
from iptv_manager.domain.entities.stream_validation_result import StreamValidationResult


@runtime_checkable
class StreamValidator(Protocol):
    async def validate(self, channel: Channel) -> StreamValidationResult: ...
