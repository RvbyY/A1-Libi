import logging
import time

from src.scheduler.task_manager import TaskManager

logger = logging.getLogger("sensai.scheduler")


class TaskRunner:
    def __init__(self, session_factory, executor):
        self.session_factory = session_factory
        self.executor = executor

    def run_due_tasks(self):
        session = self.session_factory()

        try:
            task_manager = TaskManager(session)
            tasks = task_manager.get_due_tasks()

            for task in tasks:
                try:
                    logger.info(
                        f"[Scheduler] Exécution de la tâche {task.id}: {task.prompt}"
                    )

                    response = self.executor(task.prompt)
                    print(f"\nSensAI [scheduled] : {response}")

                    task_manager.mark_completed(task)

                except Exception as exc:
                    logger.exception(
                        f"[Scheduler] Échec de la tâche {task.id}: {exc}"
                    )
                    task_manager.mark_failed(task)

        finally:
            session.close()

    def run_forever(self, interval: int = 5):
        while True:
            self.run_due_tasks()
            time.sleep(interval)