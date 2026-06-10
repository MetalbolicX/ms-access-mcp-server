"""Database property operations for COM automation.

Wraps DAO `CurrentDb.Properties` access — the user-defined and built-in
property bag that backs Access's "Database Properties" dialog.

Patterns mirror VbaOperations: a thin class that owns a reference to the
STA-threaded ComDispatcher and pushes every COM call through `dispatcher.call`.
"""

from typing import Any

from ..adapters.com_dispatcher import ComDispatcher
from ..logging import get_logger

_logger = get_logger(__name__)


# DAO data type enum values (dbDataTypeEnum-like integers used by CreateProperty).
# See: https://learn.microsoft.com/en-us/office/client-developer/access/desktop-database-reference/datatypeenum
_DAO_TYPE_MAP: dict[str, int] = {
    "Text": 10,
    "text": 10,
    "str": 10,
    "string": 10,
    "Long": 4,
    "long": 4,
    "int": 4,
    "integer": 3,
    "Boolean": 1,
    "boolean": 1,
    "bool": 1,
    "Double": 7,
    "double": 7,
    "float": 7,
    "Date": 8,
    "date": 8,
    "datetime": 8,
    "Byte": 2,
    "byte": 2,
}

# Built-in / system properties that should be filtered out of the "all" view
# because they are internal Access plumbing, not user-meaningful.
_INTERNAL_PREFIXES = ("_", "MSys")

# Categories used by get_database_properties. Keys are the "all" keys we
# iterate, values are the property names (case-insensitive) that fall into
# each category. A property not listed here is still included in "all" but
# not in any specific category.
_STARTUP_PROP_NAMES = frozenset(
    {
        "apptitle",
        "startupform",
        "startupshowform",
        "allowfullmenus",
        "allowbuiltinpanels",
        "allowdefaultshortcutmenus",
        "allowshortcutmenus",
        "allowtoolbarchanges",
        "allowdesignchanges",
        "startmenubar",
        "startupmenubar",
        "startupshortcutmenubar",
        "startupshowstatusbar",
        "startupshowcontextmenus",
        "usesingledocumentinterface",
        "dontshowhelptext",
    }
)
_APP_PROP_NAMES = frozenset(
    {
        "author",
        "company",
        "description",
        "keywords",
        "subject",
        "manager",
        "category",
        "comments",
        "hyperlinkbase",
        "appversion",
    }
)


def _detect_dao_type(value: str) -> tuple[str, int]:
    """Auto-detect the best DAO type for a string value.

    Precedence: Boolean → Long → Double → Text.
    Note that "true"/"false" (case-insensitive) win over integer detection so
    that the string "1" is a Boolean only when explicitly requested via type;
    we never auto-detect "1" as Boolean.

    Returns:
        (dao_type_name, dao_type_int) — e.g. ("Text", 10).
    """
    lowered = value.lower() if value else ""
    if lowered in ("true", "false"):
        return "Boolean", 1
    # digit-only positive integers → Long
    if value and value.isdigit():
        return "Long", 4
    # Anything that parses as a number → Double (covers negatives & decimals)
    try:
        float(value)
        return "Double", 7
    except (TypeError, ValueError):
        pass
    return "Text", 10


class DbOperations:
    """Database property operations requiring COM automation.

    Args:
        dispatcher: ComDispatcher instance for STA-threaded COM calls.
    """

    def __init__(self, dispatcher: ComDispatcher) -> None:
        self._dispatcher = dispatcher

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def get_database_properties(self, names: list[str] | None = None) -> dict:
        """Read database properties from `CurrentDb.Properties`.

        Args:
            names: Optional list of property names to filter to. If provided,
                only matching names are included. Names are matched
                case-insensitively.

        Returns:
            dict with keys:
              - startup: {name: value} of properties in the startup category
              - app: {name: value} of application-level properties
              - project: {name: value} of project-level properties
              - all: {name: value} of all non-internal properties

            Returns empty categories when dispatcher is not started or the
            current database is not available.
        """
        if not self._dispatcher._started:
            return {"startup": {}, "app": {}, "project": {}, "all": {}}

        def _do() -> dict:
            startup: dict[str, str] = {}
            app: dict[str, str] = {}
            project: dict[str, str] = {}
            all_props: dict[str, str] = {}

            try:
                db = self._dispatcher.current_db
                if db is None:
                    return {"startup": startup, "app": app, "project": project, "all": all_props}

                names_filter: set[str] | None = {n.lower() for n in names} if names else None

                # `db.Properties` is a 0-based DAO collection in COM automation.
                # Use index-based access for reliability across pywin32 versions.
                try:
                    count = db.Properties.Count
                except Exception:
                    count = 0

                for i in range(count):
                    try:
                        prop = db.Properties(i)
                        name = prop.Name
                        if not name:
                            continue
                        if name.startswith(_INTERNAL_PREFIXES):
                            continue
                        if names_filter is not None and name.lower() not in names_filter:
                            continue
                        value = prop.Value
                        # Coerce value to string for transport
                        if value is None:
                            value_str = ""
                        elif isinstance(value, bool):
                            value_str = "True" if value else "False"
                        else:
                            value_str = str(value)

                        all_props[name] = value_str
                        lname = name.lower()
                        if lname in _STARTUP_PROP_NAMES:
                            startup[name] = value_str
                        if lname in _APP_PROP_NAMES:
                            app[name] = value_str
                    except Exception:
                        # Skip individual property errors (some Access versions
                        # mark certain props as inaccessible) — never let one
                        # bad property break the entire read.
                        continue

                # Project-level info comes from CurrentProject (separate from
                # Properties collection).
                try:
                    app_obj = self._dispatcher.access_app
                    cp = app_obj.CurrentProject
                    project["Path"] = str(cp.FullName) if cp.FullName else ""
                    project["Name"] = str(cp.Name) if cp.Name else ""
                    project["ProjectType"] = "ADP" if cp.ProjectType else "MDB/ACCDB"
                except Exception:
                    pass
            except Exception as e:
                _logger.debug(f"[get_database_properties] returning empty due to: {e}")
                return {"startup": {}, "app": {}, "project": {}, "all": {}}

            return {"startup": startup, "app": app, "project": project, "all": all_props}

        return self._dispatcher.call(_do)

    def set_database_property(self, name: str, value: str, type: str | None = None) -> bool:
        """Create or update a database property on `CurrentDb.Properties`.

        If the property already exists, its value is updated in place.
        Otherwise a new property is created (auto-detecting the DAO type from
        the string value) and appended to the collection.

        Args:
            name: Property name to create/update.
            value: New value (always transported as a string; conversion to
                the appropriate DAO type happens internally).
            type: Optional explicit DAO type ("Text" | "Long" | "Boolean" |
                "Double" | "Date" | "Byte"). When None, the type is inferred
                from the value.

        Returns:
            True on success, False on any error (not connected, COM error,
            permission denied, etc.).
        """
        if not self._dispatcher._started:
            return False

        def _do() -> bool:
            try:
                db = self._dispatcher.current_db
                if db is None:
                    return False

                # Determine DAO type for new property creation.
                if type is not None:
                    dao_type = _DAO_TYPE_MAP.get(type)
                    if dao_type is None:
                        dao_type = _DAO_TYPE_MAP.get(type.capitalize(), 10)
                    _type_label = type
                else:
                    _type_label, dao_type = _detect_dao_type(value)

                # Try to find existing property.
                existing = None
                try:
                    count = db.Properties.Count
                    for i in range(count):
                        try:
                            prop = db.Properties(i)
                            if prop.Name == name:
                                existing = prop
                                break
                        except Exception:
                            continue
                except Exception:
                    existing = None

                if existing is not None:
                    # Convert value to the existing property's DAO type so
                    # COM doesn't reject the assignment.
                    try:
                        existing.Type = dao_type
                    except Exception:
                        # Some built-in properties have a fixed type — ignore.
                        pass
                    existing.Value = _coerce_for_type(value, dao_type)
                    return True

                # Create new property
                new_prop = db.CreateProperty(name, dao_type, _coerce_for_type(value, dao_type))
                db.Properties.Append(new_prop)
                return True
            except Exception as e:
                _logger.debug(f"[set_database_property] failed for {name!r}: {e}")
                return False

        return self._dispatcher.call(_do)


def _coerce_for_type(value: str, dao_type: int) -> Any:
    """Best-effort conversion of a string value to a Python value matching the
    DAO type expected by COM.

    Access COM generally accepts strings for text/date properties and will
    raise on type mismatch for numerics, so we coerce numerics and leave
    everything else as a raw string.
    """
    if dao_type == 1:  # Boolean
        return value.lower() in ("true", "1", "yes", "-1")
    if dao_type in (2, 3, 4):  # Byte, Integer, Long
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    if dao_type == 7:  # Double
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return value
