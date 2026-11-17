import os
import shutil
import sys
import tempfile


_test_root = tempfile.mkdtemp(prefix="teacher-system-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_test_root, 'test.db').replace(os.sep, '/')}"
os.environ["DATA_DIR"] = _test_root
os.environ["STORAGE_ROOT"] = os.path.join(_test_root, "storage")
os.environ["ENABLE_DEMO_SEED"] = "0"
os.environ["PILOT_ACCESS_PIN"] = "test-pin"
os.environ["CORS_ORIGIN_REGEX"] = ""
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.app.database import Base, engine


def pytest_sessionstart(session):
    Base.metadata.create_all(bind=engine)


def pytest_sessionfinish(session, exitstatus):
    Base.metadata.drop_all(bind=engine)
    shutil.rmtree(_test_root, ignore_errors=True)


