import time
import json
import sys
import requests
from datetime import datetime, timezone
from kafka import KafkaProducer
from kafka.errors import KafkaError
import os
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

# Carga variables de entorno
load_dotenv()

# Área de América del Sur
LAT_MIN, LAT_MAX = -60.0, 15.0
LON_MIN, LON_MAX = -90.0, -30.0
LAT_MID = (LAT_MIN + LAT_MAX) / 2
LON_MID = (LON_MIN + LON_MAX) / 2

# Endpoints
API_ROOT   = "https://opensky-network.org/api"
STATES_URL = f"{API_ROOT}/states/all"
TOKEN_URL  = (
    "https://auth.opensky-network.org/auth/realms/"
    "opensky-network/protocol/openid-connect/token"
)

# Credenciales OAuth2
CLIENT_ID     = os.getenv("CLIENTID")
CLIENT_SECRET = os.getenv("CLIENTSECRET")

# Cache de token
_access_token     = None
_token_expires_at = 0

def get_access_token():
    global _access_token, _token_expires_at

    # Si aún no caduca, lo reutilizamos
    if _access_token and time.time() < _token_expires_at - 30:
        return _access_token

    # Solicitud de token con HTTP Basic Auth
    resp = requests.post(
        TOKEN_URL,
        auth=HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10
    )

    # Si hubo error 400/401, imprimimos body para depurar
    if resp.status_code >= 400:
        print("❌ Falló obtención de token:", resp.status_code, resp.text)
        resp.raise_for_status()

    j = resp.json()
    _access_token     = j["access_token"]
    _token_expires_at = time.time() + j.get("expires_in", 1800)
    return _access_token

def check_opensky_api(timeout=10):
    params  = {"lamin": -1.0, "lamax": 1.0, "lomin": -1.0, "lomax": 1.0}
    token   = get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    resp = requests.get(STATES_URL, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if "states" not in data:
        raise ValueError("Respuesta válida, pero sin clave 'states'")
    return True

def fetch_states():
    params = {"lamin": LAT_MIN, "lamax": LAT_MAX, "lomin": LON_MIN, "lomax": LON_MAX}
    while True:
        try:
            token   = get_access_token()
            headers = {"Authorization": f"Bearer {token}"}
            resp    = requests.get(STATES_URL, params=params, headers=headers, timeout=20)

            if resp.status_code == 200:
                return resp.json().get("states", [])

            if resp.status_code == 401:
                # token caducado o inválido: lo forzamos repetir
                print("🔄 401 Unauthorized — renovando token…")
                global _access_token, _token_expires_at
                _access_token = None
                continue

            if resp.status_code == 429:
                wait = int(resp.headers.get("X-Rate-Limit-Retry-After-Seconds", 300))
                print(f"⚠️  429 Too Many Requests — durmiendo {wait}s…")
                time.sleep(wait)
                continue

            print(f"❌ Error {resp.status_code}: {resp.text}")
            time.sleep(10)

        except requests.RequestException as e:
            print("❌ Exception en fetch_states:", e)
            time.sleep(10)

def build_message(state):
    return {
        "icao24":         state[0],
        "callsign":       state[1].strip() if state[1] else None,
        "origin_country": state[2],
        "time_position":  state[3],
        "last_contact":   state[4],
        "longitude":      state[5],
        "latitude":       state[6],
        "baro_altitude":  state[7],
        "on_ground":      state[8],
        "velocity":       state[9],
        "heading":        state[10],
        "timestamp_ingest": datetime.now(timezone.utc).isoformat() + "Z"
    }

def quadrant(lat, lon):
    if lat >= LAT_MID and lon <= LON_MID: return 0
    if lat >= LAT_MID and lon >  LON_MID: return 1
    if lat <  LAT_MID and lon <= LON_MID: return 2
    return 3

async def run():
    try:
        producer = KafkaProducer(
            bootstrap_servers=['localhost:9092'],
            client_id='opensky-stream',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        print("✔️ Verificando acceso a OpenSky…")
        check_opensky_api()
        print("🚀 Token OK. Empezando ciclo de envío…")

        while True:
            states = fetch_states()
            now = datetime.now(timezone.utc).isoformat() + "Z"
            print(f"{now} — obtenidos {len(states)} aviones")
            for s in states:
                msg = build_message(s)
                lat, lon = msg["latitude"], msg["longitude"]
                if lat is None or lon is None:
                    continue
                producer.send('flight_stream', value=msg, partition=quadrant(lat, lon))
            producer.flush()
            time.sleep(60)

    except KeyboardInterrupt:
        print("⏹️  Interrumpido por usuario.")
    except Exception as ex:
        print("❌ Error en el producer:", ex)
    finally:
        producer.close()
        sys.exit(0)

if __name__ == "__main__":
    import asyncio
    asyncio.run(run())