#Handles incoming WebSocket connections and messages
import json

async def handle_client(websocket, path):
    async for message in websocket:
        try:
            data = json.loads(message)
            device_id = data.get('deviceId', 'unknown')
            print(f"Received from {device_id}: {data}")
            # Here you can add code to forward data to OSC, save to file, etc.
        except Exception as e:
            print("Error handling message:", e)
