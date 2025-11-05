import collections
import numpy as np
import time

# --- Vos paramètres ---
WINDOW_SIZE = 100  # 100 échantillons par fenêtre (ex: 2s @ 50Hz)
STEP_SIZE = 50     # Créer une nouvelle fenêtre tous les 50 nouveaux échantillons (chevauchement de 50%)
NUM_FEATURES = 6   # Nombre de features (ex: AccelX, Y, Z, GyroX, Y, Z)

class SensorBuffer:
    def __init__(self, window_size, step_size, num_features):
        self.window_size = window_size
        self.step_size = step_size
        self.num_features = num_features
        
        # Le buffer principal qui se comporte comme une fenêtre glissante.
        # Il ne contiendra jamais plus de 'window_size' éléments.
        self.window_buffer = collections.deque(maxlen=window_size)
        
        # Un compteur pour savoir quand déclencher le traitement (basé sur STEP_SIZE)
        self.new_sample_counter = 0

    def add_data(self, sample):
        """
        Ajoute un nouvel échantillon de capteur au buffer.
        L'échantillon doit être une liste ou un tuple (ex: [ax, ay, az, gx, gy, gz])
        """
        if len(sample) != self.num_features:
            print(f"Erreur : L'échantillon a {len(sample)} features, mais {self.num_features} sont attendues.")
            return

        # 1. Ajouter le nouvel échantillon à la fenêtre glissante
        self.window_buffer.append(sample)
        self.new_sample_counter += 1

        # 2. Vérifier si le buffer est plein (pour la première fois au moins)
        if len(self.window_buffer) == self.window_size:
            
            # 3. Vérifier s'il est temps de créer une nouvelle fenêtre (basé sur STEP_SIZE)
            if self.new_sample_counter >= self.step_size:
                # C'est le moment !
                self.process_window()
                
                # Réinitialiser le compteur de pas
                self.new_sample_counter = 0

    def process_window(self):
        """
        Appelé lorsque le buffer est plein et que le 'step_size' est atteint.
        C'est ici que vous envoyez les données au modèle ML.
        """
        
        # 'window_buffer' est une deque. Convertissez-la en une structure
        # que votre modèle ML peut lire (ex: un array NumPy).
        # La forme sera (WINDOW_SIZE, NUM_FEATURES)
        window_data = np.array(list(self.window_buffer))
        
        print(f"Traitement d'une fenêtre de forme : {window_data.shape}")
        
        # --- C'EST ICI QUE MAGIE OPÈRE ---
        # 1. (Optionnel) Extraire des features (moyenne, variance, FFT...)
        #    features = extract_features(window_data)
        # 2. Envoyer au modèle ML pour prédiction
        #    prediction = self.ml_model.predict(np.expand_dims(window_data, axis=0))
        #    print(f"Prédiction : {prediction}")
        # ------------------------------------
        pass