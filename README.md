# ✈️ Clustering en Streaming del Tráfico Aéreo en América del Sur

> 🚀 Sistema de clustering en tiempo real para analizar el tráfico aéreo utilizando Machine Learning y tecnologías de streaming.

## 📋 Tabla de Contenidos
- [🔧 Requisitos del Sistema](#-requisitos-del-sistema)
- [⚙️ Instalación](#️-instalación)
- [🚀 Ejecución del Proyecto](#-ejecución-del-proyecto)
- [📊 Dashboard](#-dashboard)
- [🛠️ Tecnologías Utilizadas](#️-tecnologías-utilizadas)

## 🔧 Requisitos del Sistema

Antes de comenzar, asegúrate de tener instalados los siguientes componentes:

| Componente | Versión | Descripción |
|------------|---------|-------------|
| 🐧 **SO** | Linux/MacOS | Sistema operativo compatible |
| 🐍 **Python** | 3.13.4 | Lenguaje de programación |
| 📦 **pip** | 24.0+ | Gestor de paquetes |
| 🐳 **Docker Desktop** | Latest | Contenedores para Kafka |

## ⚙️ Instalación

### 1️⃣ Configuración del Entorno Virtual

Crea y activa un entorno virtual de Python:

```bash
# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2️⃣ Configuración de Docker

Descarga las imágenes necesarias de Kafka y Zookeeper:

```bash
# Descargar imagen de Kafka
docker pull confluentinc/cp-kafka

# Descargar imagen de Zookeeper
docker pull confluentinc/cp-zookeeper
```

### 3️⃣ Configuración de Red Docker

```bash
# Crear red para comunicación entre contenedores
docker network create kafka-net
```

### 4️⃣ Ejecutar Contenedores

```bash
# Ejecutar Zookeeper
docker run -d --name zookeeper --network kafka-net -p 2181:2181 confluentinc/cp-zookeeper

# Ejecutar Kafka
docker run -d --name kafka --network kafka-net -p 9092:9092 \
  -e KAFKA_ZOOKEEPER_CONNECT=zookeeper:2181 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  confluentinc/cp-kafka
```

## 🚀 Ejecución del Proyecto

> ⚠️ **Importante:** Asegúrate de que el entorno virtual esté activado y los contenedores Docker estén ejecutándose.

### 🔐 Configuración de Credenciales

1. Crea una cuenta en [Open Sky Network](https://opensky-network.org/) 🌐
2. Crea un archivo `.env` en la carpeta `kafka/` con tus credenciales:
```env
CLIENTI=tu_usuario
CLIENTSECRET=tu_contraseña
```

### 📝 Pasos de Ejecución

#### 1️⃣ **Crear Tópicos Kafka** (Solo primera vez)
```bash
python3 kafka/topic.py
```

#### 2️⃣ **Iniciar Productor de Datos**
```bash
python3 kafka/producer.py
```
> 📡 Este proceso conecta con OpenSky Network y envía datos de vuelos a Kafka por minnuto

#### 3️⃣ **Ejecutar Pipeline de ML**
```bash
python3 DENStream/ml_pipeline.py
```
> 🧠 Espera a que complete el proceso de *warm-up* antes de continuar

#### 4️⃣ **Lanzar Dashboard**
```bash
cd DENStream/
streamlit run dashboard.py
```
> 📊 Una vez completado el *warm-up*, el dashboard estará disponible

## 📊 Dashboard

El dashboard de Streamlit te permitirá:
- 📈 Visualizar clusters en tiempo real
- 🗺️ Ver mapas de tráfico aéreo
- 📋 Monitorear métricas de clustering

## 🛠️ Tecnologías Utilizadas

- **🐍 Python 3.13.4** - Lenguaje principal
- **🚀 Apache Kafka** - Streaming de datos
- **🧠 DENStream** - Algoritmo de clustering
- **📊 Streamlit** - Dashboard interactivo
- **🐳 Docker** - Contenedorización
- **✈️ OpenSky Network API** - Datos de vuelos

---

<div align="center">
  <p>🔗 <strong>Desarrollado con ❤️ para el curso de Machine Learning 🤖</strong></p>
</div>
