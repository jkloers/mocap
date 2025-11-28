# Mocap — Local Prototype

Objective
---------
This local prototype allows you to capture real-time sensor data from multiple phones via a web page, aggregate the data, and use it to generate sound.

---

# How to Test the Project Locally (Step-by-Step Guide)

## 1. Clone the Project
```sh
git clone <repository-url>
cd mocap
```

## 2. Install Server Dependencies
```sh
pip install -r requirements.txt
```

## 3. Start the Server
```sh
cd server
```
In two separate terminal windows, run the following commands:
```sh
# Terminal 1: Start the main FastAPI server
python main.py

# Terminal 2: Start the WebSocket-to-OSC bridge
python osc_sender.py
```

## 4. Start a Local Web Server with ngrok
To make the web page accessible on mobile devices, use ngrok to expose the server:
```sh
ngrok http 8000
```
Open the HTTPS URL provided by ngrok in your browser.

## 5. Configure Connections
Make sure to adjust the OSC ports and IP addresses in the `main.py` and `osc_sender.py` files to match your setup.

## 6. Verify Data Reception in Ableton
Open Ableton Live and check if the data is being received in your MaxMSP patches.

---

# Notes
- **WebSocket Endpoint**: The WebSocket endpoint is `/ws`. Ensure the client connects to the correct URL, e.g., `ws://<your-server-ip>:8000/ws`.
- **OSC Configuration**: By default, the OSC bridge sends data to `127.0.0.1` on port `8000`. Update these values in `osc_sender.py` if needed.
- **HTTPS Requirement**: On iOS devices, motion sensors require the page to be served over HTTPS. Use ngrok to meet this requirement.
- **Dependencies**: The project uses `FastAPI`, `python-osc`, and `websockets`. Ensure all dependencies are installed via `pip install -r requirements.txt`.
- **Device_id** For now please choose devide_id = "1" on your phone since it is hard-coded in MaxMSP. 

---

