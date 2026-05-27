"""
Generate a minimal test .accdb database for integration tests.

Usage:
    python tests/integration/generate_fixture.py

Requires Windows with pywin32 and MS Access installed.
Creates tests/integration/fixtures/test_db.accdb.
"""

import os
import sys
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
OUTPUT_PATH = FIXTURE_DIR / "test_db.accdb"


def main() -> None:
    if os.name != "nt":
        print("Fixture generation requires Windows with MS Access installed.", file=sys.stderr)
        sys.exit(1)

    try:
        import win32com.client  # noqa: F401
    except ImportError:
        print("pywin32 is required. Install with: pip install pywin32", file=sys.stderr)
        sys.exit(1)

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    access = win32com.client.Dispatch("Access.Application")
    try:
        access.Visible = False

        # Create a new blank database
        db = access.NewCurrentDatabase(str(OUTPUT_PATH))

        # Create tables via DAO
        dao = access.CurrentDb()

        # Table: customers
        tbl = dao.CreateTableDef("customers")
        tbl.Fields.Append(tbl.CreateField("ID", 4))  # dbLong
        tbl.Fields.Append(tbl.CreateField("Name", 10, 255))  # dbText
        dao.TableDefs.Append(tbl)

        # Table: orders
        tbl2 = dao.CreateTableDef("orders")
        tbl2.Fields.Append(tbl2.CreateField("ID", 4))
        tbl2.Fields.Append(tbl2.CreateField("CustomerID", 4))
        tbl2.Fields.Append(tbl2.CreateField("Total", 6))  # dbCurrency
        dao.TableDefs.Append(tbl2)

        # Table: products
        tbl3 = dao.CreateTableDef("products")
        tbl3.Fields.Append(tbl3.CreateField("ID", 4))
        tbl3.Fields.Append(tbl3.CreateField("Name", 10, 255))
        tbl3.Fields.Append(tbl3.CreateField("Price", 6))
        dao.TableDefs.Append(tbl3)

        print(f"Test database created: {OUTPUT_PATH}")
        print("Tables: customers, orders, products")
    finally:
        access.Quit()


if __name__ == "__main__":
    main()
