// ComDispatch.res — FIFO promise queue serializing all COM calls
// Mirrors Python com_dispatcher.py: a single STA thread must drive every
// COM object, so calls are queued and executed strictly one at a time.

// ---------------------------------------------------------------------------
// Internals — a mutable queue of already-wrapped tasks and a running flag
// ---------------------------------------------------------------------------

type task = unit => Promise.t<unit>

type t = {
  mutable queue: array<task>,
  mutable processing: bool,
}

let make = () => {
  queue: [],
  processing: false,
}

// Drain the queue one task at a time. A rejected task does not stall the
// queue — we catch the error, drop it, and continue with the next item.
let rec _drain = (dispatch: t): Promise.t<unit> => {
  switch Array.get(dispatch.queue, 0) {
  | None => {
      dispatch.queue = []
      dispatch.processing = false
      Promise.resolve()
    }
  | Some(task) => {
      dispatch.queue = Array.slice(dispatch.queue, ~start=1)
      task()
        ->Promise.then(_ => _drain(dispatch))
        ->Promise.catch(_ => _drain(dispatch))
    }
  }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

// Enqueue a thunk returning a Promise. The returned Promise resolves or
// rejects with the thunk's result, but the queue always advances to the
// next item regardless of whether this thunk rejects.
let enqueue = (dispatch: t, thunk: unit => Promise.t<'a>): Promise.t<'a> => {
  Promise.make((resolve, reject) => {
    let wrapped: task = () => {
      thunk()
        ->Promise.then(result => {
          resolve(result)
          Promise.resolve()
        })
        ->Promise.catch(error => {
          reject(error)
          Promise.resolve()
        })
    }
    dispatch.queue = Array.concat(dispatch.queue, [wrapped])
    if !dispatch.processing {
      dispatch.processing = true
      _drain(dispatch)->ignore
    }
  })
}
