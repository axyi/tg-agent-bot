"""The embeddings client (REQ-V190-RET-01): LM Studio's OpenAI-compatible
`/embeddings` endpoint, batched, one retry, a dimension check and one CLIENT
span per request. `rag.py` (T5) builds the vector side of retrieval on top
of this; `bot.py` (T7) constructs the one process-wide instance and wires it
in as `embedder=`.
"""

from collections.abc import Sequence

import httpx

import tracing

BATCH_SIZE = 32


class EmbeddingError(Exception):
    """An embeddings request failed. Subclasses `Exception`, not `LLMError`:
    embeddings are not a chat completion and share none of its retry/failover
    machinery."""


class EmbeddingTimeoutError(EmbeddingError):
    """The one retry was exhausted and the final failure was itself an
    `httpx.TimeoutException` — a distinguishable **type**, not a parsed
    message, so ERR-01's handler can catch this before the plain
    `EmbeddingError` it subclasses (row 10b before row 6)."""


class EmbeddingsClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        dim: int,
        timeout_s: float,
        client: httpx.Client,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.dim = dim
        self.timeout_s = timeout_s
        self._client = client

    def describe(self) -> tuple[str, str]:
        return ("lmstudio", self.model)

    def embed(self, texts: Sequence[str], *, conv_id: int | None = None) -> list[list[float]]:
        """Embed `texts` in batches of `BATCH_SIZE`, in order.

        `conv_id` is not part of the spec's abbreviated signature but is the
        only way the one CLIENT span per request can carry `conv_id=None`
        when indexing versus the turn's `conv_id` when querying (RET-01) —
        the caller (`rag.py`, T5) passes it through; it is optional here so
        every indexing call site can simply omit it.
        """
        texts = list(texts)
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            vectors.extend(self._embed_batch(batch, conv_id=conv_id))
        return vectors

    def _embed_batch(self, batch: list[str], *, conv_id: int | None) -> list[list[float]]:
        with tracing.start_span(
            f"embeddings {self.model}",
            tracing.KIND_CLIENT,
            conv_id=conv_id,
        ) as span:
            span.set_attribute("gen_ai.operation.name", "embeddings")
            span.set_attribute("gen_ai.provider.name", "lmstudio")
            span.set_attribute("gen_ai.request.model", self.model)
            span.set_attribute("tg_agent.embeddings.batch_size", len(batch))
            span.set_attribute("tg_agent.embeddings.dim", self.dim)
            return self._post_with_retry(batch)

    def _post_with_retry(self, batch: list[str]) -> list[list[float]]:
        """**One retry** on `httpx.TransportError` (a `TimeoutException` is a
        `TransportError` subclass, so the first attempt's timeout is caught
        here too); the classification of the *final* failure — timeout or
        not — decides which exception type is raised (REQ-V190-RET-01)."""
        try:
            return self._post(batch)
        except httpx.TransportError:
            pass
        try:
            return self._post(batch)
        except httpx.TimeoutException as exc:
            raise EmbeddingTimeoutError(
                f"embeddings transport error: {exc.__class__.__name__}"
            ) from exc
        except httpx.TransportError as exc:
            raise EmbeddingError(f"embeddings transport error: {exc.__class__.__name__}") from exc

    def _post(self, batch: list[str]) -> list[list[float]]:
        response = self._client.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "input": batch},
            timeout=self.timeout_s,
        )
        if response.status_code != 200:
            raise EmbeddingError(f"embeddings http {response.status_code}")
        try:
            data = response.json()
        except ValueError:
            raise EmbeddingError("embeddings malformed response") from None
        if not isinstance(data, dict):
            raise EmbeddingError("embeddings malformed response")
        entries = data.get("data")
        if not isinstance(entries, list) or len(entries) != len(batch):
            raise EmbeddingError("embeddings malformed response")
        try:
            ordered = sorted(entries, key=lambda entry: entry["index"])
        except (KeyError, TypeError):
            raise EmbeddingError("embeddings malformed response") from None
        vectors: list[list[float]] = []
        for entry in ordered:
            vector = entry.get("embedding") if isinstance(entry, dict) else None
            if not isinstance(vector, list):
                raise EmbeddingError("embeddings malformed response")
            if len(vector) != self.dim:
                raise EmbeddingError(f"embeddings dimension {len(vector)} != {self.dim}")
            try:
                vectors.append([float(x) for x in vector])
            except (TypeError, ValueError):
                raise EmbeddingError("embeddings malformed response") from None
        return vectors
