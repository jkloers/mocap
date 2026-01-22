import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends, Request
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
from typing import Set
import asyncio
import sys
import time

# Add parent directory to path to allow imports when running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.hmm import LiveHMMRecognizer
import numpy as np
from pythonosc.udp_client import SimpleUDPClient
import re

# --- Configuration OSC ---
OSC_IP = "127.0.0.1"  # Adresse IP de destination OSC
OSC_PORT = 9000       # Port OSC de destination
OSC_BASE = "/mocap"   # Base des adresses OSC

def sanitize_osc_path(device_id: str) -> str:
    """Nettoie le device_id pour être valide dans une adresse OSC."""
    if not isinstance(device_id, str):
        device_id = str(device_id)
    return re.sub(r'[^A-Za-z0-9_\-]', '_', device_id)

# Initialiser le client OSC
try:
    osc_client = SimpleUDPClient(OSC_IP, OSC_PORT)
    print(f"✅ Client OSC initialisé → udp://{OSC_IP}:{OSC_PORT} (base: {OSC_BASE})")
except Exception as e:
    print(f"❌ Erreur lors de l'initialisation du client OSC : {e}")
    osc_client = None

# Initialiser l'application FastAPI
# L'instance de ConnectionManager sera maintenant gérée par l'application
app = FastAPI()

# --- CLASSE DE GESTION DES CONNEXIONS AMÉLIORÉE ---
class ConnectionManager:
    """
    Gère les connexions WebSocket en les séparant par rôle:
    - Source: L'application qui envoie les données de capteur (le téléphone).
    - Receiver: L'application qui reçoit les données (le pont OSC, etc.).
    """
    def __init__(self):
        # Clients qui envoient les données (on ne leur renvoie rien)
        self.source_connections: Set[WebSocket] = set()
        # Clients qui reçoivent les données (osc_sender.py)
        self.receiver_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket, client_type: str):
        await websocket.accept()
        
        if client_type == "source":
            self.source_connections.add(websocket)
        elif client_type == "receiver":
            self.receiver_connections.add(websocket)
        else:
            # Rejeter ou gérer les types inconnus si nécessaire
            raise ValueError(f"Type de client inconnu: {client_type}")


    def disconnect(self, websocket: WebSocket):
        self.source_connections.discard(websocket)
        self.receiver_connections.discard(websocket)

    async def broadcast(self, message: str):
        """
        Diffuse le message à TOUS les clients 'receiver' (ponts OSC, etc.)
        Cette méthode garantit que les 'source' n'ont pas de trafic inutile.
        """
        tasks = []
        # On itère UNIQUEMENT sur les récepteurs
        for connection in self.receiver_connections:
            tasks.append(connection.send_text(message))
            
        # Exécuter les envois et ignorer les erreurs de déconnexion (return_exceptions=True)
        await asyncio.gather(*tasks, return_exceptions=True)

# Création du gestionnaire unique (injection de dépendance)
manager = ConnectionManager()

def get_manager():
    """Fonction de dépendance pour l'injection du ConnectionManager."""
    return manager

recognizers = {}  # deviceId -> LiveHMMRecognizer

# --- Tâche périodique pour signal OSC de test ---
async def send_osc_test_signal():
    """Envoie un signal OSC de test toutes les 4 secondes pour vérifier la connexion."""
    test_counter = 0
    while True:
        await asyncio.sleep(4.0)  # Attendre 4 secondes
        if osc_client is not None:
            try:
                test_counter += 1
                osc_address = f"{OSC_BASE}/test/ping"
                '''osc_args = [
                    "test",                    # message de test
                    float(test_counter),       # compteur
                    float(time.time())         # timestamp
                ]'''
                osc_args = [
                    10        # timestamp
                ]
                osc_client.send_message(osc_address, osc_args)
                print(f"[OSC TEST] Signal de test envoyé #{test_counter} → {osc_address}")
            except Exception as e:
                print(f"[OSC TEST ERROR] Erreur lors de l'envoi du signal de test: {e}")

# --- Endpoint WebSocket ---
# Ajout d'un paramètre de requête 'client_type' pour identifier le rôle
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_type: str = Query(..., min_length=4),  # 'source' ou 'receiver'
    manager: ConnectionManager = Depends(get_manager)
):
    
    try:
        # Se connecter et identifier le client
        await manager.connect(websocket, client_type)
        print(f"WebSocket: Client '{client_type}' connecté. (Sources: {len(manager.source_connections)}, Receivers: {len(manager.receiver_connections)})")
        
        # Seul un client de type 'source' doit boucler et envoyer des données
        if client_type == "source":
            while True:
                # 1. Attendre un message de la SOURCE
                data = await websocket.receive_text()

                # --- Parse JSON source ---
                try:
                    payload = json.loads(data)
                except Exception:
                    payload = None

                if payload and isinstance(payload, dict):
                    device_id = payload.get("deviceId", "unknown")
                    sensors = payload.get("sensors") or {}

                    # Extract sensors (mêmes noms que osc_sender.py utilise) :contentReference[oaicite:6]{index=6}
                    acc = sensors.get("accelerometer") or sensors.get("acceleration") or {}
                    gyro = sensors.get("gyroscope") or {}
                    ori = sensors.get("orientation") or {}

                    sample = np.array([
                        float(acc.get("x", 0.0)), float(acc.get("y", 0.0)), float(acc.get("z", 0.0)),
                        float(gyro.get("x", 0.0)), float(gyro.get("y", 0.0)), float(gyro.get("z", 0.0)),
                        float(ori.get("alpha", 0.0)), float(ori.get("beta", 0.0)), float(ori.get("gamma", 0.0)),
                    ], dtype=np.float32)

                    rec = recognizers.get(device_id)
                    if rec is None:
                        rec = LiveHMMRecognizer(window_size=60, step_size=3)
                        recognizers[device_id] = rec

                    pred = rec.add_sample(sample)
                    if pred is not None:
                        print(f"[SERVER] Sending prediction to client: {pred['label']}")
                        msg = {
                            "type": "prediction",
                            "deviceId": device_id,
                            "label": pred["label"],
                            "margin": pred["margin"],
                            "activity": pred["activity"],
                            "timestamp": payload.get("timestamp"),
                            "seq": payload.get("seq"),
                        }

                        # 1) renvoyer au téléphone (IMPORTANT)
                        await websocket.send_text(json.dumps(msg))

                        # 2) optionnel: aussi broadcast aux receivers (OSC pourra ignorer)
                        await manager.broadcast(json.dumps(msg))
                        
                        # 3) Envoyer la prédiction via OSC (uniquement si geste détecté avec certitude)
                        if osc_client is not None:
                            try:
                                # Adresse OSC: /mocap/{deviceId}/prediction
                                sanitized_id = sanitize_osc_path(device_id)
                                osc_address = f"{OSC_BASE}/{sanitized_id}/prediction"
                                # Convertir le label en entier (1, 2 ou 3)
                                try:
                                    gesture_number = int(pred["label"])
                                except (ValueError, TypeError):
                                    # Si le label n'est pas un nombre, essayer d'extraire le chiffre
                                    gesture_number = 0
                                
                                # Envoyer uniquement le numéro du geste (1, 2 ou 3)
                                osc_args = [gesture_number]
                                osc_client.send_message(osc_address, osc_args)
                                print(f"[OSC] Envoyé: {osc_address} → {gesture_number}")
                            except Exception as e:
                                print(f"[OSC ERROR] Erreur lors de l'envoi OSC: {e}")


                # Traiter et logger
                try:
                    # Log de réception
                    print(f"[SERVER 8000] Reçu data de la source : {data[:50]}...")
                except Exception:
                    print("[SERVER 8000] Reçu un message non-texte.")
                    continue

                # 2. DIFFUSER le message à TOUS les 'receivers'
                await manager.broadcast(data)
                
        # Les clients 'receiver' attendent simplement d'être déconnectés par le serveur
        # ou ils bouclent côté client (comme osc_sender.py)
        else:
            # Maintient la connexion ouverte pour que 'osc_sender.py' puisse recevoir le broadcast
            await websocket.receive_text() 


    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"WebSocket: Client déconnecté. (Sources: {len(manager.source_connections)}, Receivers: {len(manager.receiver_connections)})")
    except ValueError as e:
        # Erreur si client_type est invalide
        print(f"Rejet de connexion: {e}")
    except Exception as e:
        # Gestion des erreurs générales, y compris Query validation error
        print(f"Erreur inattendue dans l'endpoint WS: {e}")
        manager.disconnect(websocket)

# --- Endpoint pour recevoir un CSV depuis le navigateur ---
@app.post("/upload_csv")
async def upload_csv(request: Request):
    """
    Reçoit un CSV envoyé par le navigateur (depuis le téléphone) et le sauvegarde sur le PC.
    """
    try:
        data = await request.body()  # Contenu brut du CSV
        ts = asyncio.get_event_loop().time()  # timestamp relatif
        # Nom du fichier avec timestamp réel
        from datetime import datetime
        file_name = f"dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path = Path(file_name)

        file_path.write_bytes(data)
        print(f"✅ Fichier CSV reçu et sauvegardé sous {file_path.resolve()}")
        return {"status": "ok", "file": file_name}

    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde du CSV : {e}")
        return {"status": "error", "detail": str(e)}


# --- Configuration des fichiers statiques ---
CLIENT_DIR = Path(__file__).resolve().parent.parent / "client"
app.mount("/", StaticFiles(directory=CLIENT_DIR, html=True), name="static")

# --- Démarrage de la tâche de test OSC ---
@app.on_event("startup")
async def startup_event():
    """Lance la tâche de test OSC au démarrage du serveur."""
    asyncio.create_task(send_osc_test_signal())
    print("✅ Tâche de test OSC démarrée (signal toutes les 4 secondes)")

# Lancer le serveur avec Uvicorn
if __name__ == "__main__":
    print("Lancement du serveur web + WebSocket sur http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
