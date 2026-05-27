from ms_access_mcp.connectors.sqlserver import SqlServerConnector
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

def test_sqlserver_connector_instantiation():
    conn = SqlServerConnector()
    assert conn.target_type == "sqlserver"

def test_sqlserver_table_ddl():
    conn = SqlServerConnector()
    table = TableSchema(name="Customers", columns=[
        ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True),
        ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False),
    ], primary_key=["ID"])
    ddl = conn.generate_ddl(table)
    assert "CREATE TABLE" in ddl
    assert "INT IDENTITY" in ddl


def test_sqlserver_capabilities_and_linked_contract():
    conn = SqlServerConnector()
    capabilities = conn.get_capabilities()

    assert capabilities.supports_linked_insert_select is False
    assert capabilities.supports_checksum is True
    assert capabilities.supports_sampling is True


def test_sqlserver_checksum_and_sample_queries_are_executed_with_deterministic_ordering():
    conn = SqlServerConnector()
    cursor = _FakeCursor(rows=[(1, "Alice"), (2, "Bob")], one=("abc123",))
    conn._conn = _FakeConnection(cursor)

    checksum = conn.get_checksum("Customers", ["ID", "Name"])
    sample = conn.sample_rows("Customers", ["ID", "Name"], limit=2)

    assert checksum == "abc123"
    assert sample == [{"ID": 1, "Name": "Alice"}, {"ID": 2, "Name": "Bob"}]
    assert "hashbytes" in cursor.executed[0][0].lower()
    assert "order by" in cursor.executed[1][0].lower()
