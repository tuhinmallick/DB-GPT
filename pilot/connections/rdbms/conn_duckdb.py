from typing import Optional, Any, Iterable
from sqlalchemy import (
    MetaData,
    Table,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.ext.declarative import declarative_base

from pilot.connections.rdbms.base import RDBMSDatabase


class DuckDbConnect(RDBMSDatabase):
    """Connect Duckdb Database fetch MetaData
    Args:
    Usage:
    """

    db_type: str = "duckdb"
    db_dialect: str = "duckdb"

    @classmethod
    def from_file_path(
        cls, file_path: str, engine_args: Optional[dict] = None, **kwargs: Any
    ) -> RDBMSDatabase:
        """Construct a SQLAlchemy engine from URI."""
        _engine_args = engine_args or {}
        return cls(create_engine(f"duckdb:///{file_path}", **_engine_args), **kwargs)

    def get_users(self):
        cursor = self.session.execute(
            text(
                "SELECT * FROM sqlite_master WHERE type = 'table' AND name = 'duckdb_sys_users';"
            )
        )
        users = cursor.fetchall()
        return [(user[0], user[1]) for user in users]

    def get_grants(self):
        return []

    def get_collation(self):
        """Get collation."""
        return "UTF-8"

    def get_charset(self):
        return "UTF-8"

    def get_table_comments(self, db_name):
        cursor = self.session.execute(
            text(
                """
                SELECT name, sql FROM sqlite_master WHERE type='table'
                """
            )
        )
        table_comments = cursor.fetchall()
        return [
            (table_comment[0], table_comment[1]) for table_comment in table_comments
        ]

    def table_simple_info(self) -> Iterable[str]:
        _tables_sql = """
                SELECT name FROM sqlite_master WHERE type='table'
            """
        cursor = self.session.execute(text(_tables_sql))
        tables_results = cursor.fetchall()
        results = []
        for row in tables_results:
            table_name = row[0]
            _sql = f"""
                PRAGMA  table_info({table_name})
            """
            cursor_colums = self.session.execute(text(_sql))
            colum_results = cursor_colums.fetchall()
            table_colums = []
            for row_col in colum_results:
                field_info = list(row_col)
                table_colums.append(field_info[1])

            results.append(f"{table_name}({','.join(table_colums)});")
        return results


if __name__ == "__main__":
    engine = create_engine(
        "duckdb:////Users/tuyang.yhj/Code/PycharmProjects/DB-GPT/pilot/mock_datas/db-gpt-test.db"
    )
    metadata = MetaData(engine)

    results = (
        engine.connect()
        .execute("SELECT name FROM sqlite_master WHERE type='table'")
        .fetchall()
    )

    print(results)

    fields = []
    results2 = engine.connect().execute("""PRAGMA  table_info(user)""").fetchall()
    for row_col in results2:
        field_info = list(row_col)
        fields.append(field_info[1])
    print(fields)
