import json
import math
import numpy as np
import pyproj
from typing import Dict, Tuple, Optional
from datetime import datetime, timezone
from config import UTM_EPSG

class GeoProjector:
    """Maneja la proyección geográfica de coordenadas WGS84 a UTM."""
    
    def __init__(self, utm_epsg: int = UTM_EPSG):
        self.utm_epsg = utm_epsg
        self.transformer = pyproj.Transformer.from_crs(
            'EPSG:4326',  # WGS84
            f'EPSG:{utm_epsg}',  # UTM
            always_xy=True
        )
    
    def project_to_meters(self, lon: float, lat: float) -> Tuple[float, float]:
        """Proyecta coordenadas lon/lat a metros en UTM."""
        try:
            x, y = self.transformer.transform(lon, lat)
            return x, y
        except Exception as e:
            print(f"Error en proyección: {e}")
            return 0.0, 0.0

class FlightDataProcessor:
    """Procesa los datos de vuelo para el modelo ML."""
    
    def __init__(self, projector: GeoProjector):
        self.projector = projector

    def parse_flight_message(self, message: str) -> Optional[Dict]:
        """Parsea el mensaje JSON de Kafka."""
        try:
            # Validar que el mensaje es string
            if not isinstance(message, str):
                print(f"Error: mensaje no es string, es {type(message)}: {message}")
                return None
        
            # Parsear JSON
            data = json.loads(message)
        
            # Validar que el resultado es un diccionario
            if not isinstance(data, dict):
                print(f"Error: JSON parseado no es diccionario, es {type(data)}: {data}")
                return None
        
            # Validar que contiene campos basicos esperados
            required_fields = ['longitude', 'latitude', 'baro_altitude', 'velocity', 'heading']
            missing_fields = [field for field in required_fields if field not in data]
        
            if missing_fields:
                print(f"Campos faltantes en el mensaje: {missing_fields}")
                print(f"Mensaje completo: {message}")
                return None
        
            return data
        
        except json.JSONDecodeError as e:
            print(f"Error parseando JSON: {e}")
            print(f"Mensaje problemático: {message}")
            return None
        except Exception as e:
            print(f"Error inesperado parseando mensaje: {e}")
            print(f"Tipo de mensaje: {type(message)}")
            return None

    def parse_flight_message_map(self, message:str) ->Optional[Dict]:
        """Parsea el mensaje JSON de Kafka."""
        try:
            # Validar que el mensaje es string
            if not isinstance(message, str):
                print(f"Error: mensaje no es string, es {type(message)}: {message}")
                return None

            # Parsear JSON
            data = json.loads(message)

            if not isinstance(data, dict):
                print(f"Error: JSON parseado no es diccionario, es {type(data)}: {data}")
                return None
            required_fields = ['timestamp_ingest','longitude', 'latitude', 'callsign']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"Campos faltantes en el mensaje: {missing_fields}")
                print(f"Mensaje completo: {message}")
                return None

            return data

        except json.JSONDecodeError as e:
            print(f"Error parseando JSON: {e}")
            print(f"Mensaje problemático: {message}")
            return None
        except Exception as e:
            print(f"Error inesperado parseando mensaje: {e}")
            print(f"Tipo de mensaje: {type(message)}")
            return None

    def extract_features(self, data: Dict) -> Optional[Dict[str, float]]:
        """Extrae las características necesarias del mensaje de vuelo."""
        try:
            if not isinstance(data, dict):
                print(f"Error: data no es un diccionario, es {type(data)}: {data}")
                return None
        
            longitude = data.get('longitude')
            latitude = data.get('latitude')
            baro_altitude = data.get('baro_altitude')
            velocity = data.get('velocity')
            heading = data.get('heading')
        
            if None in [longitude, latitude, baro_altitude, velocity, heading]:
                print(f"Campos faltantes en data: {data}")
                return None
        
            try:
                longitude = float(longitude)
                latitude = float(latitude)
                baro_altitude = float(baro_altitude)
                velocity = float(velocity)
                heading = float(heading)
            except (ValueError, TypeError) as e:
                print(f"Error convirtiendo a float: {e}")
                return None
            
            x, y = self.projector.project_to_meters(longitude, latitude)
        
            # Calcular componentes trigonometricas del heading
            heading_rad = math.radians(heading)
            sin_heading = math.sin(heading_rad)
            cos_heading = math.cos(heading_rad)
        
            # Formar diccionario de caracteristicas
            features = {
                'x': x,
                'y': y,
                'alt': float(baro_altitude),
                'vel': float(velocity),
                'sh': sin_heading,
                'ch': cos_heading
            }
        
            return features
        
        except Exception as e:
            print(f"Error extrayendo características: {e}")
            print(f"Tipo de data: {type(data)}")
            print(f"Contenido de data: {data}")
            return None
    
    def validate_features(self, features: Dict[str, float]) -> bool:
        """Valida que las características sean válidas."""
        try:
            # Verificar que no hay valores NaN o infinitos
            for key, value in features.items():
                if not isinstance(value, (int, float)) or math.isnan(value) or math.isinf(value):
                    return False
            
            # Verificar rangos razonables
            if features['alt'] < -1000 or features['alt'] > 50000:  # Altitud razonable
                return False
            if features['vel'] < 0 or features['vel'] > 1000:  # Velocidad razonable
                return False
                
            return True
            
        except Exception:
            return False

class MetricsLogger:
    """Maneja el logging de métricas."""
    
    def __init__(self, log_file: str = "logs/metrics.log"):
        self.log_file = log_file
    
    def log_metric(self, metric_name: str, value: float, step: int):
        """Log una métrica con timestamp."""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = f"{timestamp} - {metric_name}: {value:.6f} - Step: {step}\n"
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Error logging metric: {e}")
    
    def log_message(self, message: str):
        """Log un mensaje general."""
        timestamp = datetime.now(timezone.utc).isoformat()
        log_entry = f"{timestamp} - {message}\n"
        
        try:
            with open(self.log_file, 'a') as f:
                f.write(log_entry)
        except Exception as e:
            print(f"Error logging message: {e}")

def save_model_checkpoint(model, scaler, step: int, checkpoint_dir: str = "models"):
    """Guarda un checkpoint del modelo y scaler."""
    import pickle
    import os
    
    checkpoint_path = os.path.join(checkpoint_dir, f"checkpoint_step_{step}.pkl")
    
    try:
        checkpoint_data = {
            'model': model,
            'scaler': scaler,
            'step': step,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        with open(checkpoint_path, 'wb') as f:
            pickle.dump(checkpoint_data, f)
            
        print(f"Checkpoint guardado: {checkpoint_path}")
        
    except Exception as e:
        print(f"Error guardando checkpoint: {e}")

def load_model_checkpoint(checkpoint_path: str):
    """Carga un checkpoint del modelo."""
    import pickle
    
    try:
        with open(checkpoint_path, 'rb') as f:
            checkpoint_data = pickle.load(f)
        
        print(f"Checkpoint cargado: {checkpoint_path}")
        return checkpoint_data
        
    except Exception as e:
        print(f"Error cargando checkpoint: {e}")
        return None