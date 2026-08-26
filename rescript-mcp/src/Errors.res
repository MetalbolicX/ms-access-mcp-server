type t = ConfigError(string) | PathGuardError(string) | DatabaseError(string) | ValidationError(string)

type dict = {error: string, message: string}

let configError = (msg: string): t => ConfigError(msg)
let pathGuardError = (msg: string): t => PathGuardError(msg)
let databaseError = (msg: string): t => DatabaseError(msg)
let validationError = (msg: string): t => ValidationError(msg)

let _variantName = (err: t): string => {
  switch err {
  | ConfigError(_) => "ConfigError"
  | PathGuardError(_) => "PathGuardError"
  | DatabaseError(_) => "DatabaseError"
  | ValidationError(_) => "ValidationError"
  }
}

let _message = (err: t): string => {
  switch err {
  | ConfigError(msg) => msg
  | PathGuardError(msg) => msg
  | DatabaseError(msg) => msg
  | ValidationError(msg) => msg
  }
}

let toDict = (err: t): dict => {
  {error: _variantName(err), message: _message(err)}
}
