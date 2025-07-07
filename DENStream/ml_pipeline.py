import json
import os
import tempfile
import pickle
import mlflow
import mlflow.sklearn
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Optional

from river import cluster  # Cambiado: importar módulo de clustering
from river import preprocessing
from confluent_kafka import Consumer, KafkaException, KafkaError

from config import KAFKA_CONFIG, KAFKA_TOPIC, MODEL_CONFIG, MLFLOW_CONFIG, DATA_DIR
from utils import GeoProjector, FlightDataProcessor, MetricsLogger, save_model_checkpoint


class FlightMLPipeline:
    """Pipeline principal de ML para datos de vuelo en streaming."""

    def __init__(self):
        # Inicializar componentes
        self.projector = GeoProjector()
        self.processor = FlightDataProcessor(self.projector)
        self.logger = MetricsLogger()

        # Inicializar modelo y scaler
        self.scaler = preprocessing.StandardScaler()

        # REEMPLAZO: Modelo DenStream en lugar de regresión lineal
        self.model = cluster.DenStream(
            decaying_factor=float(MODEL_CONFIG['decaying_factor']),
            beta=float(MODEL_CONFIG['beta']),
            mu=float(MODEL_CONFIG['mu']),
            epsilon=float(MODEL_CONFIG['epsilon']),
            n_samples_init=int(MODEL_CONFIG['n_samples_init'])
        )

        # Estado del pipeline
        self.message_count = 0
        self.warm_up_complete = False
        self.warm_up_size = MODEL_CONFIG['warm_up_size']

        # Configurar MLflow
        self.setup_mlflow()

        # Configurar Kafka
        self.setup_kafka()

    def setup_mlflow(self):
        """Configura MLflow para tracking."""
        mlflow.set_tracking_uri(MLFLOW_CONFIG['tracking_uri'])
        mlflow.set_experiment(MLFLOW_CONFIG['experiment_name'])

        # Iniciar run de MLflow
        self.mlflow_run = mlflow.start_run()

        # Log parámetros de DenStream
        mlflow.log_params({
            'warm_up_size': self.warm_up_size,
            'decaying_factor': MODEL_CONFIG['decaying_factor'],
            'beta': MODEL_CONFIG['beta'],
            'mu': MODEL_CONFIG['mu'],
            'epsilon': MODEL_CONFIG['epsilon'],
            'n_samples_init': MODEL_CONFIG['n_samples_init'],
            'utm_epsg': self.projector.utm_epsg
        })

    def setup_kafka(self):
        """Configura el consumer de Kafka."""
        self.consumer = Consumer(KAFKA_CONFIG)
        self.consumer.subscribe([KAFKA_TOPIC])
        print("Kafka consumer configurado y conectado")

    def saved_data_point(self, data: dict, name_json: str = None):
        """Guarda un punto de datos en un archivo JSON dentro de DATA_DIR."""
        # Asegurar que el directorio existe
        os.makedirs(DATA_DIR, exist_ok=True)

        # Generar nombre de archivo si no se proporciona
        if name_json is None:
            icao24 = data.get('icao24', 'unknown')
            name_json = f"{icao24}.json"

        # Construir la ruta completa
        file_path = os.path.join(DATA_DIR, name_json)

        # Guardar el diccionario como JSON
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)

        print(f"Archivo guardado en: {file_path}")


    def process_message(self, message: str) -> bool:
        """Procesa un mensaje individual con DenStream."""
        try:
            # Parsear y guardar mensaje (opcional)
            data = self.processor.parse_flight_message(message)
            if data is None:
                return False

            features = self.processor.extract_features(data)
            if features is None:
                return False

            if not self.processor.validate_features(features):
                return False

            self.message_count += 1

            # Actualizar scaler
            self.scaler.learn_one(features)
            scaled_features = self.scaler.transform_one(features)

            # Fase de warm-up: solo aprender
            if not self.warm_up_complete:
                self.model.learn_one(scaled_features)

                if self.message_count >= self.warm_up_size:
                    self.warm_up_complete = True
                    print(f"🎉 Warm-up completado. Iniciando clustering...")

            # Fase de producción: predecir y aprender
            else:
                # Obtener cluster asignado
                cluster_id = self.model.predict_one(scaled_features)

                # Actualizar modelo
                self.model.learn_one(scaled_features)

                # Log periódico a MLflow
                if self.message_count % MLFLOW_CONFIG['log_frequency'] == 0:
                    self.log_to_mlflow(cluster_id, features, scaled_features)

                data["cluster"] = cluster_id
                self.saved_data_point(data)


            return True

        except Exception as e:
            print(f"❌ Error procesando mensaje: {e}")
            return False

    def log_to_mlflow(self, cluster_id: int, features: Dict, scaled_features: Dict):
        """Log métricas de clustering a MLflow."""
        try:
            step = self.message_count

            # Métricas principales
            mlflow.log_metric("cluster_id", cluster_id, step=step)
            mlflow.log_metric("num_clusters", len(self.model.p_micro_clusters), step=step)

            # Características escaladas
            mlflow.log_metric("scaled_velocity", float(scaled_features['vel']), step=step)
            mlflow.log_metric("scaled_altitude", float(scaled_features['alt']), step=step)

            print(f"Clúster asignado: {cluster_id} | Total clusters: {len(self.model.p_micro_clusters)}")

        except Exception as e:
            print(f"Error logging a MLflow: {e}")

    def save_checkpoint(self):
        """Guarda un checkpoint del modelo."""
        try:
            save_model_checkpoint(self.model, self.scaler, self.message_count)
            # Guardar en MLflow
            with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pkl') as f:
                pickle.dump({
                    'model': self.model,
                    'scaler': self.scaler,
                    'message_count': self.message_count,
                    'warm_up_complete': self.warm_up_complete
                }, f)
                mlflow.log_artifact(f.name, "model_checkpoints")

        except Exception as e:
            print(f"Error guardando checkpoint: {e}")

    def run(self):
        """Ejecuta el pipeline principal."""
        print("Iniciando pipeline de clustering con DenStream...")
        print(f"Warm-up configurado para {self.warm_up_size} mensajes")

        try:
            while True:
                msg = self.consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    else:
                        raise KafkaException(msg.error())

                message_str = msg.value().decode('utf-8')
                success = self.process_message(message_str)

                if success and self.message_count % 100 == 0:
                    status = "warm-up" if not self.warm_up_complete else "production"
                    print(f"Mensajes procesados: {self.message_count} - Estado: {status}")

                if success and self.message_count % 1000 == 0:
                    self.save_checkpoint()

        except KeyboardInterrupt:
            print("\nInterrupción por usuario. Guardando estado final...")
            self.save_checkpoint()
        finally:
            self.cleanup()

    def cleanup(self):
        """Limpia recursos."""
        self.consumer.close()
        mlflow.end_run()
        print("Pipeline cerrado correctamente")


if __name__ == "__main__":
    pipeline = FlightMLPipeline()
    pipeline.run()