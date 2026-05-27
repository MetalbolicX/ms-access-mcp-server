from ms_access_mcp.connectors.postgres import PostgresConnector
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
        self.closed = False

    def cursor(self):
        return self._cursor

def test_postgres_connector_instantiation():
    conn = PostgresConnector()
    assert conn.target_type == "postgres"

def test_postgres_table_ddl():
    conn = PostgresConnector()
    table = TableSchema(name="Customers", columns=[
        ColumnSchema(name="ID", source_type="Long Integer", allow_null=False, is_autoincrement=True),
        ColumnSchema(name="Name", source_type="Text", max_length=255, allow_null=True, is_autoincrement=False),
    ], primary_key=["ID"])
    ddl = conn.generate_ddl(table)
    assert "CREATE TABLE" in ddl
    assert '"ID"' in ddl
    assert "BIGSERIAL" in ddl


def test_postgres_capabilities_and_linked_contract():
    conn = PostgresConnector()
    capabilities = conn.get_capabilities()

    assert capabilities.supports_linked_insert_select is False
    assert capabilities.supports_checksum is True
    assert capabilities.supports_sampling is True


def test_postgres_checksum_and_sample_queries_are_executed_with_deterministic_ordering():
    conn = PostgresConnector()
    cursor = _FakeCursor(rows=[(1, "Alice"), (2, "Bob")], one=("abc123",))
    conn._conn = _FakeConnection(cursor)

    checksum = conn.get_checksum("Customers", ["ID", "Name"])
    sample = conn.sample_rows("Customers", ["ID", "Name"], limit=2)

    assert checksum == "abc123"
    assert sample == [{"ID": 1, "Name": "Alice"}, {"ID": 2, "Name": "Bob"}]
    assert "md5" in cursor.executed[0][0].lower()
    assert "order by" in cursor.executed[1][0].lower()
