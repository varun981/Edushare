"""Export the SQLAlchemy models as a MySQL init script.

Usage: python tools/export_mysql_schema.py
The output is written to database/init_mysql.sql and contains no credentials.
"""
from __future__ import annotations

from pathlib import Path
import sys

from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateIndex, CreateTable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

DIALECT = mysql.dialect()
HEADER = """-- EduShare MySQL schema.
-- Generated from app/models.py with `python tools/export_mysql_schema.py`.
-- Run against an existing database after creating the database and user yourself.
-- The application also creates missing tables when AUTO_CREATE_TABLES=1.
--
-- Example (substitute your own values):
--   mysql -h DB_HOST -u DB_USER -p DB_NAME < database/init_mysql.sql

CREATE DATABASE IF NOT EXISTS edushare
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE edushare;

SET FOREIGN_KEY_CHECKS = 0;

"""

FOOTER = "SET FOREIGN_KEY_CHECKS = 1;\n"


def main() -> None:
    app = create_app("testing")
    with app.app_context():
        statements = []
        for table in db.metadata.sorted_tables:
            ddl = str(CreateTable(table, if_not_exists=True).compile(dialect=DIALECT)).strip()
            if not ddl.endswith(";"):
                ddl += ";"
            # Keep MySQL's InnoDB engine but enforce Unicode-safe defaults.
            ddl = ddl[:-1].rstrip() + " DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;"
            statements.append(ddl)
            for index in table.indexes:
                statements.append(
                    str(CreateIndex(index).compile(dialect=DIALECT)).strip().rstrip(";") + ";"
                )

    output = Path(__file__).resolve().parents[1] / "database" / "init_mysql.sql"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(HEADER + "\n\n".join(statements) + "\n\n" + FOOTER, encoding="utf-8")
    print(f"Wrote {output} ({len(statements)} DDL statements)")


if __name__ == "__main__":
    main()
