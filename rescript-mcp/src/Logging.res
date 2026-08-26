// Logging.res — typed console wrappers
// Uses NodeJs.Console for typed FFI instead of %raw

@val external _consoleDebug: string => unit = "console.debug"
@val external _consoleWarn: string => unit = "console.warn"
@val external _consoleError: string => unit = "console.error"

type level = Debug | Warn | Error

let debug = (message: string) => {
  _consoleDebug(message)
}

let warn = (message: string) => {
  _consoleWarn(message)
}

let error = (message: string) => {
  _consoleError(message)
}

let debugWithTag = (~tag: string, message: string) => {
  _consoleDebug("[" ++ tag ++ "] " ++ message)
}

let warnWithTag = (~tag: string, message: string) => {
  _consoleWarn("[" ++ tag ++ "] " ++ message)
}

let errorWithTag = (~tag: string, message: string) => {
  _consoleError("[" ++ tag ++ "] " ++ message)
}
