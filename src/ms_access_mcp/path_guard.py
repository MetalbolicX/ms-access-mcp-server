from pathlib import Path
from functools import wraps


# Argument names that represent file/directory paths and need PathGuard validation
PATH_ARG_NAMES = frozenset({
    "file_path",
    "output_path",
    "output_dir",
    "input_dir",
    "backup_path",
    "backup_dir",
    "script_path",
    "source",
    "dest",
})


class PathGuard:
    """Validate database paths against an allowed directory whitelist.

    Rejects:
    - Paths outside allowed directories
    - Path traversal attempts (../)
    - UNC paths (\\\\server\\share)
    """

    def __init__(self, allowed_dirs: list[str]):
        self._allowed = [Path(d).resolve() for d in allowed_dirs]

    def is_allowed(self, path: str) -> bool:
        """Return True if path is inside an allowed directory and safe."""
        if path.startswith("\\\\") or path.startswith("//"):
            return False

        try:
            abs_path = Path(path).resolve()
            for allowed in self._allowed:
                abs_path.relative_to(allowed)
                return True
        except ValueError:
            pass
        return False

    def validate(self, path: str) -> str:
        """Return absolute path if allowed, otherwise raise ValueError."""
        if not self.is_allowed(path):
            raise ValueError(
                f"Database path not allowed: {path}. "
                f"Allowed directories: {[str(d) for d in self._allowed]}"
            )
        return str(Path(path).resolve())


def validate_tool_args(guard: PathGuard):
    """Decorator that validates path-named arguments through PathGuard.

    Auto-detects args named: file_path, output_path, output_dir, input_dir,
    backup_path, backup_dir, script_path, source, dest

    If validation fails, returns {"success": False, "error": "..."} instead of
    calling the wrapped function.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get function signature to map positional args to names
            import inspect
            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Check each path argument
            for arg_name, arg_value in bound.arguments.items():
                if arg_name in PATH_ARG_NAMES and arg_value is not None:
                    if not isinstance(arg_value, str):
                        continue
                    if not guard.is_allowed(arg_value):
                        return {
                            "success": False,
                            "error": f"{arg_name}: path not allowed: {arg_value}. "
                                     f"Allowed directories: {[str(d) for d in guard._allowed]}",
                        }

            return func(*args, **kwargs)
        return wrapper
    return decorator