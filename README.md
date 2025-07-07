# Clustering en Streaming del Trafico Aéreo en America del Sur

## Intrucciones para la instalacion (Linux y MacOS):

**Requisitos:**
* Sistema Operativo Linux o MacOS
* Python 3.13.4
* pip 24.0
* Docker desktop

Se tiene que crear un entorno virtual en el que se instalaran todas las dependencias del requirements.txt
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Ahora se le tiene que hacer pull de kafka y zookeeper:
```bash
docker pull confluentinc/cp-kafka
```
```bash
docker pull confluentinc/cp-zookeeper
```

Crear una network de docker:
```bash
docker network create kafka-net
```

Correr los dockers:
```bash
docker run -d --name zookeeper --network kafka-net -p 2181:2181 zookeeper
```
```bash
docker run -d --name kafka --network kafka-net -p 9092:9092 \
  -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  confluentinc/cp-kafka
```

## Intrucciones para correr el proyecto:

Para esto, tienes que tener activado el entorno virtual y los dockers de kafka y zookeeper.

1️⃣ **Paso 1:** Correr el `topic.py` (es caso de no ser la primera vez corriendo el proyecto, no es necesario correr esto)
```bash
python3 kafka/topic.py
```

2️⃣ **Paso 2:** Correr el `producer.py`, tener en cuenta que hay que crearse una cuneta en [Open Sky Network](https://opensky-network.org/) y poner las creneciales en un archivo `.env`. Ponerlo en la carpeta de `kafka/`
```bash
python3 kafka/producer.py
```

3️⃣ **Paso 3:** Correr el `ml_pipeline.py`, se tiene que dejar corriendo hasta que termine el proceso de *warm_up*
```bash
python3 DENStream/ml_pipeline.py
```

4️⃣ **Paso 4:** Correr el `dashboard.py`, una vez termine el proceso de *warm_up*, ya esta listo para visualizar el Dashboard
```bash
cd DENStream/
streamlit run dashboard.py
```
