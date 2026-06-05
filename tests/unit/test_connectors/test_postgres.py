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


def test_get_odbc_connection_string_builds_correct_format():
    """get_odbc_connection_string() returns ODBC connection string in correct format."""
    conn = PostgresConnector()
    cursor = _FakeCursor(one=("abc123",))
    conn._conn = _FakeConnection(cursor)
    conn._connection_string = "host=localhost port=5432 dbname=test user=myuser password=secret"

    odbc_str = conn.get_odbc_connection_string()

    assert "DRIVER={PostgreSQL Unicode}" in odbc_str
    assert "SERVER=localhost" in odbc_str
    assert "PORT=5432" in odbc_str
    assert "DATABASE=test" in odbc_str
    assert "UID=myuser" in odbc_str
    assert "PWD=secret" in odbc_str
    assert odbc_str.startswith("DRIVER={PostgreSQL Unicode};SERVER=")


def test_get_odbc_connection_string_uses_pgpassword_env_when_no_password_in_dsn():
    """When DSN has no password, PGPASSWORD env var is used."""
    import os
    conn = PostgresConnector()
    cursor = _FakeCursor(one=("abc123",))
    conn._conn = _FakeConnection(cursor)
    conn._connection_string = "host=localhost port=5432 dbname=test user=myuser"

    original_pgpw = os.environ.get("PGPASSWORD")
    try:
        os.environ["PGPASSWORD"] = "env_secret"
        odbc_str = conn.get_odbc_connection_string()
        assert "PWD=env_secret" in odbc_str
    finally:
        if original_pgpw is not None:
            os.environ["PGPASSWORD"] = original_pgpw
        elif "PGPASSWORD" in os.environ:
            del os.environ["PGPASSWORD"]


def test_get_odbc_connection_string_omits_password_when_not_in_dsn_or_env():
    """When neither DSN nor PGPASSWORD has password, PWD is omitted."""
    import os
    conn = PostgresConnector()
    cursor = _FakeCursor(one=("abc123",))
    conn._conn = _FakeConnection(cursor)
    conn._connection_string = "host=localhost port=5432 dbname=test user=myuser"

    original_pgpw = os.environ.get("PGPASSWORD")
    if "PGPASSWORD" in os.environ:
        del os.environ["PGPASSWORD"]

    try:
        odbc_str = conn.get_odbc_connection_string()
        # PWD should not appear when no password available
        assert "PWD=" not in odbc_str
    finally:
        if original_pgpw is not None:
            os.environ["PGPASSWORD"] = original_pgpw


def test_get_odbc_connection_string_parses_host_with_equals():
    """DSN parsing handles host=localhost format."""
    conn = PostgresConnector()
    cursor = _FakeCursor(one=("abc123",))
    conn._conn = _FakeConnection(cursor)
    conn._connection_string = "host=db.example.com port=5433 dbname=proddb user=admin"

    odbc_str = conn.get_odbc_connection_string()

    assert "SERVER=db.example.com" in odbc_str
    assert "PORT=5433" in odbc_str
    assert "DATABASE=proddb" in odbc_str
    assert "UID=admin" in odbc_str


def test_get_capabilities_includes_passthrough_support():
    """get_capabilities() returns supports_passthrough_insert_select=True."""
    conn = PostgresConnector()
    cursor = _FakeCursor(one=("abc123",))
    conn._conn = _FakeConnection(cursor)

    caps = conn.get_capabilities()

    assert caps.supports_passthrough_insert_select is True


def test_get_odbc_connection_string_with_ssl_mode():
    """DSN parsing handles sslmode if present."""
    conn = PostgresConnector()
    cursor = _FakeCursor(one=("abc123",))
    conn._conn = _FakeConnection(cursor)
    conn._connection_string = "host=localhost port=5432 dbname=test user=u password=p sslmode=require"

    odbc_str = conn.get_odbc_connection_string()

    # sslmode is not a standard ODBC param but should not break parsing
    assert "DRIVER={PostgreSQL Unicode}" in odbc_str
    assert "SERVER=localhost" in odbc_str


def test_get_odbc_connection_string_uses_default_port():
    """DSN without port falls back to default 5432."""
    conn = PostgresConnector()
    cursor = _FakeCursor(one=("abc123",))
    conn._conn = _FakeConnection(cursor)
    conn._connection_string = "host=localhost dbname=test user=u"

    odbc_str = conn.get_odbc_connection_string()

    assert "PORT=5432" in odbc_str


def test_connect_stores_connection_string():
    """connect() stores the connection string on the connector."""
    from unittest.mock import patch, MagicMock
    conn = PostgresConnector()
    # Patch psycopg2.connect to avoid real connection
    with patch("psycopg2.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_conn.closed = False
        mock_connect.return_value = mock_conn

        conn.connect("host=localhost dbname=test user=u password=p")

        assert conn._connection_string == "host=localhost dbname=test user=u password=p"
