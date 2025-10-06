# Mocap — Prototype local

Objectif
--------
Prototype local permettant de récupérer en temps réel les capteurs de plusieurs téléphones via une page web, d'agréger ces données et de les utiliser pour générer du son (via VCV Rack ou générateur local).

Architecture
------------
- Clients : page web (HTML/JS) qui lit `DeviceMotion`/`DeviceOrientation` et transmet via WebSocket ou WebRTC DataChannel.
- Serveur : Python (asyncio). V1 = WebSocket + OSC -> VCV Rack. V2 = aiortc WebRTC DataChannels pour latence plus faible.
- Sortie audio : VCV Rack (OSC/MIDI) recommandé pour prototypage sonore modulaire.


