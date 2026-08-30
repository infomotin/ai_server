"""One-shot SQLite -> MySQL migration for OpenLocalAI."""
import os
import sys
import json
from datetime import datetime, date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

SQLITE_URL = "sqlite:////www/AI_server/openlocalai.db"
MYSQL_URL = "mysql+pymysql://aiserver:aiserver@localhost:3306/aiserver?charset=utf8mb4"

SKIP_TABLES = {"alembic_version"}

def is_json_col(table, col):
    try:
        with sqlite_inspect.bind.connect() as conn:
            r = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        for row in r:
            if row[1] == col and "JSON" in (row[2] or "").upper():
                return True
    except Exception:
        pass
    return False

def to_jsonable(v):
    if v is None or isinstance(v, (int, float, bool)):
        return v
    if isinstance(v, (datetime, date)):
        return v.isoformat(sep=" ")
    if isinstance(v, str):
        s = v.strip()
        if s.startswith(("{", "[")) and s.endswith(("}", "]")):
            try:
                json.loads(s)
                return s
            except Exception:
                return v
        return v
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode("utf-8", errors="ignore")
        except Exception:
            return str(v)
    return str(v)

def main():
    global sqlite_inspect
    sqlite_eng = create_engine(SQLITE_URL)
    mysql_eng = create_engine(MYSQL_URL, pool_pre_ping=True)
    sqlite_inspect = sqlite_eng

    from sqlalchemy import inspect
    s_inspect = inspect(sqlite_eng)
    m_inspect = inspect(mysql_eng)

    sqlite_tables = [t for t in s_inspect.get_table_names() if t not in SKIP_TABLES]
    mysql_tables = set(m_inspect.get_table_names())
    print(f"SQLite tables: {len(sqlite_tables)}")
    print(f"MySQL tables already: {sorted(mysql_tables)[:5]}…")

    # Step 1: create tables in MySQL using SQLAlchemy metadata
    print("\n[1/3] Creating tables in MySQL…")
    sys.path.insert(0, "/www/AI_server")
    from src.models.database import Base
    Base.metadata.create_all(mysql_eng)
    print("  done.")

    # Step 2: copy data table-by-table
    print("\n[2/3] Copying data…")
    S = sessionmaker(bind=sqlite_eng)()
    M = sessionmaker(bind=mysql_eng)()

    # FK-aware order: tables without FKs first.
    def fk_deps(t):
        try:
            fks = s_inspect.get_foreign_keys(t)
        except Exception:
            fks = []
        return [fk["referred_table"] for fk in fks if fk.get("referred_table")]

    order = []
    seen = set()
    def visit(t):
        if t in seen or t not in sqlite_tables:
            return
        for dep in fk_deps(t):
            visit(dep)
        seen.add(t)
        order.append(t)
    for t in sqlite_tables:
        visit(t)

    for t in order:
        cols = [c["name"] for c in s_inspect.get_columns(t)]
        if not cols:
            continue
        try:
            rows = S.execute(text(f'SELECT * FROM "{t}"')).mappings().all()
        except Exception as e:
            print(f"  ! cannot read {t}: {e}")
            continue
        if not rows:
            print(f"  - {t}: 0 rows")
            continue
        col_list = ", ".join(f"`{c}`" for c in cols)
        placeholders = ", ".join(f":{c}" for c in cols)
        insert_sql = f"INSERT IGNORE INTO `{t}` ({col_list}) VALUES ({placeholders})"
        payload = []
        for row in rows:
            d = {}
            for c in cols:
                v = row[c]
                if is_json_col(t, c):
                    if isinstance(v, str):
                        try:
                            json.loads(v); d[c] = v
                        except Exception:
                            d[c] = json.dumps(v)
                    elif v is None:
                        d[c] = None
                    else:
                        d[c] = json.dumps(v)
                else:
                    d[c] = to_jsonable(v)
            payload.append(d)
        try:
            M.execute(text(insert_sql), payload)
            M.commit()
            print(f"  ✓ {t}: {len(payload)} rows")
        except Exception as e:
            M.rollback()
            print(f"  ✗ {t}: {e}")

    S.close(); M.close()

    # Step 3: verify
    print("\n[3/3] Verifying…")
    m_inspect = inspect(mysql_eng)
    with mysql_eng.connect() as conn:
        for t in sorted(sqlite_tables):
            try:
                s_count = sqlite_eng.connect().execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
                m_count = conn.execute(text(f"SELECT COUNT(*) FROM `{t}`")).scalar()
                mark = "✓" if s_count == m_count else "!"
                print(f"  {mark} {t}: sqlite={s_count} mysql={m_count}")
            except Exception as e:
                print(f"  - {t}: {e}")

    print("\nMigration complete.")

if __name__ == "__main__":
    main()
