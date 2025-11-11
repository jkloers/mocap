import collections
import numpy as np
import time

class SensorBuffer:
    def __init__(self, window_size, step_size, num_features):
        self.window_size = window_size
        self.step_size = step_size
        self.num_features = num_features
        
        self.window_buffer = collections.deque(maxlen=window_size)
        self.new_sample_counter = 0
        
        # --- CHARGEMENT DU MODÈLE ---
        # Charge ton modèle ML (ex: .pkl, .h5, .pt) UNE SEULE FOIS
        try:
            # Remplace 'mon_modele.pkl' par le chemin vers ton fichier
            self.model =  True #'''joblib.load('mon_modele.pkl')'''
            print("[Buffer] Modèle 'mon_modele.pkl' chargé avec succès.")
        except FileNotFoundError:
            print("[Buffer] ATTENTION: 'mon_modele.pkl' non trouvé. Le buffer fonctionnera sans prédiction.")
            self.model = None
        except Exception as e:
            print(f"[Buffer] Erreur au chargement du modèle: {e}")
            self.model = None

    def add_data(self, sample):
        if len(sample) != self.num_features:
            print(f"Erreur : L'échantillon a {len(sample)} features, mais {self.num_features} sont attendues.")
            return

        self.window_buffer.append(sample)
        self.new_sample_counter += 1

        if len(self.window_buffer) == self.window_size:
            if self.new_sample_counter >= self.step_size:
                result = self.process_window()
                self.new_sample_counter = 0
                return result
            else:
                return None
        else:
            return None

    def process_window(self):
        """
        C'EST ICI QUE LA MAGIE OPÈRE.
        Appelé par add_data() quand une fenêtre est prête.
        """
        
        # 1. Préparer les données pour le modèle
        # window_data aura la forme (WINDOW_SIZE, NUM_FEATURES)
        window_data = np.array(list(self.window_buffer))
        
        # 2. Vérifier si le modèle est chargé
        if self.model:
            try:
                # 3. Adapter la forme (shape)
                # La plupart des modèles (Keras, Sklearn) attendent un "batch"
                # (1, WINDOW_SIZE, NUM_FEATURES) ou (1, N_FEATURES_EXTRAITES)
                # Cet exemple suppose (1, 100, 9)
                model_input = np.expand_dims(window_data, axis=0)
                
                # 4. PRÉDICTION
                start_time = time.time()
                ''' prediction = self.model.predict(model_input) '''
                resultat = 10
                end_time = time.time()
                
                print("INPUTS IN BUFFER : ", model_input)
                
                # 5. UTILISER LE RÉSULTAT
                # 'prediction' peut être [0] ou [[0.1, 0.9]] selon ton modèle
                ''' resultat = prediction[0] '''
                
                print(f"--- PRÉDICTION ML ---")
                print(f"  Résultat: {resultat} (calculé en {(end_time - start_time) * 1000:.2f} ms)")
                print(f"  Basé sur une fenêtre de {window_data.shape}")
                print(f"----------------------")

                # use the result to send it back as a websocket message 
                # can also send a OSC message to the receiver
                return resultat

            except Exception as e:
                print(f"[ML Error] Erreur lors de la prédiction: {e}")
                return None
        else:
            print(f"Traitement fenêtre {window_data.shape}, mais aucun modèle n'est chargé.")
            return None