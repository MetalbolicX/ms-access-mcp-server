"""Shared fixtures for COM integration tests.

Each test class copies the fixture to a temp dir via setup_method.
See test_wincom_data_write.py for the canonical pattern.
"""

# conftest intentionally empty — temp DB copy is handled per-test-class
# to keep fixture setup and teardown explicit in each test file.