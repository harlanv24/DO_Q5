from app.database import Base, engine
import app.models  # noqa: F401


def pytest_sessionstart(session) -> None:  # noqa: ANN001
    # Ensure schema exists in clean CI environments before any tests run.
    Base.metadata.create_all(bind=engine)
