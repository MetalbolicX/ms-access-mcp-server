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


# ============================================================================
# PathGuard Middleware Wrapper (validate_tool_args decorator)
# ============================================================================

class TestPathGuardMiddleware:
    """PathGuard middleware wrapper validates file args on tool calls."""

    def test_validate_tool_argsDecorator_rejects_traversal_on_file_path(self, tmp_path):
        """Decorator should reject file_path containing ../ traversal."""
        from ms_access_mcp.path_guard import validate_tool_args, PathGuard

        guard = PathGuard(allowed_dirs=[str(tmp_path)])

        @validate_tool_args(guard)
        def my_tool(file_path: str) -> dict:
            return {"success": True, "file_path": file_path}

        bad_path = str(tmp_path / ".." / ".." / "etc" / "passwd.accdb")
        result = my_tool(file_path=bad_path)
        assert result["success"] is False
        assert "not allowed" in result["error"]

    def test_validate_tool_argsDecorator_rejects_unc_path(self, tmp_path):
        """Decorator should reject UNC paths in file_path arg."""
        from ms_access_mcp.path_guard import validate_tool_args, PathGuard

        guard = PathGuard(allowed_dirs=[str(tmp_path)])

        @validate_tool_args(guard)
        def my_tool(file_path: str) -> dict:
            return {"success": True, "file_path": file_path}

        result = my_tool(file_path="\\\\server\\share\\db.accdb")
        assert result["success"] is False
        assert "not allowed" in result["error"]

    def test_validate_tool_argsDecorator_allows_valid_path(self, tmp_path):
        """Decorator should allow file_path inside allowed dirs."""
        from ms_access_mcp.path_guard import validate_tool_args, PathGuard

        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        good_file = tmp_path / "app.accdb"
        good_file.touch()

        @validate_tool_args(guard)
        def my_tool(file_path: str) -> dict:
            return {"success": True, "file_path": file_path}

        result = my_tool(file_path=str(good_file))
        assert result["success"] is True

    def test_validate_tool_argsDecorator_checks_multiple_path_args(self, tmp_path):
        """Decorator should validate all path args: file_path, output_path, source, dest."""
        from ms_access_mcp.path_guard import validate_tool_args, PathGuard

        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        good_file = tmp_path / "app.accdb"
        good_file.touch()

        @validate_tool_args(guard)
        def my_tool(file_path: str, output_path: str, source: str, dest: str) -> dict:
            return {"success": True}

        # All valid
        result = my_tool(
            file_path=str(good_file),
            output_path=str(good_file),
            source=str(good_file),
            dest=str(good_file),
        )
        assert result["success"] is True

        # output_path traversal rejected
        bad_out = str(tmp_path / ".." / "etc" / "out.accdb")
        result = my_tool(
            file_path=str(good_file),
            output_path=bad_out,
            source=str(good_file),
            dest=str(good_file),
        )
        assert result["success"] is False
        assert "output_path" in result["error"]

    def test_validate_tool_argsDecorator_checks_backup_path_and_script_path(self, tmp_path):
        """Decorator should also validate backup_path, script_path, input_dir, output_dir."""
        from ms_access_mcp.path_guard import validate_tool_args, PathGuard

        guard = PathGuard(allowed_dirs=[str(tmp_path)])
        good_file = tmp_path / "app.accdb"
        good_file.touch()

        @validate_tool_args(guard)
        def my_tool(backup_path: str, script_path: str, input_dir: str) -> dict:
            return {"success": True}

        # All valid
        result = my_tool(
            backup_path=str(good_file),
            script_path=str(good_file),
            input_dir=str(tmp_path / "data"),
        )
        assert result["success"] is True

        # script_path traversal rejected
        bad_script = str(tmp_path / ".." / "hack" / "script.sql")
        result = my_tool(
            backup_path=str(good_file),
            script_path=bad_script,
            input_dir=str(tmp_path),
        )
        assert result["success"] is False
        assert "script_path" in result["error"]