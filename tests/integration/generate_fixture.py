"""
Generate a test .accdb database for integration tests.

Creates a full-featured fixture DB with tables, saved queries, VBA modules,
forms, reports, and macros.

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
        tbl.Fields.Append(tbl.CreateField("Email", 10, 255))  # dbText
        dao.TableDefs.Append(tbl)

        # Table: orders
        tbl2 = dao.CreateTableDef("orders")
        tbl2.Fields.Append(tbl2.CreateField("ID", 4))
        tbl2.Fields.Append(tbl2.CreateField("CustomerID", 4))
        tbl2.Fields.Append(tbl2.CreateField("OrderDate", 8))  # dbDateTime
        tbl2.Fields.Append(tbl2.CreateField("Total", 6))  # dbCurrency
        dao.TableDefs.Append(tbl2)

        # Table: products
        tbl3 = dao.CreateTableDef("products")
        tbl3.Fields.Append(tbl3.CreateField("ID", 4))
        tbl3.Fields.Append(tbl3.CreateField("Name", 10, 255))
        tbl3.Fields.Append(tbl3.CreateField("Price", 7))  # dbDouble
        dao.TableDefs.Append(tbl3)

        # Saved query: qryCustomerOrders
        qry = dao.CreateQueryDef(
            "qryCustomerOrders",
            (
                "SELECT customers.Name, orders.ID, orders.Total, orders.OrderDate "
                "FROM customers INNER JOIN orders ON customers.ID = orders.CustomerID"
            ),
        )

        # Create a standard VBA module: modUtilities
        # Use LoadFromText with a text representation of the module
        vba_code = (
            "Version 1.0 Begin VBA\n"
            "Function AddTwo(a As Long, b As Long) As Long\n"
            "    AddTwo = a + b\n"
            "End Function\n"
            "Sub Hello()\n"
            '    MsgBox "Hello from modUtilities"\n'
            "End Sub\n"
            "End VBA\n"
        )

        # Create the module file path
        import tempfile

        fd, mod_path = tempfile.mkstemp(suffix=".bas", prefix="modUtilities_")
        os.close(fd)
        try:
            with open(mod_path, "wb") as f:
                # Write UTF-16-LE with BOM (what Access expects)
                f.write(b"\xff\xfe")
                f.write(vba_code.encode("utf-16-le"))
            access.LoadFromText(5, "modUtilities", mod_path)  # acModule = 5
        finally:
            os.unlink(mod_path)

        # Create a simple form: frmMain
        # Form with TextBox (txtName), Label (lblTitle), CommandButton (cmdGreet)
        form_text = (
            "Begin Form frmMain\n"
            "    Caption = \"Test Form\"\n"
            "    Width = 10\n"
            "    Height = 5\n"
            "    Begin Label lblTitle\n"
            "        Caption = \"Welcome\"\n"
            "        Left = 1\n"
            "        Top = 1\n"
            "        Width = 5\n"
            "        Height = 0.5\n"
            "    End\n"
            "    Begin TextBox txtName\n"
            "        Name = \"txtName\"\n"
            "        Left = 1\n"
            "        Top = 2\n"
            "        Width = 5\n"
            "        Height = 0.5\n"
            "    End\n"
            "    Begin CommandButton cmdGreet\n"
            "        Name = \"cmdGreet\"\n"
            "        Caption = \"Greet\"\n"
            "        Left = 1\n"
            "        Top = 3\n"
            "        Width = 2\n"
            "        Height = 0.5\n"
            "    End\n"
            "End Form\n"
        )

        fd, form_path = tempfile.mkstemp(suffix=".txt", prefix="frmMain_")
        os.close(fd)
        try:
            with open(form_path, "wb") as f:
                f.write(b"\xff\xfe")
                f.write(form_text.encode("utf-16-le"))
            access.LoadFromText(2, "frmMain", form_path)  # acForm = 2
        finally:
            os.unlink(form_path)

        # Create a form with embedded VBA code: frmWithCode
        # Create the form without code first
        frm_code_form_text = (
            "Begin Form frmWithCode\n"
            "    Caption = \"Form With Code\"\n"
            "    Width = 10\n"
            "    Height = 5\n"
            "    Begin CommandButton cmdHello\n"
            "        Name = \"cmdHello\"\n"
            "        Caption = \"Say Hello\"\n"
            "        Left = 1\n"
            "        Top = 1\n"
            "        Width = 2\n"
            "        Height = 0.5\n"
            "    End\n"
            "End Form\n"
        )

        fd, frm_code_path = tempfile.mkstemp(suffix=".txt", prefix="frmWithCode_")
        os.close(fd)
        try:
            with open(frm_code_path, "wb") as f:
                f.write(b"\xff\xfe")
                f.write(frm_code_form_text.encode("utf-16-le"))
            access.LoadFromText(2, "frmWithCode", frm_code_path)
        finally:
            os.unlink(frm_code_path)

        # Now add VBA code to frmWithCode's module
        # Access names form code modules as "Form_<form_name>"
        vbe = access.VBE
        form_module_name = "Form_frmWithCode"
        try:
            for i in range(1, vbe.VBProjects.Count + 1):
                vb_proj = vbe.VBProjects(i)
                for comp in vb_proj.VBComponents:
                    if comp.Name == form_module_name:
                        comp.CodeModule.AddFromString(
                            "Private Sub cmdHello_Click()\n"
                            '    MsgBox "Hello!"\n'
                            "End Sub\n"
                        )
                        break
        except Exception:
            # If we can't add code, continue without it
            pass

        # Create a simple report: rptCustomers
        report_text = (
            "Begin Report rptCustomers\n"
            "    Caption = \"Customers Report\"\n"
            "    Width = 10\n"
            "    Height = 5\n"
            "    Begin Label lblName\n"
            "        Caption = \"Customer Name\"\n"
            "        Left = 1\n"
            "        Top = 1\n"
            "        Width = 3\n"
            "        Height = 0.5\n"
            "    End\n"
            "End Report\n"
        )

        fd, report_path = tempfile.mkstemp(suffix=".txt", prefix="rptCustomers_")
        os.close(fd)
        try:
            with open(report_path, "wb") as f:
                f.write(b"\xff\xfe")
                f.write(report_text.encode("utf-16-le"))
            access.LoadFromText(4, "rptCustomers", report_path)  # acReport = 4
        finally:
            os.unlink(report_path)

        # Create a simple macro: macTest
        # Access macros are saved as acMacro = 8
        # A simple macro that runs a beep
        macro_text = (
            "Version 1.0\n"
            "Begin Macro\n"
            '    Condition = ""\n'
            '    Action = "Beep"\n'
            "    Arguments\n"
            "End Macro\n"
        )

        fd, macro_path = tempfile.mkstemp(suffix=".txt", prefix="macTest_")
        os.close(fd)
        try:
            with open(macro_path, "wb") as f:
                f.write(b"\xff\xfe")
                f.write(macro_text.encode("utf-16-le"))
            access.LoadFromText(8, "macTest", macro_path)  # acMacro = 8
        finally:
            os.unlink(macro_path)

        print(f"Test database created: {OUTPUT_PATH}")
        print("Tables: customers, orders, products")
        print("Query: qryCustomerOrders")
        print("Module: modUtilities")
        print("Forms: frmMain, frmWithCode")
        print("Report: rptCustomers")
        print("Macro: macTest")
    finally:
        access.Quit()


if __name__ == "__main__":
    main()