"""Verify that VBA refactoring fixes are persisted in the database."""
import sys
import win32com.client

src = "D:/JMS/Limbo/excel-and-sql-book/data/db/helper.accdb"

app = win32com.client.Dispatch("Access.Application")
app.OpenCurrentDatabase(src, True)
app.Visible = False

for comp in app.VBE.VBProjects(1).VBComponents:
    if comp.Name == "Form_frmDsnlessConnection":
        cm = comp.CodeModule
        print(f"Total lines: {cm.CountOfLines}")
        code = cm.Lines(1, cm.CountOfLines)

        checks = [
            ("SanitizeCSValue function", "Function SanitizeCSValue"),
            ("ValidateRequiredFields", "Function ValidateRequiredFields"),
            ("checkIsTableHidden (typo fix)", "checkIsTableHidden"),
            ("RefreshLinkedTable preserved", "Sub RefreshLinkedTable"),
            ("SetTableHidden error handler", "Sub SetTableHidden"),
            ("db as parameter", "ByRef db As DAO.Database"),
            ("GetDbType SQLite case", 'Case "SQLite"'),
            ("GetDbType Access case", 'Case "Access"'),
            ("BuildConnectionString ByVal port", "ByVal port As Long"),
            ("TryGetDriver function", "Function TryGetDriver"),
            ("No Option Compare (line 1)", "Option Explicit"),
        ]

        for name, pattern in checks:
            found = pattern in code
            mark = "OK" if found else "MISS"
            print(f"  [{mark}] {name}")

        # Show first 5 lines
        print("\nFirst 5 lines:")
        for i in range(1, 6):
            line = cm.Lines(i, 1)
            if line.strip():
                print(f"  {i}: {line.strip()}")

        # Show GetDbType function
        idx = code.find("Private Function GetDbType")
        if idx >= 0:
            print("\nGetDbType function:")
            end = code.find("End Function", idx) + len("End Function")
            for line in code[idx:end].split("\n"):
                if line.strip():
                    print(f"  {line.strip()}")
        break

app.Quit()
