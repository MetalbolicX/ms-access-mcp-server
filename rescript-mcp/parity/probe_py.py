import os, json
import pyodbc

dbq = os.environ["ACCESS_TEST_DB"]
c = pyodbc.connect(
    r"Driver={Microsoft Access Driver (*.mdb, *.accdb)};Dbq=" + dbq + ";"
)
cur = c.cursor()

# Probe several candidate table names that might exist in the fixture
candidates = [
    "Customers", "Orders", "Products", "OrderDetails", "OrderItems",
    "Category", "Categories", "Supplier", "Suppliers",
    "Employees", "Shippers", "Regions",
]
schema = {}
for tname in candidates:
    try:
        cur.execute(f"SELECT * FROM [{tname}] WHERE 1=0")
        cols = [d[0] for d in cur.description]
        cur.execute(f"SELECT COUNT(*) FROM [{tname}]")
        n = cur.fetchone()[0]
        schema[tname] = {"columns": cols, "row_count": n}
    except Exception as e:
        schema[tname] = {"error": repr(e)[:120]}

c.close()
print(json.dumps({"connected": True, "dbq": dbq, "schema": schema}, indent=2))