# Mocap — Prototype local

Objectif
--------
Prototype local permettant de récupérer en temps réel les capteurs de plusieurs téléphones via une page web, d'agréger ces données et de les utiliser pour générer du son (via VCV Rack ou générateur local).


---

# Tester le projet en local (mode d'emploi)

## 1. Cloner le projet
```sh
git clone <url-du-repo>
cd mocap
```

## 2. Installer les dépendances serveur
```sh
cd server
pip install -r requirements.txt
```

## 3. Lancer le serveur WebSocket
```sh
python main.py
```
Tu dois voir :
```
WebSocket server started on ws://0.0.0.0:8765
```

## 4. Trouver l'adresse IP locale de ton ordinateur
Dans un terminal :
```sh
ipconfig getifaddr en0
# ou
ifconfig
```
Note l'adresse du type `192.168.x.x` ou `10.x.x.x`.

## 5. Lancer un serveur web local pour la page client
Dans un nouveau terminal :
```sh
cd ../client
python3 -m http.server 8000
```

## 6. Ouvrir la page web
- Sur ton ordinateur : va sur [http://localhost:8000](http://localhost:8000)
- Sur ton téléphone (même Wi-Fi) : va sur [http://<IP-de-ton-ordi>:8000](http://<IP-de-ton-ordi>:8000)

## 7. Configurer la connexion WebSocket dans la page
- Dans le champ "Server WebSocket", entre :
	`ws://<IP-de-ton-ordi>:8765`  (ex : `ws://10.3.0.136:8765`)
- Clique sur "Demander permission (iOS)" si besoin.
- Clique sur "Démarrer".

## 8. Vérifier la réception
- Les valeurs des capteurs s'affichent dans la page.
- Les messages reçus s'affichent dans le terminal du serveur Python.

---

**Résumé rapide :**
1. Lancer le serveur Python (`python main.py`)
2. Lancer un serveur web local (`python3 -m http.server 8000`)
3. Ouvrir la page web et entrer l'adresse WebSocket
4. Démarrer l'envoi
5. Observer les données côté serveur


