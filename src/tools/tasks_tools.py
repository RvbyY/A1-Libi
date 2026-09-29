def create_task(description: str, due_date: str = None, priority: str = "normal") -> dict:
    """Crée une tâche à faire."""

def complete_task(task_id: str) -> bool:
    """Marque une tâche comme terminée."""

def list_pending_tasks(user_id: str) -> list[dict]:
    """Liste les tâches en attente."""