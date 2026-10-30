# Copyright (c) 2026 OceanBase.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Canonical, self-contained context packets with verified prefix reuse."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import cast

from powercontext.errors import PowerContextError

_PACK_SCHEMA = "powercontext.context-pack.v1"
_DELTA_SCHEMA = "powercontext.context-pack-delta.v1"
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class ContextPackError(PowerContextError, ValueError):
    """A packet, delta or UTF-8 chunk violates the transport contract."""


def _wire(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ContextPackError("Duplicate JSON field")  # noqa: TRY003
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ContextPackError(f"Invalid JSON constant: {value}")  # noqa: TRY003


def _payload(data: bytes, schema: str, fields: set[str]) -> dict[str, object]:
    if not isinstance(data, bytes):
        raise ContextPackError("Packet data must be bytes")  # noqa: TRY003
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_fields, parse_constant=_reject_constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise ContextPackError("Invalid UTF-8 JSON packet") from error  # noqa: TRY003
    if not isinstance(value, dict) or set(value) != fields or value.get("schema") != schema:
        raise ContextPackError("Invalid packet fields or schema")  # noqa: TRY003
    return cast("dict[str, object]", value)


def _validate_items(items: tuple[bytes, ...]) -> None:
    if not isinstance(items, tuple) or any(not isinstance(item, bytes) for item in items):
        raise ContextPackError("Chunks must be a tuple of bytes")  # noqa: TRY003
    try:
        for item in items:
            item.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ContextPackError("Each chunk must contain valid UTF-8") from error  # noqa: TRY003


def _encode_items(items: tuple[bytes, ...]) -> list[str]:
    return [base64.b64encode(item).decode("ascii") for item in items]


def _decode_items(value: object) -> tuple[bytes, ...]:
    if not isinstance(value, list):
        raise ContextPackError("Wire chunks must be a Base64 string array")  # noqa: TRY003
    items: list[bytes] = []
    for encoded in value:
        if not isinstance(encoded, str):
            raise ContextPackError("Wire chunks must be Base64 strings")  # noqa: TRY003
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ContextPackError("Invalid Base64 chunk") from error  # noqa: TRY003
        if base64.b64encode(decoded).decode("ascii") != encoded:
            raise ContextPackError("Noncanonical Base64 chunk")  # noqa: TRY003
        items.append(decoded)
    result = tuple(items)
    _validate_items(result)
    return result


def _validate_digest(value: str) -> None:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ContextPackError("Invalid SHA-256 digest")  # noqa: TRY003


@dataclass(frozen=True)
class ContextPack:
    """An immutable complete packet with canonical digest and wire byte count."""

    items: tuple[bytes, ...]
    digest: str = field(init=False)
    byte_count: int = field(init=False)

    def __post_init__(self) -> None:
        _validate_items(self.items)
        payload: dict[str, object] = {"schema": _PACK_SCHEMA, "items": _encode_items(self.items)}
        digest = "sha256:" + hashlib.sha256(_wire(payload)).hexdigest()
        object.__setattr__(self, "digest", digest)
        payload.update(digest=digest, byte_count=0)
        # The decimal width of byte_count contributes to the count itself.
        while (size := len(_wire(payload))) != payload["byte_count"]:
            payload["byte_count"] = size
        object.__setattr__(self, "byte_count", size)

    @classmethod
    def build(cls, items: tuple[bytes, ...]) -> ContextPack:
        """Build and validate a complete packet, including an empty packet."""
        return cls(items)

    @classmethod
    def from_content(cls, content: str | bytes | None, *, chunk_bytes: int = 512) -> ContextPack:
        """Split UTF-8 at deterministic byte boundaries without losing any bytes."""
        if type(chunk_bytes) is not int or chunk_bytes <= 0:
            raise ContextPackError("chunk_bytes must be a positive integer")  # noqa: TRY003
        if content is None:
            content = ""
        try:
            if isinstance(content, str):
                raw = content.encode("utf-8")
            elif isinstance(content, bytes):
                content.decode("utf-8")
                raw = content
            else:
                raise ContextPackError("Content must be UTF-8 text or bytes")  # noqa: TRY003
        except UnicodeError as error:
            raise ContextPackError("Content must be valid UTF-8") from error  # noqa: TRY003
        items: list[bytes] = []
        start = 0
        while start < len(raw):
            end = min(start + chunk_bytes, len(raw))
            while end < len(raw) and end > start and raw[end] & 0xC0 == 0x80:
                end -= 1
            if end == start:
                raise ContextPackError("chunk_bytes cannot hold the next UTF-8 character")  # noqa: TRY003
            items.append(raw[start:end])
            start = end
        return cls.build(tuple(items))

    def to_bytes(self) -> bytes:
        """Encode exactly the v1 full-packet fields."""
        return _wire({
            "schema": _PACK_SCHEMA,
            "items": _encode_items(self.items),
            "digest": self.digest,
            "byte_count": self.byte_count,
        })

    @classmethod
    def from_bytes(cls, data: bytes) -> ContextPack:
        """Decode without sender state and verify digest and self-inclusive size."""
        payload = _payload(data, _PACK_SCHEMA, {"schema", "items", "digest", "byte_count"})
        pack = cls.build(_decode_items(payload["items"]))
        if payload["digest"] != pack.digest:
            raise ContextPackError("Packet digest does not match its chunks")  # noqa: TRY003
        if type(payload["byte_count"]) is not int or payload["byte_count"] != pack.byte_count:
            raise ContextPackError("Packet byte_count is incorrect")  # noqa: TRY003
        return pack


@dataclass(frozen=True)
class ContextPackDelta:
    """A reusable base prefix and the target's complete remaining suffix."""

    base_digest: str
    target_digest: str
    prefix_items: int
    appended: tuple[bytes, ...]

    def __post_init__(self) -> None:
        _validate_digest(self.base_digest)
        _validate_digest(self.target_digest)
        if type(self.prefix_items) is not int or self.prefix_items < 0:
            raise ContextPackError("prefix_items must be a nonnegative integer")  # noqa: TRY003
        _validate_items(self.appended)

    @property
    def byte_count(self) -> int:
        """Count all serialized fields without adding a byte_count wire field."""
        return len(self.to_bytes())

    @classmethod
    def between(cls, base: ContextPack, target: ContextPack) -> ContextPackDelta:
        """Reuse the longest identical prefix of the two complete chunk sequences."""
        if not isinstance(base, ContextPack) or not isinstance(target, ContextPack):
            raise ContextPackError("Base and target must be complete ContextPacks")  # noqa: TRY003
        prefix = 0
        for before, after in zip(base.items, target.items, strict=False):
            if before != after:
                break
            prefix += 1
        return cls(base.digest, target.digest, prefix, target.items[prefix:])

    def to_bytes(self) -> bytes:
        """Encode exactly the v1 delta fields, including standard Base64 chunks."""
        return _wire({
            "schema": _DELTA_SCHEMA,
            "base_digest": self.base_digest,
            "target_digest": self.target_digest,
            "prefix_items": self.prefix_items,
            "appended": _encode_items(self.appended),
        })

    @classmethod
    def from_bytes(cls, data: bytes) -> ContextPackDelta:
        """Decode the delta; base-dependent bounds are verified when applying it."""
        payload = _payload(data, _DELTA_SCHEMA, {"schema", "base_digest", "target_digest", "prefix_items", "appended"})
        return cls(
            cast("str", payload["base_digest"]),
            cast("str", payload["target_digest"]),
            cast("int", payload["prefix_items"]),
            _decode_items(payload["appended"]),
        )


def apply_context_pack_delta(base: ContextPack, delta: ContextPackDelta) -> ContextPack:
    """Verify the base and reconstructed target without shared caches or objects."""
    if not isinstance(base, ContextPack) or not isinstance(delta, ContextPackDelta):
        raise ContextPackError("Expected a complete base pack and a context delta")  # noqa: TRY003
    if base.digest != delta.base_digest:
        raise ContextPackError("Delta base digest does not match")  # noqa: TRY003
    if delta.prefix_items > len(base.items):
        raise ContextPackError("Delta prefix exceeds the base chunk count")  # noqa: TRY003
    target = ContextPack.build(base.items[: delta.prefix_items] + delta.appended)
    if target.digest != delta.target_digest:
        raise ContextPackError("Reconstructed target digest does not match")  # noqa: TRY003
    return target
