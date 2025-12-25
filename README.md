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

# Générer ses propres données 

## Lancer l'enregistrement :
Maintenant que tout est set up et qu'on voit bien sur l'interface les données qui évoluent:
- Accéléromètre, ax, ay, az
- Gyroscope, gx, gy, gz
- Orientation, alpha, beta, gamma

On peut utiliser les boutons :
Mouvement 1, 2 ,3 ou 4 pour lancer l'enregistrement d'un mouvement pendant une seconde.
Les mouvements seront enregistres avec les étiquettes 1, 2, 3 ou 4, à vous de les affecter et d'être consistent par rapport à ces valeurs.
L'host local enregistre l'historique des ces mouvements, donc label du mouvement et données a chaque interval de temps

## Récupérer les données :
Une fois les mouvements enregistrés, on peut les exporter via le bouton d'exportation csv.
On récupère un fichier csv non nettoyé avec les données associées a chaque mouvement, l'host envoi les données via un paquet websocket au serveur !

## Preprocessing :
Enfin, le script de preprocessing data/data_preprocessing.py permet de reformater ces données dans un nouveau csv, ou on a chaque mouvement son étiquette et la progression temporelle de chaque variable. Le script est prévu pour un interval à 60 prise pour un mouvement (1s). Soit :
- ax, ay, az, gx, gy, gz, alpha, beta, gamma à t=1/60
- ax, ay, az, gx, gy, gz, alpha, beta, gamma à t=2/60
...
- ax, ay, az, gx, gy, gz, alpha, beta, gamma à t=60/60


