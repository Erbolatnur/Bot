"""Small PostgreSQL persistence layer for user projects and imported match metadata."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any

import psycopg
from psycopg.rows import dict_row


def database_url() -> str | None:
    return os.getenv("DATABASE_URL")


def available() -> bool:
    return bool(database_url())


def connect():
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return psycopg.connect(url, connect_timeout=8, row_factory=dict_row)


def init_storage() -> None:
    if not available():
        return
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                owner_provider TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'created',
                data JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS projects_owner_updated_idx
            ON projects(owner_provider, owner_id, updated_at DESC)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                provider TEXT NOT NULL,
                match_id TEXT NOT NULL,
                owner_provider TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY(provider, match_id, owner_provider, owner_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS matches_owner_created_idx
            ON matches(owner_provider, owner_id, created_at DESC)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS demos (
                id TEXT PRIMARY KEY,
                owner_provider TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                size_bytes BIGINT NOT NULL,
                sha256 TEXT NOT NULL,
                raw_data BYTEA NOT NULL,
                analysis JSONB NOT NULL DEFAULT '{}'::jsonb,
                status TEXT NOT NULL DEFAULT 'uploaded',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS demos_owner_created_idx
            ON demos(owner_provider, owner_id, created_at DESC)
        """)


def save_match(provider: str, match_id: str, owner_provider: str, owner_id: str,
               payload: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute("""
            INSERT INTO matches(provider, match_id, owner_provider, owner_id, payload)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT(provider, match_id, owner_provider, owner_id)
            DO UPDATE SET payload=EXCLUDED.payload, updated_at=NOW()
        """, (provider, match_id, owner_provider, owner_id, json.dumps(payload)))


def list_matches(owner_provider: str, owner_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("""
            SELECT provider, match_id, payload, created_at, updated_at
            FROM matches WHERE owner_provider=%s AND owner_id=%s
            ORDER BY created_at DESC LIMIT %s
        """, (owner_provider, owner_id, limit)).fetchall()
    return [dict(row) for row in rows]



def demo_storage_usage(owner_provider: str, owner_id: str) -> tuple[int, int]:
    """Return (account bytes, global bytes) used by stored demo files."""
    with connect() as conn:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(size_bytes) FILTER (WHERE owner_provider=%s AND owner_id=%s), 0) AS account_bytes,
                COALESCE(SUM(size_bytes), 0) AS global_bytes
            FROM demos
        """, (owner_provider, owner_id)).fetchone()
    return int(row["account_bytes"]), int(row["global_bytes"])


def save_demo(demo_id: str, owner_provider: str, owner_id: str, filename: str,
              size_bytes: int, sha256: str, raw_data: bytes, analysis: dict[str, Any], status: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("""
            INSERT INTO demos(id, owner_provider, owner_id, filename, size_bytes, sha256, raw_data, analysis, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            RETURNING id, filename, size_bytes, sha256, analysis, status, created_at
        """, (demo_id, owner_provider, owner_id, filename, size_bytes, sha256,
              raw_data, json.dumps(analysis), status)).fetchone()
    return dict(row)


def list_demos(owner_provider: str, owner_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("""
            SELECT id, filename, size_bytes, sha256, analysis, status, created_at
            FROM demos WHERE owner_provider=%s AND owner_id=%s ORDER BY created_at DESC
        """, (owner_provider, owner_id)).fetchall()
    return [dict(row) for row in rows]


def get_demo(owner_provider: str, owner_id: str, demo_id: str, include_data: bool = False) -> dict[str, Any] | None:
    columns = "id, filename, size_bytes, sha256, analysis, status, created_at"
    if include_data:
        columns += ", raw_data"
    with connect() as conn:
        row = conn.execute(f"SELECT {columns} FROM demos WHERE id=%s AND owner_provider=%s AND owner_id=%s",
                           (demo_id, owner_provider, owner_id)).fetchone()
    return dict(row) if row else None


def delete_demo(owner_provider: str, owner_id: str, demo_id: str) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM demos WHERE id=%s AND owner_provider=%s AND owner_id=%s",
                              (demo_id, owner_provider, owner_id))
    return cursor.rowcount > 0

def create_project(owner_provider: str, owner_id: str, title: str,
                   description: str = "", data: dict[str, Any] | None = None) -> dict[str, Any]:
    project_id = str(uuid.uuid4())
    with connect() as conn:
        row = conn.execute("""
            INSERT INTO projects(id, owner_provider, owner_id, title, description, data)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, title, description, status, data, created_at, updated_at
        """, (project_id, owner_provider, owner_id, title, description,
              json.dumps(data or {}))).fetchone()
    return dict(row)


def list_projects(owner_provider: str, owner_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("""
            SELECT id, title, description, status, data, created_at, updated_at
            FROM projects WHERE owner_provider=%s AND owner_id=%s
            ORDER BY updated_at DESC
        """, (owner_provider, owner_id)).fetchall()
    return [dict(row) for row in rows]


def get_project(owner_provider: str, owner_id: str, project_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("""
            SELECT id, title, description, status, data, created_at, updated_at
            FROM projects WHERE id=%s AND owner_provider=%s AND owner_id=%s
        """, (project_id, owner_provider, owner_id)).fetchone()
    return dict(row) if row else None


def update_project(owner_provider: str, owner_id: str, project_id: str,
                   fields: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {"title", "description", "status", "data"}
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return get_project(owner_provider, owner_id, project_id)
    if "data" in updates:
        updates["data"] = json.dumps(updates["data"])
    assignments = []
    values = []
    for key, value in updates.items():
        assignments.append(f"{key}=%s::jsonb" if key == "data" else f"{key}=%s")
        values.append(value)
    values.extend([project_id, owner_provider, owner_id])
    with connect() as conn:
        row = conn.execute(f"""
            UPDATE projects SET {", ".join(assignments)}, updated_at=NOW()
            WHERE id=%s AND owner_provider=%s AND owner_id=%s
            RETURNING id, title, description, status, data, created_at, updated_at
        """, values).fetchone()
    return dict(row) if row else None


def delete_project(owner_provider: str, owner_id: str, project_id: str) -> bool:
    with connect() as conn:
        cursor = conn.execute("""
            DELETE FROM projects WHERE id=%s AND owner_provider=%s AND owner_id=%s
        """, (project_id, owner_provider, owner_id))
    return cursor.rowcount > 0
