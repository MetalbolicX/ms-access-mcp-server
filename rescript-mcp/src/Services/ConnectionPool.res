// ConnectionPool.res — named connection pool management
// Implements: connect, disconnect, get, isConnected, list, set_active, get_active
// Pure ReScript implementation using list for connection storage

// ---------------------------------------------------------------------------
// Errors — pool-specific error constructors wrapping Errors.t
// ---------------------------------------------------------------------------

let poolError = (msg: string): Errors.t => Errors.databaseError(msg)
let poolKeyError = (name: string): Errors.t => poolError("Connection '" ++ name ++ "' not found")
let poolAlreadyExistsError = (name: string): Errors.t =>
  poolError("Connection '" ++ name ++ "' already exists. Use disconnect('" ++ name ++ "') first.")

// ---------------------------------------------------------------------------
// ConnectionState — holds state for a single named connection
// ---------------------------------------------------------------------------

type connectionState = {
  mutable connected: bool,
  mutable dbPath: option<string>,
  dbPathStr: string,
  adapterType: string,
  password: string,
}

// ---------------------------------------------------------------------------
// Pool — internal state for the connection pool
// Uses Belt.MapString for string-keyed map (remove returns new map)
// ---------------------------------------------------------------------------

type pool = {
  mutable connections: array<(string, connectionState)>,
  mutable active: string,
  mutable aliases: array<(string, string)>,  // alias -> name mapping
}

// ---------------------------------------------------------------------------
// make — create a new empty pool
// ---------------------------------------------------------------------------

let make = (): pool => {
  {connections: [], active: "default", aliases: []}
}

// ---------------------------------------------------------------------------
// _findConnection — find a connection by name in the array
// ---------------------------------------------------------------------------

let _findConnection = (
  connections: array<(string, connectionState)>,
  name: string,
): option<connectionState> => {
  Belt.Array.getBy(connections, ((n, _state)) => n == name)->Option.map(((_n, state)) => state)
}

// ---------------------------------------------------------------------------
// connect — create or reuse a named connection
// Returns Result<connectionState, Errors.t>
// ---------------------------------------------------------------------------

let connect = (
  p: pool,
  name: string,
  dbPath: string,
  adapterType: string,
  ~password: string="",
): Promise.t<result<connectionState, Errors.t>> => {
  // Check if connection already exists
  switch _findConnection(p.connections, name) {
  | Some(_) => Promise.resolve(Error(poolAlreadyExistsError(name)))
  | None => {
      // Create new connection state
      let state: connectionState = {
        connected: true,
        dbPath: Some(dbPath),
        dbPathStr: dbPath,
        adapterType: adapterType,
        password: password,
      }
      p.connections = Belt.Array.concat(p.connections, [(name, state)])
      Promise.resolve(Ok(state))
    }
  }
}

// ---------------------------------------------------------------------------
// disconnect — remove a named connection from the pool
// Returns Result<unit, Errors.t>
// ---------------------------------------------------------------------------

let disconnect = (
  p: pool,
  ~name: string,
): Promise.t<result<unit, Errors.t>> => {
  let target = name
  switch _findConnection(p.connections, target) {
  | None => {
      if target == "default" {
        // Disconnecting non-existent default is a no-op (matches Python behavior)
        Promise.resolve(Ok(()))
      } else {
        Promise.resolve(Error(poolKeyError(target)))
      }
    }
  | Some(state) => {
      state.connected = false
      state.dbPath = None
      p.connections = Belt.Array.keep(p.connections, ((n, _state)) => n != target)
      Promise.resolve(Ok(()))
    }
  }
}

// ---------------------------------------------------------------------------
// disconnectDefault — disconnect the default connection
// ---------------------------------------------------------------------------

let disconnectDefault = (
  p: pool,
): Promise.t<result<unit, Errors.t>> => {
  disconnect(p, ~name="default")
}

// ---------------------------------------------------------------------------
// get — retrieve connection state by name
// Returns Result<connectionState, Errors.t>
// ---------------------------------------------------------------------------

let get = (
  p: pool,
  ~name: string,
): result<connectionState, Errors.t> => {
  switch _findConnection(p.connections, name) {
  | Some(state) => Ok(state)
  | None => Error(poolKeyError(name))
  }
}

// ---------------------------------------------------------------------------
// getActive — retrieve the active connection state
// Returns Result<connectionState, Errors.t>
// ---------------------------------------------------------------------------

let getActive = (
  p: pool,
): result<connectionState, Errors.t> => {
  switch _findConnection(p.connections, p.active) {
  | Some(state) => Ok(state)
  | None => Error(poolKeyError(p.active))
  }
}

// ---------------------------------------------------------------------------
// isConnected — check if a connection is connected
// Returns Result<bool, Errors.t>
// ---------------------------------------------------------------------------

let isConnected = (
  p: pool,
  ~name: string,
): result<bool, Errors.t> => {
  switch _findConnection(p.connections, name) {
  | Some(state) => Ok(state.connected)
  | None => Ok(false)  // Not in pool → not connected
  }
}

// ---------------------------------------------------------------------------
// isConnectedActive — check if the active connection is connected
// Returns Result<bool, Errors.t>
// ---------------------------------------------------------------------------

let isConnectedActive = (
  p: pool,
): result<bool, Errors.t> => {
  switch _findConnection(p.connections, p.active) {
  | Some(state) => Ok(state.connected)
  | None => Ok(false)  // Not in pool → not connected
  }
}

// ---------------------------------------------------------------------------
// list — return all connections in the pool as array of (name, state) pairs
// Returns array<(string, connectionState)>
// ---------------------------------------------------------------------------

let list = (p: pool): array<(string, connectionState)> => {
  p.connections
}

// ---------------------------------------------------------------------------
// set_active — set the active connection context
// Returns Result<unit, Errors.t>
// ---------------------------------------------------------------------------

let set_active = (
  p: pool,
  name: string,
): result<unit, Errors.t> => {
  switch _findConnection(p.connections, name) {
  | Some(_) => {
      p.active = name
      Ok(())
    }
  | None => Error(poolKeyError(name))
  }
}

// ---------------------------------------------------------------------------
// get_active — get the name of the currently active connection
// Returns string
// ---------------------------------------------------------------------------

let get_active = (p: pool): string => {
  p.active
}

// ---------------------------------------------------------------------------
// Alias support — registerAlias, resolveAlias, disconnectByAlias
// ---------------------------------------------------------------------------

let poolAliasError = (msg: string): Errors.t => poolError(msg)

let _findAlias = (
  aliases: array<(string, string)>,
  alias: string,
): option<string> => {
  Belt.Array.getBy(aliases, ((a, _n)) => a == alias)->Option.map(((_a, n)) => n)
}

let _aliasExistsForDifferentName = (
  aliases: array<(string, string)>,
  alias: string,
  expectedName: string,
): bool => {
  switch _findAlias(aliases, alias) {
  | Some(n) => n != expectedName
  | None => false
  }
}

// ---------------------------------------------------------------------------
// registerAlias — register an alias for an existing connection name
// Returns Result<unit, Errors.t>
// ---------------------------------------------------------------------------

let registerAlias = (
  p: pool,
  ~alias: string,
  ~name: string,
): result<unit, Errors.t> => {
  // Check if alias already exists for a DIFFERENT name
  if _aliasExistsForDifferentName(p.aliases, alias, name) {
    Error(poolAliasError("Alias '" ++ alias ++ "' already registered for a different connection"))
  } else {
    p.aliases = Belt.Array.concat(p.aliases, [(alias, name)])
    Ok(())
  }
}

// ---------------------------------------------------------------------------
// resolveAlias — resolve an alias to its connection name
// Returns Result<string, Errors.t>
// ---------------------------------------------------------------------------

let resolveAlias = (
  p: pool,
  ~alias: string,
): result<string, Errors.t> => {
  switch _findAlias(p.aliases, alias) {
  | Some(name) => Ok(name)
  | None => Error(poolAliasError("Alias '" ++ alias ++ "' not found"))
  }
}

// ---------------------------------------------------------------------------
// disconnectByAlias — disconnect the connection behind an alias
// Returns Promise<result<unit, Errors.t>>
// ---------------------------------------------------------------------------

let disconnectByAlias = (
  p: pool,
  ~alias: string,
): Promise.t<result<unit, Errors.t>> => {
  switch _findAlias(p.aliases, alias) {
  | Some(name) => disconnect(p, ~name)
  | None => Promise.resolve(Error(poolAliasError("Alias '" ++ alias ++ "' not found")))
  }
}
