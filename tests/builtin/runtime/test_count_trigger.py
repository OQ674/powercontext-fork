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

"""Persistent count eligibility and atomic, bounded automatic admission."""

from __future__ import annotations

import asyncio
from functools import partial

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from typing_extensions import override

from powercontext.builtin.persistence.cursors import SourceCursorRepository
from powercontext.builtin.persistence.processing_intents import (
    ArtifactProcessingIntentRepository,
    StoredArtifactProcessingIntent,
)
from powercontext.builtin.persistence.sources import SourceRepository
from powercontext.builtin.runtime import artifact_processing as processing
from powercontext.builtin.runtime.artifact_processing import ArtifactProcessingBinding, ArtifactProcessingSupervisor
from powercontext.builtin.runtime.family_processing import FAMILY_BINDINGS
from powercontext.builtin.runtime.processing_contracts import ArtifactProcessingWorkerCompletion
from powercontext.builtin.runtime.processing_discovery import SourceProcessingPendingProvider
from powercontext.builtin.runtime.processing_execution import ScopeInvocation
from powercontext.builtin.sources import BUILTIN_SOURCE_REGISTRY, ContentCapture, SourceCursor
from tests.builtin.runtime.test_processing_scheduler import _intent, _Launcher, _profile, _request, _wait


async def _capture(database, scope: str, index: int) -> None:
    source = await BUILTIN_SOURCE_REGISTRY.resolve(
        ContentCapture(source_id=f"turn-{index}", content=f"Evidence turn {index} " + "正文" * index)
    )
    async with database.transaction() as connection:
        await SourceRepository(BUILTIN_SOURCE_REGISTRY).add(connection, scope, source)


@pytest.mark.asyncio
async def test_count_reads_independent_persistent_family_cursors_and_unique_identities(tmp_path) -> None:
    binding = FAMILY_BINDINGS["memory"]
    async with _profile(tmp_path, "count-cursors") as profile:
        for scope, count in [("left", 5), ("right", 2)]:
            for index in range(count):
                await _capture(profile.database, scope, index)
                await _capture(profile.database, scope, index)
        async with profile.database.transaction() as connection:
            await SourceCursorRepository().save(
                connection, "left", binding, SourceCursor(sequence=3), expected_generation=None
            )
        provider = SourceProcessingPendingProvider(profile.database, binding, "memory")
        topic = SourceProcessingPendingProvider(profile.database, "topic-memory-source-window", "topic-memory")
        async with profile.database.transaction() as connection:
            assert await provider.count_ready(connection, ("left", "right", "absent"), threshold=3) == frozenset()
            assert await provider.count_ready(connection, ("left", "right"), threshold=2) == {"left", "right"}
            assert await topic.count_ready(connection, ("left", "right"), threshold=3) == {"left"}
    async with _profile(tmp_path, "count-cursors") as profile:
        provider = SourceProcessingPendingProvider(profile.database, binding, "memory")
        async with profile.database.transaction() as connection:
            assert await provider.count_ready(connection, ("left", "right"), threshold=3) == frozenset()


@pytest.mark.asyncio
async def test_memory_large_backlog_rechecks_after_every_window_then_explicit_request_bypasses_count(tmp_path) -> None:
    binding = FAMILY_BINDINGS["memory"]
    async with _profile(tmp_path, "count-backlog") as profile:
        for index in range(8):
            await _capture(profile.database, "scope", index)
        cursors = SourceCursorRepository()

        async def consume_window(work):
            async with profile.database.transaction() as connection:
                invocation = ScopeInvocation(work)
                await invocation.start(connection)
                current = await cursors.load(connection, work.scope_id, binding)
                before = 0 if current is None else current.cursor.sequence
                high = await SourceRepository(BUILTIN_SOURCE_REGISTRY).journal_position(connection, work.scope_id)
                after = min(high, before + 2)
                await cursors.save(
                    connection,
                    work.scope_id,
                    binding,
                    SourceCursor(sequence=after),
                    expected_generation=None if current is None else current.generation,
                )
                await invocation.complete(connection, remaining_work=after < high)
            return ArtifactProcessingWorkerCompletion()

        launcher = _Launcher(profile.database, on_work=consume_window)
        provider = SourceProcessingPendingProvider(profile.database, binding, "memory")
        supervisor = ArtifactProcessingSupervisor(
            database=profile.database,
            bindings=(
                ArtifactProcessingBinding(
                    binding,
                    "memory",
                    launcher,
                    automatic_count_filter=partial(provider.count_ready, threshold=3),
                ),
            ),
            lease_mode="single-process",
        )
        await supervisor.start()
        try:
            await _wait(lambda: len(launcher.assignments) == 3)
            async with asyncio.timeout(5):
                while (await _intent(profile.database, binding, "scope")).handled_generation != 3:  # noqa: ASYNC110
                    await asyncio.sleep(0.01)
            await asyncio.sleep(1.1)
            assert len(launcher.assignments) == 3
            async with profile.database.transaction() as connection:
                current = await cursors.load(connection, "scope", binding)
                assert current is not None and current.cursor.sequence == 6
                await ArtifactProcessingIntentRepository().request(connection, "scope", binding)
            supervisor.wake(binding)
            await _wait(lambda: len(launcher.assignments) == 4)
            async with asyncio.timeout(5):
                while (await _intent(profile.database, binding, "scope")).handled_generation != 4:  # noqa: ASYNC110
                    await asyncio.sleep(0.01)
            async with profile.database.transaction() as connection:
                current = await cursors.load(connection, "scope", binding)
                assert current is not None and current.cursor.sequence == 8
        finally:
            await supervisor.close()


class _AdmissionRollback(Exception):
    pass


class _FailingRequests(ArtifactProcessingIntentRepository):
    fail_once = False

    @override
    async def request(
        self, connection: AsyncConnection, scope_id: str, binding_name: str, /
    ) -> StoredArtifactProcessingIntent:
        result = await super().request(connection, scope_id, binding_name)
        if self.fail_once and scope_id == "b":
            self.fail_once = False
            raise _AdmissionRollback
        return result


@pytest.mark.asyncio
@pytest.mark.parametrize("boundary", ["eligibility", "request"])
async def test_count_page_rollback_keeps_requests_atomic_and_all_scopes_reachable(
    tmp_path, monkeypatch, boundary
) -> None:
    monkeypatch.setattr(processing, "_DISCOVERY_PAGE_SIZE", 2)
    async with _profile(tmp_path, "count-rollback") as profile:
        for scope in ("a", "b", "c", "d", "e"):
            await _request(profile.database, "memory-binding", scope, requested=False)
        fail_filter = boundary == "eligibility"

        async def eligible(connection, scopes):
            nonlocal fail_filter
            if fail_filter:
                fail_filter = False
                raise _AdmissionRollback
            return frozenset(scopes)

        intents = _FailingRequests()
        intents.fail_once = boundary == "request"
        launcher = _Launcher(profile.database)
        supervisor = ArtifactProcessingSupervisor(
            database=profile.database,
            bindings=(
                ArtifactProcessingBinding(
                    "memory-binding",
                    "memory",
                    launcher,
                    max_workers=2,
                    automatic_count_filter=eligible,
                ),
            ),
            lease_mode="single-process",
            intents=intents,
        )
        await supervisor._acquire()
        state = supervisor._families["memory-binding"]
        try:
            with pytest.raises(_AdmissionRollback):
                await supervisor._discover_count(state)
            for scope in ("a", "b", "c", "d", "e"):
                assert (await _intent(profile.database, "memory-binding", scope)).requested_generation == 0
            for _ in range(4):
                state.next_count_scan_at = 0
                await supervisor._discover_count(state)
                await supervisor._dispatch(state)
                await asyncio.gather(*(running.task for running in state.running.values()))
                await supervisor._reap(state)
            assert sorted(item.scope_id for item in launcher.assignments) == ["a", "b", "c", "d", "e"]
        finally:
            await supervisor._lose_leadership()
