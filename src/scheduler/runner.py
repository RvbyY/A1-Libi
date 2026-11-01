"""
Module scheduler/runner.py
TaskRunner : exécute en arrière-plan les tâches planifiées arrivées à échéance.

Chaque passage ouvre sa propre session SQLAlchemy : le runner tourne dans un thread séparé
et ne partage jamais la session du terminal ou de la webapp.
"""
import logging
import threading
from typing import Any, Callable, Optional

from src.scheduler.task_manager import TaskManager

logger = logging.getLogger("sensai.scheduler")

# executor(task, session) -> réponse du modèle
TaskExecutor = Callable[[Any, Any], str]
# on_result(task, réponse ou None, erreur ou None)
TaskResultCallback = Callable[[Any, Optional[str], Optional[Exception]], None]


class TaskRunner:
    def __init__(self, session_factory, executor: TaskExecutor, on_result: Optional[TaskResultCallback] = None):
        self.session_factory = session_factory
        self.executor = executor
        self.on_result = on_result
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def run_due_tasks(self) -> int:
        """Exécute les tâches dues, reprogramme les récurrentes. Retourne le nombre de tâches traitées."""
        session = self.session_factory()
        processed = 0
        try:
            task_manager = TaskManager(session)
            for task in task_manager.get_due_tasks():
                processed += 1
                try:
                    logger.info(f"[Scheduler] Exécution de la tâche {task.id}: {task.prompt}")
                    response = self.executor(task, session)
                    if task.recurrence:
                        task_manager.reschedule_recurring_task(task)
                    else:
                        task_manager.mark_completed(task)
                    self._notify(task, response, None)
                except Exception as exc:
                    logger.exception(f"[Scheduler] Échec de la tâche {task.id}: {exc}")
                    session.rollback()
                    task_manager.mark_failed(task)
                    self._notify(task, None, exc)
        finally:
            session.close()
        return processed

    def _notify(self, task, response: Optional[str], error: Optional[Exception]) -> None:
        if self.on_result is None:
            return
        try:
            self.on_result(task, response, error)
        except Exception as exc:
            logger.error(f"[Scheduler] Échec de la notification de la tâche {task.id}: {exc}")

    def run_forever(self, interval: float = 5) -> None:
        """Boucle de vérification, jusqu'à stop(). Une erreur inattendue n'arrête pas la boucle."""
        while not self._stop.is_set():
            try:
                self.run_due_tasks()
            except Exception as exc:
                logger.exception(f"[Scheduler] Erreur pendant la vérification des tâches : {exc}")
            self._stop.wait(interval)

    def start(self, interval: float = 5) -> threading.Thread:
        """Lance la boucle dans un thread en arrière-plan (daemon : il s'arrête avec le programme)."""
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._stop.clear()
        self._thread = threading.Thread(target=self.run_forever, args=(interval,), name="sensai-scheduler", daemon=True)
        self._thread.start()
        logger.info(f"[Scheduler] Démarré (vérification toutes les {interval} s).")
        return self._thread

    def stop(self, timeout: float = 5) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)
            self._thread = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
