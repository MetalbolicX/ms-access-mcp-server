"""Export strategy pattern — pluggable format converters.

Use ``ExportStrategySelector`` to pick a strategy by format name::

    selector = ExportStrategySelector()
    strategy = selector.get("csv")
    result = strategy.export(context)

Built-in formats: ``csv``, ``json``, ``excel``.
"""

from .strategies import (
    ExportContext,
    ExportStrategy,
    ExportStrategySelector,
    CsvStrategy,
    JsonStrategy,
    ExcelStrategy,
)

__all__ = [
    "ExportContext",
    "ExportStrategy",
    "ExportStrategySelector",
    "CsvStrategy",
    "JsonStrategy",
    "ExcelStrategy",
]
