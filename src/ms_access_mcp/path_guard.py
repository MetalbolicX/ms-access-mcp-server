from pathlib import Path


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