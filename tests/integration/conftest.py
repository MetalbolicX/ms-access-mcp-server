"""
Pytest configuration for integration tests.

Shared skip conditions and helpers are in helpers.py.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from helpers import TEST_DB, skip_unless_windows, skip_unless_pywin32, skip_unless_db

pytestmark = [skip_unless_windows, skip_unless_pywin32, skip_unless_db]


@pytest.fixture
def temp_db_copy():
    """Create a temporary copy of the test database for destructive tests.

    Yields the path to the cloned .accdb file.  The clone is a file-level copy
    (shutil.copy2) so every test gets a pristine isolated database.  The master
    fixture at TEST_DB is never modified.

    Teardown always removes the clone and its parent temp directory — even if
    the test raises an exception.  Access files cannot be deleted while Access
    holds a lock, so we rely on ComDispatcher's _release_com_safe() being called
    by the test's teardown (adapter.disconnect()).
    """
    if not TEST_DB:
        pytest.skip("ACCESS_TEST_DB not set and no fixture found")

    src_path = Path(TEST_DB)
    if not src_path.exists():
        pytest.skip(f"Fixture database not found: {src_path}")

    # Create a temp directory that will own the clone; when we clean it up
    # the clone goes with it regardless of whether the test forgot to delete.
    tmpdir = tempfile.mkdtemp(prefix="acc_test_")
    clone_path = Path(tmpdir) / src_path.name

    try:
        shutil.copy2(src_path, clone_path)
        yield str(clone_path)
    finally:
        # Give any lingering Access process a moment to release the file
        import time
        time.sleep(0.25)
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass