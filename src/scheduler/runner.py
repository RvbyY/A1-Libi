import logging

from src.scheduler.task_manager import TaskManager

logger = logging.getLogger("sensai.scheduler")
    

class TaskRunner:
    def __init__(self, session):
        self.task_manager = TaskManager(session)

    def run_due_tasks(self):
        tasks = self.task_manager.get_due_tasks()

        for task in tasks:
            try:
                logger.info(
                    f"[Scheduler] Exécution de la tâche {task.id}: {task.prompt}"
                )

                print(f"[ScheduledTask] {task.prompt}")

                self.task_manager.mark_completed(task)

            except Exception as exc:
                logger.exception(
                    f"[Scheduler] Échec de la tâche {task.id}: {exc}"
                )
                self.task_manager.mark_failed(task)