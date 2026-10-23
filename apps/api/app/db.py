"""Supabase PostgreSQL asyncpg 커넥션 풀.

Supabase Connection Pooler(Supavisor, transaction mode, 포트 6543) 를 쓰면 서버 측 prepared
statement 를 재사용할 수 없으므로 statement_cache_size=0 으로 설정한다.
"""

from __future__ import annotations

import json
import logging

import asyncpg

from app.config import Settings

logger = logging.getLogger(__name__)


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def create_pool(settings: Settings) -> asyncpg.Pool | None:
    if not settings.database_url:
        logger.warning("DATABASE_URL 이 비어 있어 DB 없이 기동합니다 (/health 만 동작).")
        return None
    try:
        return await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=settings.db_pool_min,
            max_size=settings.db_pool_max,
            statement_cache_size=0,
            command_timeout=30,
            init=_init_connection,
        )
    except Exception:  # noqa: BLE001 — DB 장애여도 /health 는 살아 있어야 슬립/재시작 루프를 피함
        logger.exception("DB 풀 생성 실패")
        return None
