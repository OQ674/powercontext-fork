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

"""Propagate Source withdrawal and recovery without rewriting historical bodies."""

# Keep contextual domain validation messages at their failing boundary.
# ruff: noqa: TRY003

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator

from powercontext.artifacts import ArtifactRef, MemoryCitation
from powercontext.builtin.persistence.source_lifecycle import SourceLifecycleRepository
from powercontext.builtin.records import BaseValueNotFoundError
from powercontext.builtin.runtime.models import GetMemoryEntryRequest
from powercontext.builtin.sources import validate_scope_id
from powercontext.sources import SourceRef

if TYPE_CHECKING:
    from powercontext.builtin.persistence.database import AsyncDatabase
    from powercontext.builtin.runtime.application import BuiltinRuntime

_Reference = SourceRef | MemoryCitation | ArtifactRef


class SourceLifecycleError(ValueError):
    """A dependency registration, event, or resolution violates the lifecycle contract."""


class SourceLifecycleEvent(BaseModel):
    """One strictly typed, replayable transition of a registered Source."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    node_id: StrictStr
    revision: Annotated[StrictInt, Field(gt=0)]
    sequence: Annotated[StrictInt, Field(gt=0)]
    available: StrictBool
    reason: StrictStr

    @field_validator("node_id", "reason")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must contain non-whitespace text")
        return value


class _Node(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    node_id: str
    kind: Literal["source", "memory", "topic"]
    reference: _Reference
    parents: tuple[str, ...] = ()
    policy: Literal["all", "any"] = "all"
    revision: int = 1
    available: bool = True
    event: SourceLifecycleEvent | None = None


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceLifecycleError("node_id and parents must be nonblank strings")
    return value


def _propagate(nodes: dict[str, _Node]) -> dict[str, _Node]:
    # Loaded rows need not be in registration order. Resolve the DAG explicitly.
    resolved: dict[str, _Node] = {}
    remaining = dict(nodes)
    while remaining:
        ready = [node for node in remaining.values() if all(parent in resolved for parent in node.parents)]
        if not ready:
            raise SourceLifecycleError("dependency graph has a missing parent or cycle")
        for node in ready:
            if node.kind != "source":
                support = [resolved[parent].available for parent in node.parents]
                node = node.model_copy(update={"available": all(support) if node.policy == "all" else any(support)})
            resolved[node.node_id] = node
            del remaining[node.node_id]
    return resolved


class ScopedSourceLifecycle:
    """Coordinate one immutable dependency graph under the Runtime's scope lock."""

    def __init__(self, runtime: BuiltinRuntime, repository: SourceLifecycleRepository | None, scope_id: str) -> None:
        self._runtime = runtime
        self._repository = repository
        self.scope_id = validate_scope_id(scope_id)

    async def register_source(self, node_id: str, source_ref: SourceRef, *, revision: int = 1) -> None:
        if type(revision) is not int or revision <= 0:
            raise SourceLifecycleError("revision must be a positive integer")
        if not isinstance(source_ref, SourceRef):
            raise SourceLifecycleError("source binding requires a SourceRef")
        await self._register(
            _Node(node_id=_identifier(node_id), kind="source", reference=source_ref, revision=revision)
        )

    async def register_memory(
        self,
        node_id: str,
        citation: MemoryCitation,
        *,
        parents: tuple[str, ...],
        policy: Literal["all", "any"] = "all",
    ) -> None:
        if not isinstance(citation, MemoryCitation):
            raise SourceLifecycleError("memory binding requires a MemoryCitation")
        await self._register(self._derived(node_id, "memory", citation, parents, policy))

    async def register_topic(
        self,
        node_id: str,
        artifact_ref: ArtifactRef,
        *,
        parents: tuple[str, ...],
        policy: Literal["all", "any"] = "all",
    ) -> None:
        if not isinstance(artifact_ref, ArtifactRef) or artifact_ref.family != "topic-memory":
            raise SourceLifecycleError("topic binding requires a topic-memory ArtifactRef")
        await self._register(self._derived(node_id, "topic", artifact_ref, parents, policy))

    @staticmethod
    def _derived(
        node_id: str,
        kind: Literal["memory", "topic"],
        reference: _Reference,
        parents: tuple[str, ...],
        policy: Literal["all", "any"],
    ) -> _Node:
        _identifier(node_id)
        if not isinstance(policy, str) or policy not in {"all", "any"}:
            raise SourceLifecycleError("policy must be all or any")
        if not isinstance(parents, (tuple, list)) or not parents:
            raise SourceLifecycleError("derived nodes require parents")
        normalized = tuple(sorted(_identifier(parent) for parent in parents))
        if len(set(normalized)) != len(normalized) or node_id in normalized:
            raise SourceLifecycleError("duplicate parent or self dependency")
        return _Node(node_id=node_id, kind=kind, reference=reference, parents=normalized, policy=policy)

    async def _load(self) -> dict[str, _Node]:
        if self._repository is None:
            raise SourceLifecycleError("lifecycle persistence is not configured")
        nodes = (_Node.model_validate_json(payload) for payload in await self._repository.load(self.scope_id))
        return {node.node_id: node for node in nodes}

    async def _save(self, nodes: dict[str, _Node]) -> None:
        if self._repository is None:
            raise SourceLifecycleError("lifecycle persistence is not configured")
        await self._repository.save(
            self.scope_id,
            [
                (
                    node.node_id,
                    node.model_dump_json(),
                    node.available,
                    node.reference.artifact_id if isinstance(node.reference, ArtifactRef) else None,
                )
                for node in nodes.values()
            ],
        )

    async def _validate_reference(self, node: _Node) -> None:
        reference = node.reference
        try:
            if isinstance(reference, SourceRef):
                await self._runtime.records.for_scope(self.scope_id).get_source(
                    reference.source_type, reference.source_id
                )
            elif isinstance(reference, MemoryCitation):
                await self._runtime.memory.for_scope(self.scope_id).get(GetMemoryEntryRequest(citation=reference))
            else:
                await self._runtime.records.for_scope(self.scope_id).get_artifact_revision(
                    reference.family,
                    reference.artifact_id,
                    reference.revision,
                )
        except (ValueError, LookupError, BaseValueNotFoundError) as error:
            raise SourceLifecycleError("registered reference must exist and be readable in this scope") from error

    async def _register(self, node: _Node) -> None:
        async with self._runtime._scoped_operation(self.scope_id), self._runtime._locked(self.scope_id):
            nodes = await self._load()
            previous = nodes.get(node.node_id)
            if previous is not None:
                identity = {"available", "event"}
                if previous.model_dump(exclude=identity) != node.model_dump(exclude=identity):
                    raise SourceLifecycleError("node_id is already bound differently")
            elif any(parent not in nodes for parent in node.parents):
                raise SourceLifecycleError("parents must already be registered")
            await self._validate_reference(node)
            if previous is None:
                nodes[node.node_id] = node
                nodes = _propagate(nodes)
                await self._save(nodes)
            await self._reconcile(nodes, reason="dependency registration")

    async def apply(self, event: SourceLifecycleEvent) -> list[str]:
        if not isinstance(event, SourceLifecycleEvent):
            raise SourceLifecycleError("apply requires a SourceLifecycleEvent")
        async with self._runtime._scoped_operation(self.scope_id), self._runtime._locked(self.scope_id):
            nodes = await self._load()
            source = nodes.get(event.node_id)
            if source is None or source.kind != "source" or source.revision != event.revision:
                raise SourceLifecycleError("unknown Source or lifecycle revision mismatch")
            previous = source.event
            if previous is not None and (
                event.sequence < previous.sequence or (event.sequence == previous.sequence and event != previous)
            ):
                raise SourceLifecycleError("event sequence is stale or conflicts with the accepted event")
            if previous != event:
                nodes[event.node_id] = source.model_copy(update={"available": event.available, "event": event})
                nodes = _propagate(nodes)
                # Write intent before native updates: retry after a partial write
                # reconciles actual Memory state rather than skipping this event.
                await self._save(nodes)
            await self._reconcile(nodes, reason=event.reason)
            return sorted(node.node_id for node in nodes.values() if node.available)

    async def _reconcile(self, nodes: dict[str, _Node], *, reason: str) -> None:
        # The complete event reason remains durable; Memory's audit field has
        # its own 512-character limit and NFC normalization contract.
        memory_reason = unicodedata.normalize("NFC", reason).strip()[:512]
        memories = [node for node in nodes.values() if node.kind == "memory"]
        if not memories:
            return
        async with self._runtime._context(self.scope_id) as context:
            service = context.artifacts.memory
            current = await service.head(context.artifacts.memory_artifact_id)
            for available in (False, True):
                entries = {entry.entry_id: entry for entry in await service.entries(current)}
                states = {item.entry_id: item.state for item in current.content.manifest.entries}
                targets = []
                for node in memories:
                    reference = node.reference
                    if not isinstance(reference, MemoryCitation):
                        raise SourceLifecycleError("invalid persisted Memory binding")
                    entry = entries.get(reference.entry_id)
                    if entry is None or entry.entry_version_id != reference.entry_version_id:
                        raise SourceLifecycleError("registered Memory body was changed externally")
                    if node.available == available and (states[reference.entry_id] == "active") != available:
                        targets.append(entry)
                if targets:
                    operation = service.reactivate if available else service.forget
                    current = await operation(current, entries=targets, reason=memory_reason)

    async def resolve(self, node_id: str, *, purpose: str = "generation") -> _Reference:
        _identifier(node_id)
        if not isinstance(purpose, str) or purpose not in {"generation", "audit"}:
            raise SourceLifecycleError("unknown reference purpose")
        async with self._runtime._scoped_operation(self.scope_id):
            node = (await self._load()).get(node_id)
            if node is None or (purpose == "generation" and not node.available):
                raise SourceLifecycleError("node is unknown or unavailable for generation")
            return node.reference.model_copy(deep=True)


class SourceLifecycleApplication:
    """Select a persistent lifecycle service for one scope."""

    def __init__(self, runtime: BuiltinRuntime, database: AsyncDatabase | None) -> None:
        self._runtime = runtime
        self._repository = None if database is None else SourceLifecycleRepository(database)

    def for_scope(self, scope_id: str) -> ScopedSourceLifecycle:
        return ScopedSourceLifecycle(self._runtime, self._repository, scope_id)
