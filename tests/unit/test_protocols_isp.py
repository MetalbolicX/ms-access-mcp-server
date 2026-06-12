"""Tests for ISP (Interface Segregation Principle) protocol split (PR2).

Verifies that:
- IUiAdapter is a TypeAlias combining 6 focused protocols.
- OdbcAdapter declares IDataAdapter, ISchemaAdapter, IDatabasePropertiesAdapter.
- WinComAdapter declares all 6 UI protocols plus IDataAdapter and ISchemaAdapter.
- BackupService and DevCopyService use the narrowest applicable protocols.
- ComOnlyAdapterMixin no longer stubs IDatabasePropertiesAdapter/IVersioningAdapter methods.
"""

from __future__ import annotations

import pytest

from ms_access_mcp.adapters import com_only_mixin, interfaces
from ms_access_mcp.adapters.interfaces import (
    IControlAdapter,
    IDataAdapter,
    IDatabasePropertiesAdapter,
    IFormAdapter,
    IMacroAdapter,
    ISchemaAdapter,
    IUiAdapter,
    IVbaAdapter,
    IVersioningAdapter,
)
from ms_access_mcp.adapters.odbc import OdbcAdapter
from ms_access_mcp.adapters.wincom import WinComAdapter

# =============================================================================
# Protocol existence — every split protocol must be importable
# =============================================================================


class TestSplitProtocolsExist:
    """The 6 split UI protocols must be importable from interfaces."""

    @pytest.mark.parametrize(
        "protocol",
        [
            IFormAdapter,
            IVbaAdapter,
            IMacroAdapter,
            IControlAdapter,
            IDatabasePropertiesAdapter,
            IVersioningAdapter,
        ],
    )
    def test_protocol_importable(self, protocol):
        assert protocol is not None

    def test_iui_adapter_is_type_alias(self):
        """IUiAdapter is a TypeAlias combining the 6 UI protocols."""
        # TypeAlias evaluates to the union of its members
        assert hasattr(interfaces, "IUiAdapter")
        # IUiAdapter.__args__ should contain the 6 protocols
        args = getattr(IUiAdapter, "__args__", ())
        assert IFormAdapter in args
        assert IVbaAdapter in args
        assert IMacroAdapter in args
        assert IControlAdapter in args
        assert IDatabasePropertiesAdapter in args
        assert IVersioningAdapter in args


# =============================================================================
# IFormAdapter — form-level operations
# =============================================================================


class TestIFormAdapterProtocol:
    """IFormAdapter must declare the form operations listed in the spec."""

    def test_form_methods_declared(self):
        # Protocol methods must exist as abstract members
        for method in ("open_form", "close_form", "get_form_controls",
                       "set_control_property", "get_control_property",
                       "export_form_to_html"):
            assert hasattr(IFormAdapter, method), f"IFormAdapter missing {method}"


# =============================================================================
# IVbaAdapter — VBA module operations
# =============================================================================


class TestIVbaAdapterProtocol:
    """IVbaAdapter must declare the VBA operations listed in the spec."""

    def test_vba_methods_declared(self):
        for method in ("get_vba_module", "save_vba_module", "execute_vba",
                       "get_vba_references", "add_vba_reference"):
            assert hasattr(IVbaAdapter, method), f"IVbaAdapter missing {method}"


# =============================================================================
# IMacroAdapter — macro operations
# =============================================================================


class TestIMacroAdapterProtocol:
    """IMacroAdapter must declare the macro operations listed in the spec."""

    def test_macro_methods_declared(self):
        for method in ("run_macro", "create_macro", "delete_macro", "rename_macro"):
            assert hasattr(IMacroAdapter, method), f"IMacroAdapter missing {method}"


# =============================================================================
# IControlAdapter — control operations
# =============================================================================


class TestIControlAdapterProtocol:
    """IControlAdapter must declare the control operations listed in the spec."""

    def test_control_methods_declared(self):
        for method in ("get_controls", "set_control_property",
                       "get_control_property", "set_control_source"):
            assert hasattr(IControlAdapter, method), f"IControlAdapter missing {method}"


# =============================================================================
# IDatabasePropertiesAdapter — DAO properties
# =============================================================================


class TestIDatabasePropertiesAdapterProtocol:
    """IDatabasePropertiesAdapter must declare the DB-property operations."""

    def test_db_props_methods_declared(self):
        for method in ("get_database_properties", "set_database_property"):
            assert hasattr(IDatabasePropertiesAdapter, method), \
                f"IDatabasePropertiesAdapter missing {method}"


# =============================================================================
# IVersioningAdapter — backup/restore/export
# =============================================================================


class TestIVersioningAdapterProtocol:
    """IVersioningAdapter must declare the versioning/export operations."""

    def test_versioning_methods_declared(self):
        for method in ("export_database", "import_database", "create_backup",
                       "restore_backup"):
            assert hasattr(IVersioningAdapter, method), \
                f"IVersioningAdapter missing {method}"


# =============================================================================
# Adapter protocol compliance — OdbcAdapter and WinComAdapter
# =============================================================================


class TestOdbcAdapterProtocolCompliance:
    """OdbcAdapter must implement IDataAdapter, ISchemaAdapter, IDatabasePropertiesAdapter."""

    def test_odbc_implements_idata_adapter(self):
        assert isinstance(OdbcAdapter(), IDataAdapter)

    def test_odbc_implements_ischema_adapter(self):
        assert isinstance(OdbcAdapter(), ISchemaAdapter)

    def test_odbc_implements_idatabase_properties_adapter(self):
        assert isinstance(OdbcAdapter(), IDatabasePropertiesAdapter)

    def test_odbc_does_not_implement_iform_adapter(self):
        # OdbcAdapter has UI stubs from the mixin that raise NotImplementedError
        # but the class declaration should not include IFormAdapter.
        # We check the class hierarchy, not isinstance (which would pass for stub methods).
        from ms_access_mcp.adapters.odbc import OdbcAdapter as OdbcClass
        bases = [b.__name__ for b in OdbcClass.__mro__]
        assert "IFormAdapter" not in bases

    def test_odbc_does_not_implement_ivba_adapter(self):
        from ms_access_mcp.adapters.odbc import OdbcAdapter as OdbcClass
        bases = [b.__name__ for b in OdbcClass.__mro__]
        assert "IVbaAdapter" not in bases


class TestWinComAdapterProtocolCompliance:
    """WinComAdapter must implement all split UI protocols."""

    def test_wincom_implements_idata_adapter(self):
        assert isinstance(WinComAdapter(), IDataAdapter)

    def test_wincom_implements_ischema_adapter(self):
        assert isinstance(WinComAdapter(), ISchemaAdapter)

    def test_wincom_implements_idatabase_properties_adapter(self):
        assert isinstance(WinComAdapter(), IDatabasePropertiesAdapter)

    def test_wincom_class_declares_all_ui_protocols(self):
        """WinComAdapter's class declaration must list the 6 UI protocols."""
        from ms_access_mcp.adapters.wincom import WinComAdapter as WinClass
        bases = [b.__name__ for b in WinClass.__mro__]
        # All 6 new UI protocols must be in the MRO
        for proto in ("IFormAdapter", "IVbaAdapter", "IMacroAdapter",
                      "IControlAdapter", "IDatabasePropertiesAdapter",
                      "IVersioningAdapter"):
            assert proto in bases, \
                f"WinComAdapter must declare {proto} in its class hierarchy"


# =============================================================================
# ComOnlyAdapterMixin — scope of stubs
# =============================================================================


class TestComOnlyAdapterMixinScope:
    """The mixin must only stub IForm/IVba/IMacro/IControlAdapter methods."""

    @staticmethod
    def _source_contains(method_name: str, needle: str = "NotImplementedError") -> bool:
        """Return True if the mixin's method body contains the needle."""
        import inspect

        method = getattr(com_only_mixin.ComOnlyAdapterMixin, method_name, None)
        if method is None:
            return False
        try:
            src = inspect.getsource(method)
        except (OSError, TypeError):
            return False
        return needle in src

    def test_mixin_does_not_stub_get_database_properties(self):
        """IDatabasePropertiesAdapter stubs are removed from the mixin."""
        assert not self._source_contains("get_database_properties"), \
            "Mixin should not stub get_database_properties — it belongs to OdbcAdapter directly"

    def test_mixin_does_not_stub_set_database_property(self):
        assert not self._source_contains("set_database_property"), \
            "Mixin should not stub set_database_property"

    def test_mixin_does_not_stub_export_all_versioning(self):
        """IVersioningAdapter stubs are removed from the mixin."""
        assert not self._source_contains("export_all_versioning"), \
            "Mixin should not stub export_all_versioning"

    def test_mixin_does_not_stub_import_all_versioning(self):
        assert not self._source_contains("import_all_versioning"), \
            "Mixin should not stub import_all_versioning"

    def test_mixin_does_not_stub_compare_versioning(self):
        assert not self._source_contains("compare_versioning"), \
            "Mixin should not stub compare_versioning"

    def test_mixin_does_not_stub_export_query_to_text(self):
        assert not self._source_contains("export_query_to_text"), \
            "Mixin should not stub export_query_to_text"

    def test_mixin_still_stubs_open_form(self):
        """IFormAdapter stubs are kept in the mixin."""
        assert self._source_contains("open_form"), \
            "Mixin should still stub open_form"

    def test_mixin_still_stubs_set_vba_code(self):
        """IVbaAdapter stubs are kept in the mixin."""
        assert self._source_contains("set_vba_code"), \
            "Mixin should still stub set_vba_code"


# =============================================================================
# Service narrow type hints — BackupService and DevCopyService
# =============================================================================


class TestBackupServiceNarrowing:
    """BackupService must depend on the narrowest applicable protocols."""

    def test_backup_service_uses_versioning_protocol(self):
        """BackupService must import IVersioningAdapter (per task 2.10)."""
        import inspect

        from ms_access_mcp.services import backup_service

        source = inspect.getsource(backup_service)
        assert "IVersioningAdapter" in source, \
            "BackupService must import IVersioningAdapter per task 2.10"


class TestDevCopyServiceNarrowing:
    """DevCopyService must depend on IVersioningAdapter + IDatabasePropertiesAdapter."""

    def test_dev_copy_service_uses_versioning_protocol(self):
        """DevCopyService must import IVersioningAdapter (per task 2.11)."""
        import inspect

        from ms_access_mcp.services import dev_copy_service

        source = inspect.getsource(dev_copy_service)
        assert "IVersioningAdapter" in source, \
            "DevCopyService must import IVersioningAdapter per task 2.11"

    def test_dev_copy_service_uses_db_properties_protocol(self):
        """DevCopyService must import IDatabasePropertiesAdapter (per task 2.11)."""
        import inspect

        from ms_access_mcp.services import dev_copy_service

        source = inspect.getsource(dev_copy_service)
        assert "IDatabasePropertiesAdapter" in source, \
            "DevCopyService must import IDatabasePropertiesAdapter per task 2.11"


# =============================================================================
# Import smoke test — make sure the new split imports don't break
# =============================================================================


def test_split_protocols_importable():
    """All new protocols must be importable from interfaces module."""
    from ms_access_mcp.adapters.interfaces import (
        IControlAdapter,
        IDatabasePropertiesAdapter,
        IFormAdapter,
        IMacroAdapter,
        IUiAdapter,
        IVbaAdapter,
        IVersioningAdapter,
    )
    assert all([
        IFormAdapter, IVbaAdapter, IMacroAdapter, IControlAdapter,
        IDatabasePropertiesAdapter, IVersioningAdapter, IUiAdapter,
    ])
