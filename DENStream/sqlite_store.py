import sqlite3
import pandas as pd
import json
from datetime import datetime, timedelta
import time
import threading


class FlightDataStorage:
    """Sistema ultra optimizado para alta concurrencia de escritura"""

    def __init__(self, db_path='flight_data.db', retention_minutes=10):
        self.db_path = db_path
        self.retention_minutes = retention_minutes
        self.write_lock = threading.Lock()  # Bloqueo para escrituras
        self._init_db()

    def _get_connection(self):
        """Crea conexión optimizada para alta concurrencia"""
        conn = sqlite3.connect(
            self.db_path,
            timeout=30,  # Tiempo de espera aumentado
            check_same_thread=False  # Permite acceso desde multiples hilos
        )
        # Optimizaciones criticas para rendimiento
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def _init_db(self):
        """Inicializa la base de datos con optimizaciones"""
        with self._get_connection() as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS flight_data (
                icao24 TEXT PRIMARY KEY,
                callsign TEXT,
                longitude REAL,
                latitude REAL,
                velocity REAL,
                baro_altitude REAL,
                heading REAL,
                cluster INTEGER,
                timestamp_ingest TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                origin_country TEXT,
                time_position INTEGER,
                last_contact INTEGER,
                on_ground BOOLEAN,
                x REAL,
                y REAL,
                alt REAL,
                vel REAL,
                sh REAL,
                ch REAL )
            """)

            # Solo indices esenciales
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON flight_data(timestamp_ingest)")
            conn.commit()

    def save_flight_data(self, data):
        """Guarda datos con manejo de alta concurrencia"""
        icao24 = data.get('icao24', 'Unknown')

        # Bloqueo solo para escritura, no para todo el proceso
        with self.write_lock:
            try:
                # Intentar actualizacion primero
                updated = self._try_update(icao24, data)
                if not updated:
                    self._try_insert(icao24, data)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    time.sleep(0.05)  # Pequeña pausa
                    self.save_flight_data(data)  # Reintento recursivo
                else:
                    print(f"❌ Error grave en save: {e}")
            except Exception as e:
                print(f"⚠️ Error inesperado: {e}")

    def _try_update(self, icao24, data):
        """Intenta actualizar registro existente"""
        if not icao24 or icao24 == 'Unknown':
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE flight_data SET
                callsign = ?,
                longitude = ?,
                latitude = ?,
                velocity = ?,
                baro_altitude = ?,
                heading = ?,
                cluster = ?,
                origin_country = ?,
                time_position = ?,
                last_contact = ?,
                on_ground = ?,
                x = ?,
                y = ?,
                alt = ?,
                vel = ?,
                sh = ?,
                ch = ?,
                timestamp_ingest = CURRENT_TIMESTAMP
            WHERE icao24 = ?
            """, (
                data.get('callsign', 'Unknown'),
                data.get('longitude'),
                data.get('latitude'),
                data.get('velocity'),
                data.get('baro_altitude'),
                data.get('heading'),
                data.get('cluster'),
                data.get('origin_country'),
                data.get('time_position'),
                data.get('last_contact'),
                data.get('on_ground', False),
                data.get('x'),
                data.get('y'),
                data.get('alt'),
                data.get('vel'),
                data.get('sh'),
                data.get('ch'),
                icao24
            ))
            updated = cursor.rowcount > 0
            conn.commit()
            return updated

    def _try_insert(self, icao24, data):
        """Inserta nuevo registro optimizado"""
        with self._get_connection() as conn:
            # Usar INSERT OR IGNORE para evitar conflictos
            conn.execute("""
            INSERT OR IGNORE INTO flight_data 
            (icao24, callsign, longitude, latitude, velocity, baro_altitude, 
             heading, cluster, origin_country, time_position, last_contact, 
             on_ground, x, y, alt, vel, sh, ch)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                icao24,
                data.get('callsign', 'Unknown'),
                data.get('longitude'),
                data.get('latitude'),
                data.get('velocity'),
                data.get('baro_altitude'),
                data.get('heading'),
                data.get('cluster'),
                data.get('origin_country'),
                data.get('time_position'),
                data.get('last_contact'),
                data.get('on_ground', False),
                data.get('x'),
                data.get('y'),
                data.get('alt'),
                data.get('vel'),
                data.get('sh'),
                data.get('ch')
            ))
            conn.commit()

    def get_recent_flight_data(self, minutes=5):
        """Obtiene datos rápidamente sin bloqueos"""
        cutoff = datetime.utcnow() - timedelta(minutes=minutes)
        cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')

        with self._get_connection() as conn:
            # Consulta optimizada solo para columnas necesarias
            df = pd.read_sql_query(f"""
                SELECT 
                    icao24, callsign, longitude, latitude, 
                    baro_altitude, velocity, heading, cluster,
                    x, y, alt, vel, sh, ch, timestamp_ingest
                FROM flight_data 
                WHERE timestamp_ingest >= ?
                """,
                                   conn,
                                   params=(cutoff_str,)
                                   )
        return df

    def cleanup_old_data(self):
        """Limpieza optimizada con manejo de bloqueos"""
        with self.write_lock:
            try:
                cutoff = datetime.utcnow() - timedelta(minutes=self.retention_minutes)
                cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')

                with self._get_connection() as conn:
                    # Eliminacion por lotes para mejor rendimiento
                    conn.execute("DELETE FROM flight_data WHERE timestamp_ingest < ?", (cutoff_str,))
                    conn.commit()
            except Exception as e:
                print(f"⚠️ Error en limpieza: {e}")

    def run_periodic_cleanup(self, interval_minutes=5):
        """Ejecución segura de limpieza periódica"""
        while True:
            try:
                self.cleanup_old_data()
            except Exception as e:
                print(f"⚠️ Error en limpieza periódica: {e}")
            time.sleep(interval_minutes * 60)