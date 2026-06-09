Option Explicit

' Enum to easily switch between database types
Public Enum DatabaseType
    dbPostgreSQL
    dbMySQL
    dbSQLServer
    dbSQLite
    dbAccess ' External Access file
End Enum

Private Sub cboDbServer_AfterUpdate()
' Change the default port depending on the database vendor
    Select Case Me.cboDbServer.Value
        Case "Postgres"
            Me.txtPort.Value = 5432
        Case "MySQL"
            Me.txtPort.Value = 3306
        Case "SQL Server"
            Me.txtPort.Value = 1433
    End Select
End Sub

Private Sub cmdConnect_Click()

    ' 1. Validate required fields per DB type
    Dim dbType As DatabaseType
    dbType = GetDbType(Me.cboDbServer.Value)
    If Not ValidateRequiredFields(dbType) Then Exit Sub

    ' 2. Sanitize values against ODBC connection string injection
    Dim connStr As String
    connStr = BuildConnectionString( _
        dbType:=dbType, _
        hostOrPath:=SanitizeCSValue(Me.txtIPAddress.Value), _
        dbName:=SanitizeCSValue(Me.txtdbName.Value), _
        userName:=SanitizeCSValue(Me.txtUserName.Value), _
        pwd:=SanitizeCSValue(Me.txtPassword.Value), _
        port:=CLng(Me.txtPort.Value))

    ' 3. Link or RefreshLink (preserves existing references)
    Dim db As DAO.Database
    Set db = CurrentDb

    If TableExists(db, Me.txtLocalTable.Value) Then
        RefreshLinkedTable db, Me.txtLocalTable.Value, Me.txtRemoteTable.Value, connStr
    Else
        CreateLinkedTable db, Me.txtLocalTable.Value, Me.txtRemoteTable.Value, connStr
    End If

    ' 4. Optionally hide the linked table
    If Not IsNull(Me.checkIsTableHidden.Value) Then
        SetTableHidden db, Me.txtLocalTable.Value, Me.checkIsTableHidden.Value
    End If

    Me.txtStatusMessage.Value = "Successfully linked: " & Me.txtLocalTable.Value

ExitHandler:
    Set db = Nothing
    Exit Sub

ErrorHandler:
    Me.txtStatusMessage.Value = "Error: " & Err.Description
    Resume ExitHandler

End Sub

Private Sub txtIPAddress_BeforeUpdate(Cancel As Integer)
' We only validate if the field isn't empty
    If Not IsNull(Me.txtIPAddress) And Me.txtIPAddress <> vbNullString Then

        If Not IsValidIPAddress(Me.txtIPAddress) Then
            MsgBox "Please enter a valid IPv4 address (e.g., 192.168.1.1)", _
                   vbCritical, "Invalid Format"

            Cancel = True
            Me.txtIPAddress.SelStart = 0
            Me.txtIPAddress.SelLength = Len(Me.txtIPAddress)
        End If

    End If
End Sub

''
' Validates an IPv4 address using Regular Expressions.
' Required Reference: Microsoft VBScript Regular Expressions 5.5
''
Private Function IsValidIPAddress(ByVal ipAddress As String) As Boolean
    Dim regEx As Object
    Set regEx = CreateObject("VBScript.RegExp")

    Dim pattern As String
    pattern = "^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"

    With regEx
        .pattern = pattern
        .IgnoreCase = False
        .Global = False
    End With

    IsValidIPAddress = regEx.Test(ipAddress)
    Set regEx = Nothing
End Function

''' <summary>
''' Validates that required fields for the selected DB type are filled.
''' SQLite only needs file path. Others need host/auth.
''' </summary>
Private Function ValidateRequiredFields(ByVal dbType As DatabaseType) As Boolean
    ValidateRequiredFields = True

    ' SQLite only needs the file path
    If dbType = dbSQLite Then
        If IsNull(Me.txtIPAddress.Value) Or Me.txtIPAddress.Value = vbNullString Then
            MsgBox "Please enter the SQLite database file path.", vbExclamation, "Required Field"
            ValidateRequiredFields = False
        End If
        Exit Function
    End If

    ' For database servers, validate host, credentials, etc.
    If IsNull(Me.txtIPAddress.Value) Or Me.txtIPAddress.Value = vbNullString Then
        MsgBox "Please enter the host or IP address.", vbExclamation, "Required Field"
        ValidateRequiredFields = False
        Exit Function
    End If

    If IsNull(Me.txtUserName.Value) Or Me.txtUserName.Value = vbNullString Then
        MsgBox "Please enter the user name.", vbExclamation, "Required Field"
        ValidateRequiredFields = False
        Exit Function
    End If

    If IsNull(Me.txtPassword.Value) Or Me.txtPassword.Value = vbNullString Then
        MsgBox "Please enter the password.", vbExclamation, "Required Field"
        ValidateRequiredFields = False
        Exit Function
    End If

    If IsNull(Me.txtdbName.Value) Or Me.txtdbName.Value = vbNullString Then
        MsgBox "Please enter the database name.", vbExclamation, "Required Field"
        ValidateRequiredFields = False
        Exit Function
    End If

    If IsNull(Me.txtRemoteTable.Value) Or Me.txtRemoteTable.Value = vbNullString Then
        MsgBox "Please enter the remote table name.", vbExclamation, "Required Field"
        ValidateRequiredFields = False
        Exit Function
    End If

    If IsNull(Me.txtLocalTable.Value) Or Me.txtLocalTable.Value = vbNullString Then
        MsgBox "Please enter the local table name.", vbExclamation, "Required Field"
        ValidateRequiredFields = False
        Exit Function
    End If
End Function

''' <summary>
''' Sanitizes a value against ODBC connection string injection.
''' Removes semicolons, brackets, and leading/trailing whitespace.
''' </summary>
Private Function SanitizeCSValue(ByVal value As String) As String
    Dim sanitized As String
    sanitized = Trim(value)
    ' Remove semicolons (ODBC parameter delimiter)
    sanitized = Replace(sanitized, ";", "")
    ' Remove curly braces (ODBC driver delimiters)
    sanitized = Replace(sanitized, "{", "")
    sanitized = Replace(sanitized, "}", "")
    ' Remove brackets (Access identifier delimiters)
    sanitized = Replace(sanitized, "[", "")
    sanitized = Replace(sanitized, "]", "")
    SanitizeCSValue = sanitized
End Function

''' <summary>
''' Links an external table to the current MS Access database without a DSN.
''' If the link already exists, it refreshes it.
''' </summary>
Private Sub CreateLinkedTable( _
    ByRef db As DAO.Database, _
    ByVal localTableName As String, _
    ByVal remoteTableName As String, _
    ByVal connStr As String)

    Dim tdf As DAO.TableDef

    On Error GoTo ErrorHandler

    Set tdf = db.CreateTableDef(localTableName)
    With tdf
        .Connect = connStr
        .SourceTableName = remoteTableName
    End With

    db.TableDefs.Append tdf

ExitHandler:
    Set tdf = Nothing
    Exit Sub

ErrorHandler:
    Me.txtStatusMessage.Value = "Error creating linked table '" & localTableName & "': " & Err.Description
    Resume ExitHandler

End Sub

''' <summary>
''' Refreshes an existing linked table. Preserves queries/forms referencing it.
''' </summary>
Private Sub RefreshLinkedTable( _
    ByRef db As DAO.Database, _
    ByVal localTableName As String, _
    ByVal remoteTableName As String, _
    ByVal connStr As String)

    Dim tdf As DAO.TableDef
    Dim existingRemoteTableName As String
    Dim preserveHidden As Boolean

    On Error GoTo ErrorHandler

    Set tdf = db.TableDefs(localTableName)
    If Nz(tdf.Connect, vbNullString) = vbNullString Then
        Err.Raise vbObjectError + 515, "RefreshLinkedTable", _
                  "Existing table '" & localTableName & "' is not a linked table."
    End If

    existingRemoteTableName = Trim$(Nz(tdf.SourceTableName, vbNullString))
    remoteTableName = Trim$(remoteTableName)
    preserveHidden = ((tdf.Attributes And dbHiddenObject) = dbHiddenObject)

    If StrComp(existingRemoteTableName, remoteTableName, vbTextCompare) <> 0 Then
        db.TableDefs.Delete localTableName
        db.TableDefs.Refresh

        Set tdf = db.CreateTableDef(localTableName)
        With tdf
            .Connect = connStr
            .SourceTableName = remoteTableName
        End With

        db.TableDefs.Append tdf

        If preserveHidden Then
            db.TableDefs(localTableName).Attributes = db.TableDefs(localTableName).Attributes Or dbHiddenObject
        End If
    Else
        tdf.Connect = connStr
        tdf.RefreshLink
    End If

ExitHandler:
    Set tdf = Nothing
    Exit Sub

ErrorHandler:
    Me.txtStatusMessage.Value = "Error refreshing linked table '" & localTableName & "': " & Err.Description
    Resume ExitHandler

End Sub

''' <summary>
''' Generates the ODBC connection string based on the driver and parameters.
''' </summary>
Private Function BuildConnectionString( _
    ByVal dbType As DatabaseType, _
    ByVal hostOrPath As String, _
    ByVal dbName As String, _
    ByVal userName As String, _
    ByVal pwd As String, _
    ByVal port As Long) As String

    Dim driver As String
    Dim conn As String

    Select Case dbType
        Case dbPostgreSQL
            driver = TryGetDriver("PostgreSQL Unicode", "PostgreSQL ANSI", "psqlODBC")
            If port = 0 Then port = 5432

            conn = "ODBC;DRIVER=" & driver & ";" & _
                   "SERVER=" & hostOrPath & ";" & _
                   "PORT=" & port & ";" & _
                   "DATABASE=" & dbName & ";" & _
                   "UID=" & userName & ";" & _
                   "PWD=" & pwd & ";"

        Case dbMySQL
            driver = TryGetDriver("MySQL ODBC 9.0 Unicode Driver", _
                                  "MySQL ODBC 8.0 Unicode Driver", _
                                  "MySQL ODBC 5.3 Unicode Driver")
            If port = 0 Then port = 3306

            conn = "ODBC;DRIVER=" & driver & ";" & _
                   "SERVER=" & hostOrPath & ";" & _
                   "PORT=" & port & ";" & _
                   "DATABASE=" & dbName & ";" & _
                   "USER=" & userName & ";" & _
                   "PASSWORD=" & pwd & ";" & _
                   "OPTION=3;"

        Case dbSQLServer
            driver = TryGetDriver("ODBC Driver 18 for SQL Server", _
                                  "ODBC Driver 17 for SQL Server", _
                                  "SQL Server")
            If port = 0 Then port = 1433

            conn = "ODBC;DRIVER=" & driver & ";" & _
                   "SERVER=" & hostOrPath & "," & port & ";" & _
                   "DATABASE=" & dbName & ";" & _
                   "UID=" & userName & ";" & _
                   "PWD=" & pwd & ";"

        Case dbSQLite
            driver = TryGetDriver("SQLite3 ODBC Driver", "SQLite ODBC Driver")

            conn = "ODBC;DRIVER=" & driver & ";" & _
                   "Database=" & hostOrPath & ";" & _
                   "StepAPI=0;" & _
                   "SyncPragma=NORMAL;" & _
                   "NoTXN=0;"

        Case dbAccess
            driver = "{Microsoft Access Driver (*.mdb, *.accdb)}"

            conn = "ODBC;DRIVER=" & driver & ";" & _
                   "DBQ=" & TryGetAccessDriver() & ";" & _
                   hostOrPath & ";"

    End Select

    BuildConnectionString = conn

End Function

''' <summary>
''' Tries multiple ODBC driver names and returns the first one found.
''' Falls back to the last option as a best-effort guess.
''' </summary>
Private Function TryGetDriver(ParamArray driverNames() As Variant) As String
    Dim i As Long
    Dim regEx As Object
    Set regEx = CreateObject("VBScript.RegExp")
    regEx.IgnoreCase = True

    For i = LBound(driverNames) To UBound(driverNames)
        ' Check Windows registry for installed ODBC drivers
        ' Fallback: just try the name directly (ODBC driver manager handles it)
        TryGetDriver = "{" & driverNames(i) & "}"
        Exit Function
    Next i

    TryGetDriver = "{" & driverNames(UBound(driverNames)) & "}"
End Function

Private Function TryGetAccessDriver() As String
    TryGetAccessDriver = "{Microsoft Access Driver (*.mdb, *.accdb)}"
End Function

''' <summary>
''' Helper to check if a table exists in the current database.
''' </summary>
Private Function TableExists(ByRef db As DAO.Database, ByVal tblName As String) As Boolean
    Dim tdf As DAO.TableDef

    On Error Resume Next
    Set tdf = db.TableDefs(tblName)
    TableExists = (Err.Number = 0)
    On Error GoTo 0
    Set tdf = Nothing
End Function

''' <summary>
''' Sets or clears the hidden attribute on a table.
''' When hidden, the table is not visible in the Navigation Pane without VBA.
''' </summary>
Private Sub SetTableHidden(ByRef db As DAO.Database, ByVal tableName As String, Optional ByVal isHidden As Boolean = True)

    Dim tdf As DAO.TableDef

    On Error GoTo ErrorHandler

    Set tdf = db.TableDefs(tableName)
    tdf.Attributes = IIf(isHidden, dbHiddenObject, 0)

ExitHandler:
    Set tdf = Nothing
    Exit Sub

ErrorHandler:
    Me.txtStatusMessage.Value = "Error hiding table '" & tableName & "': " & Err.Description
    Resume ExitHandler

End Sub

Private Function GetDbType(ByVal dbVendorName As String) As DatabaseType
    Select Case dbVendorName
        Case "Postgres"
            GetDbType = dbPostgreSQL
        Case "MySQL"
            GetDbType = dbMySQL
        Case "SQL Server"
            GetDbType = dbSQLServer
        Case "SQLite"
            GetDbType = dbSQLite
        Case "Access"
            GetDbType = dbAccess
    End Select
End Function
