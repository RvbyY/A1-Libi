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


def test_schedule_parser_modes_and_reschedule():
    from src.scheduler.parser import ScheduleParser

    spec_in = ScheduleParser.parse("in 15m Vérifier les logs")
    assert spec_in.prompt == "Vérifier les logs"
    assert spec_in.recurrence is None
    assert spec_in.scheduled_at > datetime.now()

    spec_daily = ScheduleParser.parse("daily 08:30 Briefing matin")
    assert spec_daily.recurrence == "daily"
    assert spec_daily.scheduled_at.hour == 8
    assert spec_daily.scheduled_at.minute == 30

    spec_weekly = ScheduleParser.parse("weekly lundi 14:00 Point hebdo")
    assert spec_weekly.recurrence == "weekly:lundi"

    spec_every = ScheduleParser.parse("every 2h Check serveur")
    assert spec_every.recurrence == "every:2h"

    session = make_session()
    profile = create_profile(session)
    manager = TaskManager(session)
    base_time = datetime.now()
    recurring_task = manager.create_task(
        profile_id=profile.id,
        prompt="Recurring check",
        scheduled_at=base_time,
        recurrence="daily",
    )
    manager.reschedule_recurring_task(recurring_task)
    assert recurring_task.status == "pending"
    assert recurring_task.scheduled_at == base_time + timedelta(days=1)