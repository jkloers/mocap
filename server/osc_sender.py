import asyncio
import json
import re
import websockets
from pythonosc.udp_client import SimpleUDPClient

# -------------------------------------------------------------------
# 1. CONFIGURATION 
# -------------------------------------------------------------------
# URI du serveur WebSocket (adapter si votre endpoint WS est /ws)
WS_SERVER_URI = "ws://127.0.0.1:8000/ws?client_type=receiver"

# Destination OSC (VCV Rack / MaxMSP)
OSC_IP = "127.0.0.1"
OSC_PORT = 9000

# Base de l'adresse OSC (les capteurs seront envoyés sous /mocap/<deviceId>/...)
OSC_BASE = "/mocap"

# -------------------------------------------------------------------
# 2. UTILITAIRES
# -------------------------------------------------------------------
def sanitize_id(device_id: str) -> str:
    """Remplace les caractères non sûrs par '_' pour utilisation dans une adresse OSC."""
    if not isinstance(device_id, str):
        device_id = str(device_id)
    return re.sub(r'[^A-Za-z0-9_\-]', '_', device_id)

def safe_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return float(default)

# -------------------------------------------------------------------
# 3. INITIALISATION CLIENT OSC
# -------------------------------------------------------------------
try:
    osc_client = SimpleUDPClient(OSC_IP, OSC_PORT)
    print(f"Client OSC prêt → udp://{OSC_IP}:{OSC_PORT} (base: {OSC_BASE})")
except Exception as e:
    print(f"Erreur lors de la création du client OSC : {e}")
    # En cas d'échec de l'initialisation de l'OSC, l'application ne peut pas fonctionner.
    raise

# -------------------------------------------------------------------
# 4. PONT WS → OSC : ENVOI SÉPARÉ PAR CAPTEUR (MEILLEURE PRATIQUE)
# -------------------------------------------------------------------
async def ws_bridge():
    """
    Se connecte au serveur WebSocket et envoie, pour chaque message JSON reçu,
    un message OSC distinct par type de capteur.
    """
    while True:
        try:
            # Tente d'établir une connexion WS
            async with websockets.connect(WS_SERVER_URI) as websocket:
                print(f"Connecté au serveur WebSocket : {WS_SERVER_URI}")
                
                # --- DÉBUT DE LA BOUCLE DE RÉCEPTION ---
                try:
                    async for message in websocket:
                        # LE MESSAGE SE LOGUE SEULEMENT ICI LORSQU'IL EST ENVOYÉ PAR LE SERVEUR
                        print("[INFO] Message WS reçu - Décodage...")
                        
                        try:
                            data = json.loads(message)
                            # print(f"WS data received: {data}") # Commenté pour éviter le spam, décommenter si besoin
                        except json.JSONDecodeError:
                            print("[ERROR] Message WS non JSON, skip.")
                            continue

                        device_id = data.get("deviceId", "unknown")
                        seq = data.get("seq", None)
                        timestamp = data.get("timestamp", None)
                        sensors = data.get("sensors", {}) or {}

                        sid = sanitize_id(device_id)

                        # helper to build common prefix args
                        common_args = []
                        if seq is not None:
                            try:
                                common_args.append(int(seq))
                            except Exception:
                                common_args.append(str(seq))
                        else:
                            common_args.append(None)
                        
                        if timestamp is not None:
                            try:
                                common_args.append(int(timestamp))
                            except Exception:
                                common_args.append(str(timestamp))
                        else:
                            common_args.append(None)


                        # 1) ACCELEROMETER (x,y,z)
                        accel = sensors.get("accelerometer") or sensors.get("acceleration")
                        if accel:
                            ax = safe_float(accel.get("x"))
                            ay = safe_float(accel.get("y"))
                            az = safe_float(accel.get("z"))
                            addr = f"{OSC_BASE}/{sid}/accelerometer"
                            args = [a for a in common_args]  # copy
                            args.extend([ax, ay, az])
                            try:
                                osc_client.send_message(addr, args)
                                # print(f"OSC -> {addr} {args}") # Commenté pour éviter le spam, décommenter si besoin
                            except Exception as e:
                                print(f"[ERROR] Erreur envoi OSC accel: {e}")

                        # 2) GYROSCOPE (alpha/beta/gamma or x/y/z)
                        gyro = sensors.get("gyroscope")
                        if gyro:
                            # prefer x,y,z keys, fallback to alpha/beta/gamma
                            if all(k in gyro for k in ("alpha","beta","gamma")):
                                ga = safe_float(gyro.get("alpha"))
                                gb = safe_float(gyro.get("beta"))
                                gc = safe_float(gyro.get("gamma"))
                            else:
                                ga = safe_float(gyro.get("x"))
                                gb = safe_float(gyro.get("y"))
                                gc = safe_float(gyro.get("z"))
                            addr = f"{OSC_BASE}/{sid}/gyroscope"
                            args = [a for a in common_args]
                            args.extend([ga, gb, gc])
                            try:
                                osc_client.send_message(addr, args)
                                # print(f"OSC -> {addr} {args}") # Commenté pour éviter le spam, décommenter si besoin
                            except Exception as e:
                                print(f"[ERROR] Erreur envoi OSC gyro: {e}")

                        # 3) ORIENTATION (alpha/beta/gamma)
                        orient = sensors.get("orientation")
                        if orient:
                            oa = safe_float(orient.get("alpha"))
                            ob = safe_float(orient.get("beta"))
                            oc = safe_float(orient.get("gamma"))
                            addr = f"{OSC_BASE}/{sid}/orientation"
                            args = [a for a in common_args]
                            args.extend([oa, ob, oc])
                            try:
                                osc_client.send_message(addr, args)
                                # print(f"OSC -> {addr} {args}") # Commenté pour éviter le spam, décommenter si besoin
                            except Exception as e:
                                print(f"[ERROR] Erreur envoi OSC orientation: {e}")
                
                except websockets.exceptions.ConnectionClosed as e:
                    # Capture la fermeture de la connexion (ex. si le serveur tombe après la connexion)
                    print(f"[WARN] Connexion WS fermée de manière inattendue : {e}")

        except (websockets.exceptions.InvalidURI, ConnectionRefusedError) as e:
            print(f"[WARN] Connexion WS impossible (serveur 8000 non actif ou URI invalide) : {e}. Nouvelle tentative dans 5s...")
            await asyncio.sleep(5)
        except KeyboardInterrupt:
            print("Interruption clavier, arrêt.")
            break
        except Exception as e:
            print(f"[ERROR] Erreur inattendue globale: {e}. Nouvelle tentative dans 5s...")
            await asyncio.sleep(5)

# -------------------------------------------------------------------
# 5. LANCEMENT
# -------------------------------------------------------------------
if __name__ == "__main__":
    print("Démarrage pont WebSocket → OSC (Ctrl+C pour quitter)...")
    try:
        asyncio.run(ws_bridge())
    except KeyboardInterrupt:
        print("Arrêt demandé.")
