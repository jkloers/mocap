import asyncio
import json
import re
import websockets
from pythonosc.udp_client import SimpleUDPClient

# -------------------------------------------------------------------
# 1. CONFIGURATION
# -------------------------------------------------------------------
# URI du serveur WebSocket (correspond à /ws?client_type=receiver)
WS_SERVER_URI = "ws://127.0.0.1:8000/ws?client_type=receiver"

# Destination OSC (par défaut : localhost:9000)
OSC_IP = "127.0.0.1"
OSC_PORT = 9000

# Base des adresses OSC
OSC_BASE = "/mocap"

# -------------------------------------------------------------------
# 2. UTILITAIRES
# -------------------------------------------------------------------
def sanitize_id(device_id: str) -> str:
    """Nettoie le device_id pour être sûr qu’il soit valide dans une adresse OSC."""
    if not isinstance(device_id, str):
        device_id = str(device_id)
    return re.sub(r'[^A-Za-z0-9_\-]', '_', device_id)

def safe_float(v, default=0.0):
    """Convertit en float sans lever d’erreur."""
    try:
        return float(v)
    except Exception:
        return float(default)

def osc_send(addr: str, common_args: list, extra: list):
    """
    Envoie un message OSC en filtrant les None et en gérant les erreurs.
    """
    args = [a for a in common_args if a is not None]
    args.extend(extra)
    try:
        osc_client.send_message(addr, args)
    except Exception as e:
        print(f"[ERROR] Envoi OSC vers {addr} échoué : {e}")

# -------------------------------------------------------------------
# 3. INITIALISATION CLIENT OSC
# -------------------------------------------------------------------
try:
    osc_client = SimpleUDPClient(OSC_IP, OSC_PORT)
    print(f"✅ Client OSC prêt → udp://{OSC_IP}:{OSC_PORT} (base: {OSC_BASE})")
except Exception as e:
    print(f"❌ Erreur lors de la création du client OSC : {e}")
    raise

# -------------------------------------------------------------------
# 4. PONT WS → OSC
# -------------------------------------------------------------------
async def ws_bridge():
    """
    Se connecte au serveur WebSocket et traduit les messages JSON reçus en messages OSC.
    Garde la connexion ouverte indéfiniment (reconnexion automatique en cas d’échec).
    """
    while True:
        try:
            async with websockets.connect(
                WS_SERVER_URI,
                ping_interval=20,
                ping_timeout=20,
                max_queue=32,
                close_timeout=5
            ) as websocket:
                print(f"🔌 Connecté au serveur WebSocket : {WS_SERVER_URI}")
                
                async for message in websocket:
                    print("[INFO] Message WS reçu — décodage...")

                    # --- Décodage JSON ---
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        print("[ERROR] Message WS non valide (pas JSON). Ignoré.")
                        continue

                    device_id = data.get("deviceId", "unknown")
                    seq = data.get("seq")
                    timestamp = data.get("timestamp")
                    sensors = data.get("sensors", {}) or {}

                    sid = sanitize_id(device_id)
                    common_args = []

                    # Ajoute seq et timestamp si dispo
                    try:
                        common_args.append(int(seq))
                    except Exception:
                        common_args.append(None)
                    try:
                        common_args.append(int(timestamp))
                    except Exception:
                        common_args.append(None)

                    # === 1) ACCELEROMÈTRE ===
                    accel = sensors.get("accelerometer") or sensors.get("acceleration")
                    if accel:
                        ax, ay, az = (
                            safe_float(accel.get("x")),
                            safe_float(accel.get("y")),
                            safe_float(accel.get("z")),
                        )
                        addr = f"{OSC_BASE}/{sid}/accelerometer"
                        osc_send(addr, common_args, [ax, ay, az])

                    # === 2) GYROSCOPE ===
                    gyro = sensors.get("gyroscope")
                    if gyro:
                        if all(k in gyro for k in ("x", "y", "z")):
                            ga, gb, gc = map(safe_float, (gyro["x"], gyro["y"], gyro["z"]))
                        elif all(k in gyro for k in ("alpha", "beta", "gamma")):
                            ga, gb, gc = map(
                                safe_float, (gyro["alpha"], gyro["beta"], gyro["gamma"])
                            )
                        else:
                            print("[WARN] Gyro sans composantes reconnues :", gyro)
                            ga = gb = gc = 0.0
                        addr = f"{OSC_BASE}/{sid}/gyroscope"
                        osc_send(addr, common_args, [ga, gb, gc])

                    # === 3) ORIENTATION ===
                    orient = sensors.get("orientation")
                    if orient:
                        oa, ob, oc = (
                            safe_float(orient.get("alpha")),
                            safe_float(orient.get("beta")),
                            safe_float(orient.get("gamma")),
                        )
                        addr = f"{OSC_BASE}/{sid}/orientation"
                        osc_send(addr, common_args, [oa, ob, oc])

        except websockets.exceptions.ConnectionClosed as e:
            print(f"[WARN] Connexion WS fermée : {e}. Tentative de reconnexion dans 5s...")
            await asyncio.sleep(5)
        except (ConnectionRefusedError, websockets.exceptions.InvalidURI) as e:
            print(f"[WARN] Serveur WebSocket injoignable : {e}. Nouvelle tentative dans 5s...")
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            print("🛑 Arrêt manuel demandé (Ctrl+C).")
            break
        except Exception as e:
            print(f"[ERROR] Erreur inattendue : {e}. Nouvelle tentative dans 5s...")
            await asyncio.sleep(5)

# -------------------------------------------------------------------
# 5. MAIN
# -------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Démarrage du pont WebSocket → OSC (Ctrl+C pour quitter)")
    try:
        asyncio.run(ws_bridge())
    except KeyboardInterrupt:
        print("🛑 Arrêt demandé par l’utilisateur.")
