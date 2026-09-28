from client import RapideAPI

# 1. Initialisation unique avec les configurations de base (comme une instance FastAPI)
api = RapideAPI(
    base_url="https://jsonplaceholder.typicode.com",
    default_headers={"Authorization": "Bearer MON_TOKEN"}
)

# 2. Utilisation propre et minimaliste partout dans ton code
def fetch_users():
    """Récupère une liste d'utilisateurs."""
    # L'URL finale sera https://jsonplaceholder.typicode.com/users
    users = api.get("/users")
    print(f"Nombre d'utilisateurs: {len(users)}")
    return users

def create_post(title: str, body: str, user_id: int):
    """Crée un nouvel article via un payload JSON."""
    payload = {
        "title": title,
        "body": body,
        "userId": user_id
    }
    # La conversion en JSON et la gestion des headers sont automatiques
    response = api.post("/posts", json=payload)
    print(f"Article créé avec l'ID: {response.get('id')}")
    return response

if __name__ == "__main__":
    fetch_users()
    create_post("Mon super titre", "Le contenu de mon article", 1)
