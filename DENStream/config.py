import os
from pathlib import Path

# Configuración general
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data_flights_local"
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"

# Crear directorios si no existen
for dir_path in [DATA_DIR, MODELS_DIR, LOGS_DIR]:
    dir_path.mkdir(exist_ok=True)

# Configuración de Kafka
KAFKA_CONFIG = {
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'flight_ml_pipeline',
    'auto.offset.reset': 'earliest'
}

KAFKA_TOPIC = 'flight_stream'

# Configuración del modelo
# MODEL_CONFIG = {
#     'warm_up_size': 10,
#     'decay_rate': 0.01,
#     'learning_rate': 0.001,
#     'n_features': 6  # x, y, alt, vel, sin_heading, cos_heading
# }

# PRUEBA 1
# MODEL_CONFIG = {
#     'warm_up_size': 1000,
#     'decaying_factor': 0.25,
#     'beta': 0.75,            # Reemplaza core_weight_threshold
#     'mu': 2,                 # Nuevo parámetro
#     'epsilon': 0.02,         # Nuevo parámetro
#     'n_samples_init': 1000   # Nuevo parámetro
# }

# PRUEBA 2
# MODEL_CONFIG = {
#     'warm_up_size': 3000,
#     'decaying_factor': 0.005,
#     'beta': 0.3,            # Reemplaza core_weight_threshold
#     'mu': 5,                 # Nuevo parámetro
#     'epsilon': 0.08,         # Nuevo parámetro
#     'n_samples_init': 3000   # Nuevo parámetro
# }

# PRUEBA 3
# MODEL_CONFIG = {
#     'warm_up_size': 3000,
#     'decaying_factor': 0.01,
#     'beta': 0.5,            # Reemplaza core_weight_threshold
#     'mu': 10,                 # Nuevo parámetro
#     'epsilon': 0.05,         # Nuevo parámetro
#     'n_samples_init': 3000   # Nuevo parámetro
# }

# PRUEBA 4
# MODEL_CONFIG = {
#     'warm_up_size': 1000,
#     'decaying_factor': 0.008,
#     'beta': 0.5,            # Reemplaza core_weight_threshold
#     'mu': 8,                 # Nuevo parámetro
#     'epsilon': 0.05,         # Nuevo parámetro
#     'n_samples_init': 5000   # Nuevo parámetro
# }

# PRUEBA 5 BIG DATA
# MODEL_CONFIG = {
#     'warm_up_size': 1000,
#     'decaying_factor': 0.0001,
#     'beta': 0.2,            # Reemplaza core_weight_threshold
#     'mu': 20,                 # Nuevo parámetro
#     'epsilon': 1,         # Nuevo parámetro
#     'n_samples_init': 1000   # Nuevo parámetro
# }

# PRUEBA 6 GeminiV1
MODEL_CONFIG = {
    'warm_up_size': 1000,
    'decaying_factor': 0.05,       # Memoria larga
    'beta': 0.5,              # Ventana de outlier estándar
    'mu': 15,                 # Umbral de densidad alto
    'epsilon': 0.2,           # Radio grande (aprox. 22 km)
    'n_samples_init': 1000
}

# PRUEBA 7 GeminiV2
# MODEL_CONFIG = {
#     'warm_up_size': 1000,
#     'decaying_factor': 0.1,        # Memoria media
#     'beta': 0.5,
#     'mu': 10,                 # Umbral de densidad moderado
#     'epsilon': 0.15,          # Radio moderado (aprox. 16 km)
#     'n_samples_init': 1000
# }

# Configuración de proyección UTM
# Zona UTM 18N para Perú (Lima)
UTM_ZONE = 18
UTM_HEMISPHERE = 'N'
UTM_EPSG = 32718  # WGS84 / UTM zone 18S para Lima, Perú

# Configuración MLflow
MLFLOW_CONFIG = {
    'experiment_name': 'flight_streaming_ml',
    'tracking_uri': 'sqlite:///mlflow.db',
    'artifact_location': str(MODELS_DIR / 'mlflow_artifacts'),
    'log_frequency': 100  # Log cada 100 mensajes después del warm-up
}

# Configuración del Dashboard
DASHBOARD_CONFIG = {
    'update_frequency': 30,  # segundos
    'map_center': [-12.0464, -77.0428],  # Lima, Perú
    'map_zoom': 10,
    'heatmap_radius': 15
}