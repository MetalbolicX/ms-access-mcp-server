import pytest
from pathlib import Path

from ms_access_mcp.path_guard import PathGuard


class TestPathGuardAllow:
    """Path inside allowed directory → is_allowed returns True."""

    def test_path_inside_allowed_dir(self, tmp_path):
        """File path under the allowed directory returns True."""
        db_file = tmp_path / "test.accdb"
        db_file.touch()
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        assert guard.is_allowed(str(db_file)) is True

    def test_path_deeply_nested_inside_allowed(self, tmp_path):
        """Deeply nested file inside allowed dir returns True."""
        sub_dir = tmp_path / "sub" / "deep" / "dir"
        sub_dir.mkdir(parents=True)
        db_file = sub_dir / "data.accdb"
        db_file.touch()
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        assert guard.is_allowed(str(db_file)) is True


class TestPathGuardDeny:
    """Path outside allowed directory → is_allowed returns False."""

    def test_path_outside_allowed_dir(self, tmp_path):
        """File path outside allowed directory returns False."""
        other_dir = tmp_path.parent / "other"
        other_dir.mkdir(exist_ok=True)
        db_file = other_dir / "secret.accdb"
        db_file.touch()
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        assert guard.is_allowed(str(db_file)) is False

    def test_sibling_directory_rejected(self, tmp_path):
        """Sibling directory path is rejected."""
        sibling = tmp_path.parent / "sibling_db"
        sibling.mkdir(exist_ok=True)
        db_file = sibling / "app.accdb"
        db_file.touch()
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        assert guard.is_allowed(str(db_file)) is False


class TestPathGuardTraversal:
    """Path traversal attempts → is_allowed returns False."""

    def test_simple_traversal_rejected(self, tmp_path):
        """Single ../ traversal outside allowed dir is rejected."""
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        bad_path = str(tmp_path / ".." / ".." / "etc" / "passwd.accdb")
        assert guard.is_allowed(bad_path) is False

    def test_deep_traversal_rejected(self, tmp_path):
        """Multiple ../ segments still outside allowed dir."""
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        bad_path = str(tmp_path / ".." / ".." / "home" / ".." / "root" / "db.accdb")
        assert guard.is_allowed(bad_path) is False

    def test_traversal_inside_allowed_with_absolute_path(self, tmp_path):
        """Absolute path that resolves inside allowed dir passes."""
        safe_path = str(tmp_path / "db.accdb")
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        assert guard.is_allowed(safe_path) is True


class TestPathGuardUNC:
    """UNC paths → is_allowed returns False."""

    def test_unc_path_rejected(self, tmp_path):
        """Windows UNC path (\\\\server\\share) is rejected."""
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        assert guard.is_allowed("\\\\server\\share\\db.accdb") is False

    def test_unc_path_double_backslash_rejected(self, tmp_path):
        """UNC with double leading backslash is rejected."""
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        assert guard.is_allowed("//server/share/db.accdb") is False


class TestPathGuardValidate:
    """validate() returns absolute path or raises ValueError."""

    def test_validate_allowed_path_returns_absolute(self, tmp_path):
        """validate() returns absolute path string for allowed path."""
        db_file = tmp_path / "app.accdb"
        db_file.touch()
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        result = guard.validate(str(db_file))
        assert isinstance(result, str)
        assert Path(result).is_absolute()

    def test_validate_disallowed_path_raises(self, tmp_path):
        """validate() raises ValueError for disallowed path."""
        other_dir = tmp_path.parent / "not_allowed"
        other_dir.mkdir(exist_ok=True)
        db_file = other_dir / "db.accdb"
        db_file.touch()
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        with pytest.raises(ValueError, match="not allowed"):
            guard.validate(str(db_file))

    def test_validate_traversal_raises(self, tmp_path):
        """validate() raises ValueError for traversal path."""
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        bad_path = str(tmp_path / ".." / ".." / "db.accdb")
        with pytest.raises(ValueError, match="not allowed"):
            guard.validate(bad_path)

    def test_validate_unc_raises(self, tmp_path):
        """validate() raises ValueError for UNC path."""
        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        with pytest.raises(ValueError, match="not allowed"):
            guard.validate("\\\\server\\share\\db.accdb")