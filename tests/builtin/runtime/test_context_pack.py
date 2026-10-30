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

"""Transport interoperability, corruption rejection and UTF-8 boundaries."""

from __future__ import annotations

import base64
import hashlib
import json
import random
import subprocess
import sys
from dataclasses import replace
from itertools import pairwise
from typing import cast

import pytest

from powercontext.builtin.runtime.context_pack import (
    ContextPack,
    ContextPackDelta,
    ContextPackError,
    apply_context_pack_delta,
)


@pytest.mark.parametrize("size", [0, 1, 2, 20, 500, 700, 7400, 7500, 32000])
def test_canonical_wire_matches_independent_digest_and_size(size: int) -> None:
    pack = ContextPack.build((b"x" * size, "海洋🌊\r\n".encode()))
    unsigned = {
        "schema": "powercontext.context-pack.v1",
        "items": [base64.b64encode(item).decode() for item in pack.items],
    }
    digest = (
        "sha256:" + hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    )
    payload = {**unsigned, "digest": digest, "byte_count": len(pack.to_bytes())}
    assert pack.to_bytes() == json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    assert pack.byte_count == len(pack.to_bytes())
    assert ContextPack.from_bytes(pack.to_bytes()) == pack


@pytest.mark.parametrize("limit", [4, 5, 7, 31, 512])
def test_unicode_chunks_are_bounded_lossless_and_deterministic(limit: int) -> None:
    text = "中文e\u0301😀\r\n\t\x00é!" * 75
    pack = ContextPack.from_content(text, chunk_bytes=limit)
    assert pack == ContextPack.from_content(text.encode(), chunk_bytes=limit)
    assert b"".join(pack.items) == text.encode()
    assert all(0 < len(item) <= limit and item.decode().encode() == item for item in pack.items)
    assert ContextPack.from_content(None).items == ContextPack.from_content("").items == ()


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, None, "512"])
def test_invalid_chunk_limits_are_protocol_errors(limit: object) -> None:
    with pytest.raises(ContextPackError):
        ContextPack.from_content("text", chunk_bytes=cast("int", limit))


@pytest.mark.parametrize("content,limit", [("😀", 3), ("海", 2), (b"\xff", 512), ("\ud800", 512)])
def test_invalid_or_unrepresentable_utf8_is_rejected(content: str | bytes, limit: int) -> None:
    with pytest.raises(ContextPackError):
        ContextPack.from_content(content, chunk_bytes=limit)


@pytest.mark.parametrize("value", [[], ("not bytes",), (b"\xff",), (b"\xe6", b"\xb5\xb7")])
def test_build_rejects_invalid_individual_chunks(value: object) -> None:
    with pytest.raises(ContextPackError):
        ContextPack.build(cast("tuple[bytes, ...]", value))


@pytest.mark.parametrize(
    "replacement",
    [None, {}, [None], [42], ["!!!!"], ["YQ"], ["YR=="], ["YQ==\n"], ["_w=="], ["/w=="]],
)
def test_full_and_delta_reject_invalid_base64_or_utf8(replacement: object) -> None:
    base = ContextPack.build((b"alpha",))
    delta = ContextPackDelta.between(base, ContextPack.build((b"beta",)))
    for packet, field, decoder in [
        (base, "items", ContextPack.from_bytes),
        (delta, "appended", ContextPackDelta.from_bytes),
    ]:
        payload = {**json.loads(packet.to_bytes()), field: replacement}
        with pytest.raises(ContextPackError):
            decoder(json.dumps(payload).encode())


def test_exact_fields_duplicates_and_malformed_json_are_rejected() -> None:
    base = ContextPack.build(())
    for packet, decoder in [
        (base, ContextPack.from_bytes),
        (ContextPackDelta.between(base, base), ContextPackDelta.from_bytes),
    ]:
        payload = json.loads(packet.to_bytes())
        for field in payload:
            with pytest.raises(ContextPackError):
                decoder(json.dumps({key: value for key, value in payload.items() if key != field}).encode())
        for bad in [
            json.dumps({**payload, "extra": 0}).encode(),
            json.dumps({**payload, "schema": "wrong"}).encode(),
            b'{"schema":"duplicate",' + packet.to_bytes()[1:],
            b'{"value":NaN}',
            b'{"value":Infinity}',
            b"null",
            b"[]",
            b"{",
            b"\xff",
            packet.to_bytes() + b" trailing",
            packet.to_bytes().decode().encode("utf-16"),
        ]:
            with pytest.raises(ContextPackError):
                decoder(bad)


@pytest.mark.parametrize("count", [True, 1.5, -1, 0, "123", None])
def test_full_packet_validates_self_inclusive_byte_count(count: object) -> None:
    payload = json.loads(ContextPack.build((b"data",)).to_bytes())
    with pytest.raises(ContextPackError):
        ContextPack.from_bytes(json.dumps({**payload, "byte_count": count}).encode())


@pytest.mark.parametrize("prefix", [True, 1.5, -1, "1", None])
def test_delta_validates_prefix_type_and_range(prefix: object) -> None:
    base = ContextPack.build((b"a",))
    payload = json.loads(ContextPackDelta.between(base, base).to_bytes())
    with pytest.raises(ContextPackError):
        ContextPackDelta.from_bytes(json.dumps({**payload, "prefix_items": prefix}).encode())


def test_delta_checks_both_digests_and_base_bounds() -> None:
    base = ContextPack.build((b"a",))
    target = ContextPack.build((b"a", b"b"))
    delta = ContextPackDelta.between(base, target)
    for broken in [replace(delta, prefix_items=2), replace(delta, target_digest="sha256:" + "0" * 64)]:
        with pytest.raises(ContextPackError):
            apply_context_pack_delta(base, broken)
    with pytest.raises(ContextPackError):
        apply_context_pack_delta(target, delta)
    for field in ["base_digest", "target_digest"]:
        for value in [None, 1, "0" * 64, "sha256:" + "g" * 64]:
            with pytest.raises(ContextPackError):
                ContextPackDelta.from_bytes(json.dumps({**json.loads(delta.to_bytes()), field: value}).encode())
    payload = {**json.loads(base.to_bytes()), "digest": "sha256:" + "0" * 64}
    with pytest.raises(ContextPackError):
        ContextPack.from_bytes(json.dumps(payload).encode())


def test_randomized_valid_prefixes_and_edits_reconstruct_exact_targets() -> None:
    rng = random.Random(20261030)  # noqa: S311
    alphabet = [b"a", "海洋".encode(), "🧠".encode(), b"\n", b""]
    base = ContextPack.build(())
    for _ in range(120):
        items = list(base.items)
        position = rng.randrange(len(items) + 1)
        items[position : position + rng.randrange(3)] = rng.choices(alphabet, k=rng.randrange(4))
        target = ContextPack.build(tuple(items))
        proposed = ContextPackDelta.between(base, target)
        # An independent sender may select any shorter valid prefix.
        prefix = rng.randrange(proposed.prefix_items + 1)
        delta = ContextPackDelta(base.digest, target.digest, prefix, target.items[prefix:])
        restored = apply_context_pack_delta(
            ContextPack.from_bytes(base.to_bytes()), ContextPackDelta.from_bytes(delta.to_bytes())
        )
        assert restored == target
        assert delta.byte_count == len(delta.to_bytes())
        base = target


def test_separate_receiver_process_needs_only_serialized_packets() -> None:
    packs = [ContextPack.from_content(text) for text in ["", "海洋\n" * 300, "海洋\n" * 300 + "tail", "changed", ""]]
    packets = [packs[0].to_bytes()] + [ContextPackDelta.between(a, b).to_bytes() for a, b in pairwise(packs)]
    program = """
import base64, json, sys
from powercontext.builtin.runtime.context_pack import ContextPack, ContextPackDelta, apply_context_pack_delta
packets = [base64.b64decode(item) for item in json.load(sys.stdin)]
base = ContextPack.from_bytes(packets[0])
outputs = [base64.b64encode(b''.join(base.items)).decode()]
for wire in packets[1:]:
    base = apply_context_pack_delta(base, ContextPackDelta.from_bytes(wire))
    outputs.append(base64.b64encode(b''.join(base.items)).decode())
json.dump(outputs, sys.stdout)
"""
    received = subprocess.run(
        [sys.executable, "-c", program],
        input=json.dumps([base64.b64encode(packet).decode() for packet in packets]),
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    assert [base64.b64decode(item) for item in json.loads(received.stdout)] == [b"".join(pack.items) for pack in packs]
