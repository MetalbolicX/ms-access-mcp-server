# Fixture inventory - db/northwind.accdb (plan 026 real-database baseline)

Generated: 2026-08-29T00:26:55.134896
File size: 430080 bytes
File mtime: 2026-08-28T23:57:15.460746
Source: db/northwind.accdb (Python oracle)
Driver: `Microsoft Access Driver (*.mdb, *.accdb)` via pyodbc

## User tables (8)

### `Categories` (5 rows)

| Column | Type | Nullable |
|--------|------|----------|
| `CategoryID` | `integer` | no |
| `CategoryName` | `string` | yes |
| `Description` | `string` | yes |
| `Picture` | `pytype_bytearray` | yes |

### `Customers` (5 rows)

| Column | Type | Nullable |
|--------|------|----------|
| `CustomerID` | `integer` | no |
| `CompanyName` | `string` | yes |
| `ContactName` | `string` | yes |
| `ContactTitle` | `string` | yes |
| `Address` | `string` | yes |
| `City` | `string` | yes |
| `Region` | `string` | yes |
| `PostalCode` | `string` | yes |
| `Country` | `string` | yes |
| `Phone` | `string` | yes |
| `Fax` | `string` | yes |

### `Employees` (5 rows)

| Column | Type | Nullable |
|--------|------|----------|
| `EmployeeID` | `integer` | no |
| `LastName` | `string` | yes |
| `FirstName` | `string` | yes |
| `Title` | `string` | yes |
| `BirthDate` | `datetime` | yes |
| `HireDate` | `datetime` | yes |
| `Address` | `string` | yes |
| `City` | `string` | yes |
| `Region` | `string` | yes |
| `PostalCode` | `string` | yes |
| `Country` | `string` | yes |
| `HomePhone` | `string` | yes |

### `OrderDetails` (12 rows)

| Column | Type | Nullable |
|--------|------|----------|
| `OrderID` | `integer` | yes |
| `ProductID` | `integer` | yes |
| `UnitPrice` | `pytype_Decimal` | yes |
| `Quantity` | `integer` | yes |
| `Discount` | `double` | yes |

### `Orders` (6 rows)

| Column | Type | Nullable |
|--------|------|----------|
| `OrderID` | `integer` | no |
| `CustomerID` | `integer` | yes |
| `EmployeeID` | `integer` | yes |
| `OrderDate` | `datetime` | yes |
| `RequiredDate` | `datetime` | yes |
| `ShippedDate` | `datetime` | yes |
| `ShipVia` | `integer` | yes |
| `Freight` | `pytype_Decimal` | yes |
| `ShipName` | `string` | yes |
| `ShipCity` | `string` | yes |
| `ShipRegion` | `string` | yes |
| `ShipPostalCode` | `string` | yes |
| `ShipCountry` | `string` | yes |

### `Products` (10 rows)

| Column | Type | Nullable |
|--------|------|----------|
| `ProductID` | `integer` | yes |
| `ProductName` | `string` | yes |
| `SupplierID` | `integer` | yes |
| `CategoryID` | `integer` | yes |
| `QuantityPerUnit` | `string` | yes |
| `UnitPrice` | `pytype_Decimal` | yes |
| `UnitsInStock` | `integer` | yes |
| `UnitsOnOrder` | `integer` | yes |
| `ReorderLevel` | `integer` | yes |
| `Discontinued` | `boolean` | no |

### `Shippers` (3 rows)

| Column | Type | Nullable |
|--------|------|----------|
| `ShipperID` | `integer` | no |
| `CompanyName` | `string` | yes |
| `Phone` | `string` | yes |

### `Suppliers` (5 rows)

| Column | Type | Nullable |
|--------|------|----------|
| `SupplierID` | `integer` | no |
| `CompanyName` | `string` | yes |
| `ContactName` | `string` | yes |
| `ContactTitle` | `string` | yes |
| `Address` | `string` | yes |
| `City` | `string` | yes |
| `Region` | `string` | yes |
| `PostalCode` | `string` | yes |
| `Country` | `string` | yes |
| `Phone` | `string` | yes |
| `Fax` | `string` | yes |
| `Homepage` | `string` | yes |

## Foreign-key relationships (heuristic)

- (none inferred by the column-name heuristic)

## Saved queries (0)

- (none detected - `MSysAccessStorage WHERE Type = 5` was empty for this fixture)

## Notes

- MSysObjects ACL-blocked by Access (error -1907, "no read permission on MSysObjects") in this fixture; discovery uses probe-based candidate enumeration instead.
- MSysAccessStorage is internal Access workspace scaffolding, not user tables - verified during plan 016.
- Discovery strategy: probe-based candidate enumeration against the candidate list (env var `ACCESS_FIXTURE_TABLE_CANDIDATES`).
- Row counts taken via `SELECT COUNT(*) FROM [<name>]`; columns via `SELECT * FROM [<name>] WHERE 1=0` + `cur.description`.
- Probed 8 candidate names; override via `ACCESS_FIXTURE_TABLE_CANDIDATES` (semicolon-separated).
