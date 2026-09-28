#!/usr/bin/env bash
set -e

source .env

# Gestion propre de l'interruption (Ctrl+C)
trap 'echo -e "\n[+] Arrêt de backend.sh..."; [ "$STARTED_BY_SCRIPT" -eq 1 ] && kill $OLLAMA_PID 2>/dev/null; exit 0' INT TERM

# 1. Démarrer le serveur Ollama si non actif
if ! pgrep -x "ollama" > /dev/null; then
    echo "[+] Lancement d'Ollama en tâche de fond..."
    export OLLAMA_KEEP_ALIVE=-1
    # On redirige la sortie vers un fichier de log au lieu de /dev/null
    ollama serve > ollama.log 2>&1 &
    OLLAMA_PID=$!
    STARTED_BY_SCRIPT=1
else
    OLLAMA_PID=$(pgrep -x "ollama" | head -n 1)
    echo "[*] Ollama est déjà en cours d'exécution (PID: $OLLAMA_PID)."
    STARTED_BY_SCRIPT=0
fi

# 2. Vérifier la disponibilité de l'API HTTP
echo "[*] Attente du serveur sur $OLLAMA_HOST..."
until curl -s "$OLLAMA_HOST/api/tags" > /dev/null; do
    sleep 0.5
done
echo "[+] API Ollama opérationnelle."

# 3. Télécharger le modèle Hugging Face s'il n'est pas déjà présent
echo "[*] Vérification de la présence locale de $HF_MODEL..."
if ! curl -s "$OLLAMA_HOST/api/tags" | grep -q "$HF_MODEL"; then
    echo "[!] Modèle absent. Téléchargement depuis Hugging Face en cours..."
    ollama pull "$HF_MODEL"
else
    echo "[+] Modèle déjà disponible localement."
fi

# 4. Précharger et verrouiller le modèle en VRAM/RAM (Keep-Alive infini)
echo "[*] POST /api/generate (Préchargement du modèle en mémoire...)"
response=$(curl -s -w "\n%{http_code}" -X POST "$OLLAMA_HOST/api/generate" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$HF_MODEL\",
    \"keep_alive\": -1
  }")

http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" -ne 200 ]; then
    echo "[!] ERREUR HTTP $http_code lors du POST /api/generate: $body" >&2
    exit 1
else
    echo "[+] Requête réussie (HTTP $http_code). Modèle préchargé."
fi

echo "[✓] Prêt ! Le backend écoute sur $OLLAMA_HOST avec $HF_MODEL chargé."
echo "------------------------------------------------------------------"

if [ "$STARTED_BY_SCRIPT" -eq 1 ]; then
    echo "[*] Affichage en direct des logs Ollama (Appuyez sur Ctrl+C pour quitter)..."
    # On affiche les logs en continu et on bloque le script
    tail -f ollama.log &
    TAIL_PID=$!
    wait $OLLAMA_PID
    kill $TAIL_PID 2>/dev/null
else
    echo "[*] Surveillance du processus Ollama actif (Appuyez sur Ctrl+C pour quitter)..."
    # Ollama tournait déjà, on bloque simplement le script tant qu'il tourne
    while kill -0 $OLLAMA_PID 2>/dev/null; do
        sleep 2
    done
    echo "[-] Le processus Ollama externe s'est arrêté."
fi
