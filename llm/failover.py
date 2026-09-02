"""Provider failover: one wrapper over a primary and a secondary client.

The wrapper never swallows an error. It only decides *which* provider answers the
next request; when both sides fail, the caller sees the last `LLMError` and the
agent's own retry and fallback logic applies unchanged.
"""

import logging
import time
from collections.abc import Callable

from llm.base import DEFAULT_CONTEXT_LENGTH, LLMClient, LLMError, LLMResponse, describe_client

FAILOVER_THRESHOLD = 3        # consecutive failures before the other side is tried
FAILOVER_COOLDOWN_S = 300.0   # how long a demoted provider stays out of the way

log = logging.getLogger("llm.failover")


class FailoverLLMClient:
    def __init__(
        self,
        primary: LLMClient,
        secondary: LLMClient,
        *,
        primary_name: str,
        secondary_name: str,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._clients = {primary_name: primary, secondary_name: secondary}
        self._primary_name = primary_name
        self._secondary_name = secondary_name
        self.active_provider_name = primary_name
        self.failure_counts = {primary_name: 0, secondary_name: 0}
        self._cooldown_until = {primary_name: 0.0, secondary_name: 0.0}
        self._clock = clock

    def describe(self) -> tuple[str, str]:
        """The client that served the last call. `_try_other` promotes the
        fallback to active as soon as it answers, so reading the active client
        after an invocation names whoever actually produced the response."""
        return describe_client(self._clients[self.active_provider_name])

    @property
    def context_length(self) -> int:
        return getattr(
            self._clients[self.active_provider_name], "context_length", DEFAULT_CONTEXT_LENGTH
        )

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        *,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self._restore_primary_after_cooldown()
        active = self.active_provider_name
        try:
            response = self._clients[active].complete(messages, tools, max_tokens=max_tokens)
        except LLMError as exc:
            self.failure_counts[active] += 1
            other = self._other_name(active)
            if (
                self.failure_counts[active] >= FAILOVER_THRESHOLD
                and self._clock() >= self._cooldown_until[other]
            ):
                return self._try_other(messages, tools, max_tokens, active, other, exc)
            raise
        self.failure_counts[active] = 0
        return response

    def _try_other(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        max_tokens: int | None,
        active: str,
        other: str,
        first_error: LLMError,
    ) -> LLMResponse:
        try:
            response = self._clients[other].complete(messages, tools, max_tokens=max_tokens)
        except LLMError:
            self.failure_counts[other] += 1
            raise                              # the last error reaches the caller
        self._cooldown_until[active] = self._clock() + FAILOVER_COOLDOWN_S
        self.active_provider_name = other
        self.failure_counts[other] = 0
        log.warning(
            "provider %s failed %d times (%s); serving from %s",
            active, self.failure_counts[active], first_error.__class__.__name__, other,
        )
        return response

    def _other_name(self, name: str) -> str:
        return self._secondary_name if name == self._primary_name else self._primary_name

    def _restore_primary_after_cooldown(self) -> None:
        """Once the cooldown expires the configured primary gets a fresh chance."""
        if self.active_provider_name == self._primary_name:
            return
        if self._clock() < self._cooldown_until[self._primary_name]:
            return
        self.active_provider_name = self._primary_name
        self.failure_counts[self._primary_name] = 0
