import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Depends, Request
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import json
from typing import Set
import asyncio

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

# Lancer le serveur avec Uvicorn
if __name__ == "__main__":
    print("Lancement du serveur web + WebSocket sur http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
