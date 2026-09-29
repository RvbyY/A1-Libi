def update_db(table: str, record_id: str, fields: dict) -> dict:
    """Met à jour un enregistrement existant."""

def insert_db(table: str, data: dict) -> dict:
    """Insère un nouvel enregistrement, retourne l'id créé."""

def query_db(table: str, filters: dict, limit: int = 10) -> list[dict]:
    """Récupère des enregistrements filtrés."""

def delete_db(table: str, record_id: str) -> bool:
    """Supprime un enregistrement."""