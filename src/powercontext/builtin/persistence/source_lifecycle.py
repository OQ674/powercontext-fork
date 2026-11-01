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

"""Durable dependency bindings and Topic recall eligibility."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Table, insert, select, update
from sqlalchemy.sql import ColumnElement

from powercontext.builtin.persistence.database import AsyncDatabase
from powercontext.builtin.persistence.tables import SOURCE_LIFECYCLE_NODES_TABLE as NODES


def topic_lifecycle_eligible(topic: Table) -> ColumnElement[bool]:
    """Exclude withdrawn Topics before ranking or limiting recall candidates."""
    return (
        ~select(NODES.c.node_id)
        .where(
            NODES.c.scope_id == topic.c.scope_id,
            NODES.c.topic_artifact_id == topic.c.artifact_id,
            NODES.c.available.is_(False),
        )
        .correlate(topic)
        .exists()
    )


class SourceLifecycleRepository:
    """Persist graph state independently of retryable native Memory writes."""

    def __init__(self, database: AsyncDatabase) -> None:
        self.database = database

    async def load(self, scope_id: str) -> tuple[str, ...]:
        async with self.database.transaction() as connection:
            return tuple(await connection.scalars(select(NODES.c.payload).where(NODES.c.scope_id == scope_id)))

    async def save(self, scope_id: str, rows: Sequence[tuple[str, str, bool, str | None]]) -> None:
        async with self.database.transaction() as connection:
            existing = set(await connection.scalars(select(NODES.c.node_id).where(NODES.c.scope_id == scope_id)))
            for node_id, payload, available, topic_artifact_id in rows:
                values = {"payload": payload, "available": available, "topic_artifact_id": topic_artifact_id}
                if node_id in existing:
                    await connection.execute(
                        update(NODES)
                        .where(
                            NODES.c.scope_id == scope_id,
                            NODES.c.node_id == node_id,
                        )
                        .values(**values)
                    )
                else:
                    await connection.execute(insert(NODES).values(scope_id=scope_id, node_id=node_id, **values))
