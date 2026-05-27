from ms_access_mcp.connectors.sqlite import SqliteConnector
from ms_access_mcp.models.migration import TableSchema, ColumnSchema


class _FakeCursor:
    def __init__(self, rows=None, one=None):
        self._rows = rows or []
        self._one = one
        self.executed: list[tuple[str, tuple | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, sql: str, params=None):
        self.executed.append((sql, params))

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._rows


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

def test_sqlite_connector_instantiation():
    conn = SqliteConnector()
    assert conn.target_type == "sqlite"

def test_sqlite_table_ddl():
    conn = SqliteConnector()
    table = TableSchema(name="Customers", columns=[
        ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True),
        ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False),
    ], primary_key=["ID"])
    ddl = conn.generate_ddl(table)
    assert "CREATE TABLE" in ddl


def test_sqlite_capabilities_and_linked_contract():
    conn = SqliteConnector()
    capabilities = conn.get_capabilities()

    assert capabilities.supports_linked_insert_select is False
    assert capabilities.supports_checksum is False
    assert capabilities.supports_sampling is True


def test_sqlite_checksum_returns_none_and_sample_query_is_deterministic():
    conn = SqliteConnector()
    cursor = _FakeCursor(rows=[(1, "Alice"), (2, "Bob")])
    conn._conn = _FakeConnection(cursor)

    checksum = conn.get_checksum("Customers", ["ID", "Name"])
    sample = conn.sample_rows("Customers", ["ID", "Name"], limit=2)

    assert checksum is None
    assert sample == [{"ID": 1, "Name": "Alice"}, {"ID": 2, "Name": "Bob"}]
    assert "order by" in cursor.executed[0][0].lower()
