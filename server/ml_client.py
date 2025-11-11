import asyncio
import websockets
import json
import numpy as np
import sys
from pathlib import Path

# --- IMPORTANT ---
# On ajoute le dossier parent au 'path' pour trouver le dossier 'models'
# (C'est là que se trouve buffer.py)
current_dir = Path(__file__).resolve().parent
sys.path.append(str(current_dir))

# On importe la classe Buffer que ton ami a déjà codée
from models.buffer import SensorBuffer

# --- Configuration (doit être IDENTIQUE à main.py) ---
WINDOW_SIZE = 100
STEP_SIZE = 50
NUM_FEATURES = 9 # (accel_x,y,z, gyro_x,y,z, orient_a,b,c)

# On initialise le buffer QUI CONTIENDRA LE MODÈLE ML
# C'est ce buffer qui fera le travail.
print("Initialisation du buffer pour le client ML...")
sensor_buffer = SensorBuffer(WINDOW_SIZE, STEP_SIZE, NUM_FEATURES)
print("Buffer prêt. Tentative de connexion au serveur...")

# Fonction pour parser le JSON (idem que dans main.py)
def parse_data_to_sample(data: str) -> list | None:
    try:
        payload = json.loads(data)
        sensors = payload.get("sensors", {}) or {}

        accel = sensors.get("accelerometer") or sensors.get("acceleration") or {}
        gyro = sensors.get("gyroscope") or {}
        orientation = sensors.get("orientation") or {}

        def to_float(v, default=0.0):
            try: return float(v)
            except Exception: return float(default)

        ax = to_float(accel.get("x") if "x" in accel else accel.get("alpha"))
        ay = to_float(accel.get("y") if "y" in accel else accel.get("beta"))
        az = to_float(accel.get("z") if "z" in accel else accel.get("gamma"))

        if all(k in gyro for k in ("x", "y", "z")):
            gx, gyv, gz = to_float(gyro.get("x")), to_float(gyro.get("y")), to_float(gyro.get("z"))
        else:
            gx, gyv, gz = to_float(gyro.get("alpha")), to_float(gyro.get("beta")), to_float(gyro.get("gamma"))

        oa, ob, oc = to_float(orientation.get("alpha")), to_float(orientation.get("beta")), to_float(orientation.get("gamma"))
        
        return [ax, ay, az, gx, gyv, gz, oa, ob, oc]

    except Exception as e:
        print(f"[CLIENT] Erreur parsing JSON: {e}")
        return None

async def run_ml_client():
    """
    Se connecte au serveur en tant que 'receiver' et alimente le buffer.
    Lorsque le modèle effectue une prédiction, elle est renvoyée via le WebSocket.
    """
    uri = "ws://localhost:8000/ws?client_type=receiver"
    
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                print(f"Connecté à {uri}")

                async for message in websocket:
                    # 1. On reçoit les données brutes
                    # print(f"Reçu: {message[:50]}...") # Pour debugging

                    # 2. On les parse pour avoir notre [ax, ay, ...]
                    sample = parse_data_to_sample(message)

                    if sample:
                        # 3. On ajoute l'échantillon au buffer
                        # Si add_data retourne une prédiction, on l'envoie au client WebSocket
                        prediction = sensor_buffer.add_data(sample)
                        if prediction is not None:
                            # Formate la prédiction pour l'envoyer (JSON)
                            try:
                                # paquet de réponse: { "type": "prediction", "result": ... }
                                pred_payload = {
                                    "type": "prediction",
                                    "result": prediction
                                }
                                await websocket.send(json.dumps(pred_payload))
                                print(f"[CLIENT] Prédiction envoyée: {prediction}")
                            except Exception as e:
                                print(f"[CLIENT] Erreur lors de l'envoi de la prédiction: {e}")

        except websockets.exceptions.ConnectionClosed:
            print("Connexion perdue. Tentative de reconnexion dans 3s...")
            await asyncio.sleep(3)
        except Exception as e:
            print(f"Erreur: {e}. Tentative de reconnexion dans 3s...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    try:
        asyncio.run(run_ml_client())
    except KeyboardInterrupt:
        print("Arrêt du client ML.")