from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.galerelm.models import Base, Profile
from src.scheduler.task_manager import TaskManager


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    return Session()


def create_profile(session):
    profile = Profile(
        name="Test User",
        email="test@sensai.ai",
        instructions="Test instructions",
    )
    session.add(profile)
    session.commit()
    return profile


def test_create_scheduled_task():
    session = make_session()
    profile = create_profile(session)
    manager = TaskManager(session)

    task = manager.create_task(
        profile_id=profile.id,
        prompt="say hello",
        scheduled_at=datetime.now() + timedelta(minutes=10),
    )

    assert task.id is not None
    assert task.profile_id == profile.id
    assert task.prompt == "say hello"
    assert task.status == "pending"


def test_get_due_tasks_returns_past_pending_tasks():
    session = make_session()
    profile = create_profile(session)
    manager = TaskManager(session)

    manager.create_task(
        profile_id=profile.id,
        prompt="due task",
        scheduled_at=datetime.now() - timedelta(minutes=1),
    )

    due_tasks = manager.get_due_tasks()

    assert len(due_tasks) == 1
    assert due_tasks[0].prompt == "due task"


def test_get_due_tasks_ignores_future_tasks():
    session = make_session()
    profile = create_profile(session)
    manager = TaskManager(session)

    manager.create_task(
        profile_id=profile.id,
        prompt="future task",
        scheduled_at=datetime.now() + timedelta(hours=1),
    )

    due_tasks = manager.get_due_tasks()

    assert due_tasks == []


def test_mark_completed():
    session = make_session()
    profile = create_profile(session)
    manager = TaskManager(session)

    task = manager.create_task(
        profile_id=profile.id,
        prompt="complete me",
        scheduled_at=datetime.now() - timedelta(minutes=1),
    )

    manager.mark_completed(task)

    assert task.status == "completed"


def test_cancel_task():
    session = make_session()
    profile = create_profile(session)
    manager = TaskManager(session)

    task = manager.create_task(
        profile_id=profile.id,
        prompt="cancel me",
        scheduled_at=datetime.now() + timedelta(minutes=10),
    )

    manager.cancel_task(task)

    assert task.status == "cancelled"