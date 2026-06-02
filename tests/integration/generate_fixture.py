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

        # Table: type_test — all supported column types
        tbl4 = dao.CreateTableDef("type_test")
        tbl4.Fields.Append(tbl4.CreateField("ID", 4))   # dbLong / AutoNumber PK
        tbl4.Fields.Append(tbl4.CreateField("name", 10, 50))  # dbText
        tbl4.Fields.Append(tbl4.CreateField("active", 1))   # dbBoolean
        tbl4.Fields.Append(tbl4.CreateField("created", 8))  # dbDate
        tbl4.Fields.Append(tbl4.CreateField("price", 6))   # dbCurrency
        tbl4.Fields.Append(tbl4.CreateField("notes", 12))  # dbMemo
        tbl4.Fields.Append(tbl4.CreateField("guid", 15))   # dbGUID
        tbl4.Fields.Append(tbl4.CreateField("rating", 7))   # dbDouble
        tbl4.Fields.Append(tbl4.CreateField("level", 2))    # dbByte
        dao.TableDefs.Append(tbl4)

        # ---- Saved Query: qryCustomerOrders ---------------------------------
        try:
            qry = dao.CreateQueryDef("qryCustomerOrders",
                "SELECT c.ID, c.Name, o.ID AS OrderID, o.Total "
                "FROM customers AS c INNER JOIN orders AS o ON c.ID = o.CustomerID "
                "ORDER BY c.ID")
        except Exception as e:
            print(f"  [WARN] Could not create qryCustomerOrders: {e}")

        # ---- Form: frmMain (with button control) ----------------------------
        # Use LoadFromText — fast, invisible, deterministic
        _create_form_main(access)

        # ---- Form: frmWithCode (with event procedure) -----------------------
        _create_form_with_code(access)

        # ---- Report: rptCustomers -------------------------------------------
        _create_report_customers(access)

        # ---- VBA Module: modUtilities ----------------------------------------
        _create_vba_module(access)

        # ---- Macro: macTest --------------------------------------------------
        _create_macro_test(access)

        dao.TableDefs.Refresh()

        # Seed data — INSERT via SQL strings through DAO
        dao.Execute("INSERT INTO customers (ID, Name) VALUES (1, 'Alice')")
        dao.Execute("INSERT INTO customers (ID, Name) VALUES (2, 'Bob')")
        dao.Execute("INSERT INTO customers (ID, Name) VALUES (3, 'Charlie')")

        dao.Execute("INSERT INTO orders (ID, CustomerID, Total) VALUES (1, 1, 99.99)")
        dao.Execute("INSERT INTO orders (ID, CustomerID, Total) VALUES (2, 1, 149.50)")
        dao.Execute("INSERT INTO orders (ID, CustomerID, Total) VALUES (3, 2, 75.00)")

        dao.Execute("INSERT INTO products (ID, Name, Price) VALUES (1, 'Widget', 19.99)")
        dao.Execute("INSERT INTO products (ID, Name, Price) VALUES (2, 'Gadget', 49.99)")

        # type_test rows — mixed NULLs
        # Use simpler date format and bracket all column names
        dao.Execute("INSERT INTO type_test (ID, name, active) VALUES (1, 'Item One', -1)")
        dao.Execute("INSERT INTO type_test (ID, name, active) VALUES (2, 'Item Two', 0)")
        dao.Execute("INSERT INTO type_test (ID, name, active) VALUES (3, 'Item Three', -1)")
        dao.Execute("UPDATE type_test SET [guid] = {550e8400-e29b-41d4-a716-446655440000}, [created] = #2024-01-15#, [price] = 123.45, [rating] = 4.5, [level] = 2 WHERE [ID] = 1")
        dao.Execute("UPDATE type_test SET [notes] = 'First item notes' WHERE [ID] = 1")
        dao.Execute("UPDATE type_test SET [guid] = {6ba7b810-9dad-11d1-80b4-00c04fd430c8}, [created] = #2024-03-20#, [price] = 999.99, [rating] = 3.0, [level] = 5 WHERE [ID] = 3")
        dao.Execute("UPDATE type_test SET [notes] = 'Another item with longer notes here' WHERE [ID] = 3")
        dao.Execute("UPDATE type_test SET [guid] = {f47ac10b-58cc-4372-a567-0e02b2c3d479} WHERE [ID] = 2")

        print(f"Test database created: {OUTPUT_PATH}")
        print("Tables: customers, orders, products, type_test")
        print("Objects: qryCustomerOrders, frmMain, frmWithCode, rptCustomers, modUtilities, macTest")
    finally:
        access.Quit()


# ---------------------------------------------------------------------------
# Helper functions — create Access objects via LoadFromText
# UTF-16-LE BOM is required; Access expects this format for LoadFromText/LoadFromText
# ---------------------------------------------------------------------------

def _utf16_le_bom() -> bytes:
    return b"\xff\xfe"


def _create_form_main(access) -> None:
    """Create frmMain: label + textbox + command button."""
    # acForm = 2
    form_text = (
        "Attribute VB_Name = \"Form_frmMain\"\r\n"
        "Option Compare Database\r\n"
        "\r\n"
        "Begin Form\r\n"
        " Width = 4.5\r\n"
        " Height = 1.8\r\n"
        " RecordSource = \"customers\"\r\n"
        " DefaultView = 0\r\n"
        " Width = 4.5\r\n"
        " Height = 1.8\r\n"
        " End\r\n"
        "Begin TextBox\r\n"
        " Name = \"txtName\"\r\n"
        " Left = 1.2\r\n"
        " Top = 0.6\r\n"
        " Width = 2\r\n"
        " ControlSource = \"Name\"\r\n"
        " End\r\n"
        "Begin Label\r\n"
        " Name = \"lblTitle\"\r\n"
        " Left = 0.2\r\n"
        " Top = 0.1\r\n"
        " Caption = \"Customer Name\"\r\n"
        " Width = 1\r\n"
        " End\r\n"
        "Begin CommandButton\r\n"
        " Name = \"cmdGreet\"\r\n"
        " Left = 1.2\r\n"
        " Top = 1.2\r\n"
        " Width = 1\r\n"
        " Caption = \"Greet\"\r\n"
        " End\r\n"
    )
    _load_object_safe(access, 2, "frmMain", form_text)


def _create_form_with_code(access) -> None:
    """Create frmWithCode: form with cmdHello that has a Click event procedure."""
    form_text = (
        "Attribute VB_Name = \"Form_frmWithCode\"\r\n"
        "Option Compare Database\r\n"
        "\r\n"
        "Begin Form\r\n"
        " Width = 3\r\n"
        " Height = 1.5\r\n"
        " End\r\n"
        "Begin CommandButton\r\n"
        " Name = \"cmdHello\"\r\n"
        " Left = 0.8\r\n"
        " Top = 0.5\r\n"
        " Width = 1.2\r\n"
        " Caption = \"Say Hello\"\r\n"
        " End\r\n"
    )
    _load_object_safe(access, 2, "frmWithCode", form_text)

    # Inject the click event handler via VBA module
    try:
        vbe = access.VBE
        proj = vbe.VBProjects(1)
        mod_name = "Form_frmWithCode"
        for comp in proj.VBComponents:
            if comp.Name == mod_name:
                cm = comp.CodeModule
                # Add the event procedure after existing content
                lines = cm.CountOfLines
                if lines > 0:
                    cm.DeleteLines(1, lines)
                cm.AddFromString(
                    "Option Compare Database\r\n\r\n"
                    "Private Sub cmdHello_Click()\r\n"
                    "    MsgBox \"Hello, World!\", vbInformation, \"Greeting\"\r\n"
                    "End Sub\r\n"
                )
                break
    except Exception as e:
        print(f"  [WARN] Could not inject VBA code into frmWithCode: {e}")


def _create_report_customers(access) -> None:
    """Create rptCustomers: a simple report bound to customers table."""
    # acReport = 4
    report_text = (
        "Attribute VB_Name = \"Report_rptCustomers\"\r\n"
        "Option Compare Database\r\n"
        "\r\n"
        "Begin Report\r\n"
        " Title = \"Customers Report\"\r\n"
        " Width = 4.5\r\n"
        " Height = 2\r\n"
        " RecordSource = \"customers\"\r\n"
        " End\r\n"
        "Begin Label\r\n"
        " Name = \"lblReportTitle\"\r\n"
        " Left = 0.2\r\n"
        " Top = 0.2\r\n"
        " Caption = \"Customer Report\"\r\n"
        " Width = 2\r\n"
        " End\r\n"
        "Begin TextBox\r\n"
        " Name = \"txtCustomerName\"\r\n"
        " Left = 0.2\r\n"
        " Top = 0.8\r\n"
        " Width = 2\r\n"
        " ControlSource = \"Name\"\r\n"
        " End\r\n"
    )
    _load_object_safe(access, 4, "rptCustomers", report_text)


def _create_vba_module(access) -> None:
    """Create modUtilities: a standard module with a public function and sub."""
    # acModule = 5
    module_text = (
        "Attribute VB_Name = \"modUtilities\"\r\n"
        "Option Compare Database\r\n"
        "\r\n"
        "Public Function Hello() As String\r\n"
        "    Hello = \"Hello from modUtilities!\"\r\n"
        "End Function\r\n"
        "\r\n"
        "Public Function AddTwo(ByVal a As Long, ByVal b As Long) As Long\r\n"
        "    AddTwo = a + b\r\n"
        "End Function\r\n"
        "\r\n"
        "Public Sub SayGoodbye()\r\n"
        "    Debug.Print \"Goodbye from modUtilities\"\r\n"
        "End Sub\r\n"
    )
    _load_object_safe(access, 5, "modUtilities", module_text)


def _create_macro_test(access) -> None:
    """Create macTest: a simple macro with a MessageBox action."""
    # acMacro = 8
    macro_text = (
        "Attribute VB_Name = \"macTest\"\r\n"
        "Version = 1.0\r\n"
        "Begin Macro\r\n"
        " Action = 5\r\n"
        " Arguments = 21, \"Test macro is working!\", 1, \"\", 0\r\n"
        " End\r\n"
    )
    _load_object_safe(access, 8, "macTest", macro_text)


def _load_object_safe(access, object_type: int, object_name: str, text_data: str) -> None:
    """Write text data to a temp file and call LoadFromText; print warning on failure.

    LoadFromText is the most reliable way to inject forms/reports/macros/modules
    because it uses the same serialization format Access uses for SaveAsText.
    """
    import tempfile
    temp_path = None
    try:
        fd, temp_path = tempfile.mkstemp(suffix=".txt", prefix="acc_fix_")
        os.close(fd)
        with open(temp_path, "wb") as f:
            f.write(_utf16_le_bom())
            f.write(text_data.encode("utf-16-le"))
        access.LoadFromText(object_type, object_name, temp_path)
        print(f"  [OK] {object_name} created")
    except Exception as e:
        print(f"  [WARN] Could not create {object_name}: {e}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass


if __name__ == "__main__":
    main()
