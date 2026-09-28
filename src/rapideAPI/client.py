import requests
from typing import Any, Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)

class RapideAPI:
    """
    Un client HTTP miniature et élégant, conçu pour minimiser la mise en place
    des requêtes API, similaire à l'approche de FastAPI mais pour le côté client.
    """
    
    def __init__(self, base_url: str = "", default_headers: Optional[Dict[str, str]] = None, timeout: int = 120):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        if default_headers:
            self.session.headers.update(default_headers)

    def _build_url(self, endpoint: str) -> str:
        """Construit l'URL finale en combinant la base et l'endpoint."""
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Méthode centrale pour envoyer des requêtes et gérer les erreurs."""
        import time
        url = self._build_url(endpoint)
        kwargs.setdefault("timeout", self.timeout)

        logger.info(f"==> [{method}] {url}")
        logger.debug(f"Payload/Params: {kwargs}")

        start_time = time.time()
        try:
            response = self.session.request(method, url, **kwargs)
            duration = time.time() - start_time
            logger.info(f"<== [{method}] {url} - Status: {response.status_code} - Temps: {duration:.2f}s")
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            duration = time.time() - start_time
            error_body = response.text
            logger.error(f"[!] Erreur HTTP {response.status_code} après {duration:.2f}s : {error_body}")
            raise e
        except requests.exceptions.Timeout as e:
            duration = time.time() - start_time
            logger.error(f"[!] TIMEOUT après {duration:.2f}s sur la requête [{method}] {url}")
            raise e
        except requests.exceptions.RequestException as e:
            duration = time.time() - start_time
            logger.error(f"[!] Erreur de connexion après {duration:.2f}s : {e}")
            raise e

        # Si l'utilisateur demande un stream, on renvoie l'objet réponse brut
        if kwargs.get("stream"):
            return response

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            try:
                return response.json()
            except ValueError:
                return response.text
                
        return response.text

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        return self.request("GET", endpoint, params=params, **kwargs)

    def stream_ndjson(self, endpoint: str, data: Optional[Union[Dict, str]] = None, json_data: Optional[Dict] = None, **kwargs):
        """Envoie une requête POST et lit la réponse en tant que flux NDJSON (Newline Delimited JSON)."""
        import json
        response = self.request("POST", endpoint, data=data, json=json_data, stream=True, **kwargs)
        
        for line in response.iter_lines():
            if line:
                yield json.loads(line.decode("utf-8"))

    def post(self, endpoint: str, data: Optional[Union[Dict, str]] = None, json: Optional[Dict] = None, **kwargs) -> Any:
        return self.request("POST", endpoint, data=data, json=json, **kwargs)

    def put(self, endpoint: str, data: Optional[Union[Dict, str]] = None, json: Optional[Dict] = None, **kwargs) -> Any:
        return self.request("PUT", endpoint, data=data, json=json, **kwargs)

    def delete(self, endpoint: str, **kwargs) -> Any:
        return self.request("DELETE", endpoint, **kwargs)

    def patch(self, endpoint: str, data: Optional[Union[Dict, str]] = None, json: Optional[Dict] = None, **kwargs) -> Any:
        return self.request("PATCH", endpoint, data=data, json=json, **kwargs)

    def health(self):
        health = self.request("GET", "api/version")
        print(health)
        return health is not None
