import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
from typing import Set
import asyncio

# Gestin des buffers
from models.buffer import SensorBuffer

# Paramètres du buffer
WINDOW_SIZE = 100
STEP_SIZE = 50
NUM_FEATURES = 9

# Initialiser votre buffer (et votre modèle) UNE SEULE FOIS
sensor_buffer = SensorBuffer(WINDOW_SIZE, STEP_SIZE, NUM_FEATURES)

# Création de l'application FastAPI
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

    async def broadcast_to_receivers(self, message: str):
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

    async def broadcast_to_sources(self, message: str):
        """
        Diffuse le message à TOUS les clients 'source' (interface web) pour
        leur permettre d'afficher les prédictions du modèle.
        """
        tasks = []
        for connection in self.source_connections:
            tasks.append(connection.send_text(message))

        await asyncio.gather(*tasks, return_exceptions=True)

# Création du gestionnaire unique (injection de dépendance)
manager = ConnectionManager()

def get_manager():
    """Fonction de dépendance pour l'injection du ConnectionManager."""
    return manager

# --- Endpoint WebSocket ---
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

                # Traiter et logger
                try:
                    # Log de réception
                    print(f"[SERVER 8000] Reçu data de la source : {data[:50]}...")
                except Exception:
                    print("[SERVER 8000] Reçu un message non-texte.")
                    continue

                # Intégrer les données dans le buffer
                try:
                    payload = json.loads(data)
                    sensors = payload.get("sensors", {}) or {}

                    accel = sensors.get("accelerometer") or sensors.get("acceleration") or {}
                    gyro = sensors.get("gyroscope") or {}
                    orientation = sensors.get("orientation") or {}

                    def to_float(v, default=0.0):
                        try:
                            return float(v)
                        except Exception:
                            return float(default)

                    ax = to_float(accel.get("x") if "x" in accel else accel.get("alpha"))
                    ay = to_float(accel.get("y") if "y" in accel else accel.get("beta"))
                    az = to_float(accel.get("z") if "z" in accel else accel.get("gamma"))

                    # gyroscope may be provided as x,y,z or alpha,beta,gamma
                    if all(k in gyro for k in ("x", "y", "z")):
                        gx = to_float(gyro.get("x"))
                        gyv = to_float(gyro.get("y"))
                        gz = to_float(gyro.get("z"))
                    else:
                        gx = to_float(gyro.get("alpha"))
                        gyv = to_float(gyro.get("beta"))
                        gz = to_float(gyro.get("gamma"))

                    # orientation as alpha,beta,gamma
                    oa = to_float(orientation.get("alpha"))
                    ob = to_float(orientation.get("beta"))
                    oc = to_float(orientation.get("gamma"))

                    sample = [ax, ay, az, gx, gyv, gz, oa, ob, oc]

                    # Ajouter l'échantillon au buffer (la méthode gère la fenêtre et l'appel à process_window)
                    sensor_buffer.add_data(sample)

                except json.JSONDecodeError:
                    print("[BUFFER] JSON invalide, skip buffer add.")
                except Exception as e:
                    print(f"[BUFFER] Erreur ajout buffer: {e}")

                # 2. DIFFUSER le message à TOUS les 'receivers'
                await manager.broadcast_to_receivers(data)
                
        # Les clients 'receiver' attendent simplement d'être déconnectés par le serveur
        # ou ils bouclent côté client (comme osc_sender.py)
        else:
            # Écoute des messages envoyés par les receivers (ex: les prédictions du modèle)
            while True:
                prediction_message = await websocket.receive_text()
                try:
                    print(f"[SERVER 8000] Reçu data receiver : {prediction_message[:50]}...")
                except Exception:
                    print("[SERVER 8000] Reçu un message receiver non-texte.")
                    continue

                # Diffuser la prédiction à tous les clients source (interface web)
                await manager.broadcast_to_sources(prediction_message)


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

# --- Configuration des fichiers statiques ---
CLIENT_DIR = Path(__file__).resolve().parent.parent / "client"
app.mount("/", StaticFiles(directory=CLIENT_DIR, html=True), name="static")

# Lancer le serveur avec Uvicorn
if __name__ == "__main__":
    print("Lancement du serveur web + WebSocket sur http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

