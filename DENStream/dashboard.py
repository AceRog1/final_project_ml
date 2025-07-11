import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from streamlit_folium import st_folium
import json
import time
from datetime import datetime, timedelta
import os
import sqlite3
import mlflow
import threading
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, silhouette_samples
import matplotlib.pyplot as plt
from pathlib import Path
import random
from config import DATA_DIR, DASHBOARD_CONFIG, MLFLOW_CONFIG
from utils import GeoProjector, FlightDataProcessor
from sqlite_store import FlightDataStorage


class FlightDashboard:
    """Dashboard de visualización para el pipeline de ML de vuelos."""

    def __init__(self):
        self.projector = GeoProjector()
        self.processor = FlightDataProcessor(self.projector)
        self.setup_mlflow()
        # Inicializar con valores por defecto de configuración
        self.map_state = {
            'center': DASHBOARD_CONFIG['map_center'],
            'zoom': DASHBOARD_CONFIG['map_zoom']
        }
        self.cluster_colors = self.generate_cluster_colors(20)  # Colores para clusters

        # Inicializar el sistema de almacenamiento
        self.data_storage = FlightDataStorage(
            db_path='../flight_data.db',
            retention_minutes=5  # Mantener datos por 1 hora
        )
        cleanup_thread = threading.Thread(
            target=self.data_storage.run_periodic_cleanup,
            daemon=True
        )
        cleanup_thread.start()


    def generate_cluster_colors(self, n_clusters):
        """Genera colores distintos para cada cluster."""
        base_colors = [
            'red', 'blue', 'green', 'purple', 'orange', 'darkred',
            'lightblue', 'beige', 'darkblue', 'darkgreen', 'pink',
            'cadetblue', 'lightgray', 'black', 'lightgreen', 'gray',
            'darkpurple', 'white', 'lightred', 'darkorange'
        ]
        return {i: base_colors[i % len(base_colors)] for i in range(n_clusters)}

    def setup_mlflow(self):
        """Configura conexión a MLflow."""
        mlflow.set_tracking_uri(MLFLOW_CONFIG['tracking_uri'])

    def load_recent_flight_data(self, mins: int = 5) -> pd.DataFrame:
        """Carga datos recientes de vuelos."""
        try:

            df = self.data_storage.get_recent_flight_data(mins)

            return df

        except Exception as e:
            st.error(f"Error cargando datos: {e}")
            return pd.DataFrame()

    def load_mlflow_metrics(self) -> pd.DataFrame:
        """Carga métricas de MLflow."""
        try:
            db_path = MLFLOW_CONFIG['tracking_uri'].replace('sqlite:///', '')
            if not os.path.exists(db_path):
                return pd.DataFrame()

            conn = sqlite3.connect(db_path)
            query = """
            SELECT m.key, m.value, m.step, m.timestamp
            FROM metrics m
            JOIN runs r ON m.run_uuid = r.run_uuid
            WHERE r.status = 'RUNNING' OR r.status = 'FINISHED'
            ORDER BY m.timestamp DESC
            LIMIT 1000
            """

            df = pd.read_sql_query(query, conn)
            conn.close()

            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

            return df

        except Exception as e:
            st.error(f"Error cargando métricas MLflow: {e}")
            return pd.DataFrame()

    def create_flight_map(self, df: pd.DataFrame):
        """Crea mapa de vuelos con colores por cluster."""
        if df.empty:
            return None

        # location = self.map_state['center']
        zoom = self.map_state['zoom']
        location = (-12.0464, -77.0428)

        m = folium.Map(
            location=location,
            zoom_start=zoom,
            tiles='OpenStreetMap'
        )

        # Marcadores con colores por cluster
        for _, row in df.iterrows():
            if pd.notna(row['latitude']) and pd.notna(row['longitude']):
                cluster = row.get('cluster')
                color = self.cluster_colors.get(cluster, 'gray') if cluster is not None else 'gray'


                folium.CircleMarker(
                    location=[row['latitude'], row['longitude']],
                    radius=6,
                    popup=f"""
                    <b>Icao24:</b> {row.get('icao24', 'Unknown')}<br>
                    <b>Callsign:</b> {row.get('callsign', 'Unknown')}<br>
                    <b>Cluster:</b> {cluster}<br>
                    <b>Velocidad:</b> {row.get('vel'):.1f} kt<br>
                    <b>Altitud:</b> {row.get('alt'):.0f} ft<br>
                    <b>Timestamp:</b> {row.get('timestamp_ingest')}
                    """,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.7
                ).add_to(m)

        return m

    def create_metrics_plots(self, metrics_df: pd.DataFrame):
        """Crea gráficos de métricas de ML."""
        if metrics_df.empty:
            return None, None

        # Grafico de error de predicción
        error_data = metrics_df[metrics_df['key'] == 'prediction_error']
        fig_error = px.line(
            error_data,
            x='step',
            y='value',
            title='Error de Predicción a lo Largo del Tiempo',
            labels={'value': 'Error', 'step': 'Paso'}
        ) if not error_data.empty else None

        # Grafico de learning rate con decay
        lr_data = metrics_df[metrics_df['key'] == 'learning_rate']
        decay_data = metrics_df[metrics_df['key'] == 'decay_factor']

        if not lr_data.empty or not decay_data.empty:
            fig_lr = make_subplots(
                rows=2, cols=1,
                subplot_titles=('Learning Rate', 'Decay Factor'),
                vertical_spacing=0.1
            )

            if not lr_data.empty:
                fig_lr.add_trace(
                    go.Scatter(x=lr_data['step'], y=lr_data['value'], name='Learning Rate'),
                    row=1, col=1
                )

            if not decay_data.empty:
                fig_lr.add_trace(
                    go.Scatter(x=decay_data['step'], y=decay_data['value'], name='Decay Factor'),
                    row=2, col=1
                )

            fig_lr.update_layout(height=600, title_text="Learning Rate y Decay Factor")
        else:
            fig_lr = None

        return fig_error, fig_lr

    def create_flight_analytics(self, df: pd.DataFrame):
        """Crea gráficos de análisis de vuelos."""
        if df.empty:
            return [None] * 8  # Retornar None para todos los graficos

        # Distribucion de velocidades (existente)
        fig_vel = px.histogram(
            df,
            x='vel',
            nbins=30,
            title='Distribución de Velocidades de Vuelos',
            labels={'vel': 'Velocidad (kt)', 'count': 'Frecuencia'}
        )

        # Distribucion de altitudes (existente)
        fig_alt = px.histogram(
            df,
            x='alt',
            nbins=30,
            title='Distribución de Altitudes de Vuelos',
            labels={'alt': 'Altitud (ft)', 'count': 'Frecuencia'}
        )

        # Scatter plot velocidad vs altitud (existente)
        fig_scatter = px.scatter(
            df,
            x='alt',
            y='vel',
            color='cluster',
            color_discrete_map=self.cluster_colors,
            title='Velocidad vs Altitud por Cluster',
            labels={'alt': 'Altitud (ft)', 'vel': 'Velocidad (kt)'}
        )

        # 4. Distribucion de direcciones (nuevo)
        df['heading'] = np.degrees(np.arctan2(df['sh'], df['ch'])) % 360
        fig_heading = px.histogram(
            df,
            x='heading',
            nbins=36,
            title='Distribución de Direcciones de Vuelo',
            labels={'heading': 'Dirección (grados)', 'count': 'Frecuencia'}
        )

        # Rosa de los vientos (version mejorada)
        fig_windrose = None
        try:
            # Crear copia para no modificar el DataFrame original
            windrose_df = df.copy()
            windrose_df['cluster'] = windrose_df['cluster'].astype(str)
            # Agrupar clusters pequeños en "Otros"
            cluster_counts = windrose_df['cluster'].value_counts()
            if len(cluster_counts) > 5:
                small_clusters = cluster_counts[cluster_counts < 5].index
                windrose_df['cluster_grouped'] = windrose_df['cluster'].apply(
                    lambda x: x if x not in small_clusters else 'Otros'
                )
                color_map = {**self.cluster_colors, 'Otros': '#CCCCCC'}
            else:
                windrose_df['cluster_grouped'] = windrose_df['cluster']
                color_map = self.cluster_colors

            # Crear bins de dirección cada 30 grados
            bins = list(range(0, 390, 30))
            labels = [f"{i}-{i + 30}°" for i in range(0, 360, 30)]
            windrose_df['heading_bin'] = pd.cut(
                windrose_df['heading'],
                bins=bins,
                labels=labels,
                include_lowest=True
            )

            # Contar vuelos por bin de direccion y cluster
            # direction_counts = windrose_df.groupby(
            #     ['heading_bin', 'cluster_grouped']
            # ).size().reset_index(name='count')

            direction_counts = windrose_df.groupby(['heading_bin', 'cluster_grouped'], observed=False).size().reset_index(name='count')

            # Crear grafico polar robusto
            fig_windrose = px.bar_polar(
                direction_counts,
                theta='heading_bin',
                r='count',
                color='cluster_grouped',
                color_discrete_map=color_map,
                title='Distribución de Direcciones por Cluster',
                template='plotly_dark',
                direction='clockwise',
                start_angle=0,
                labels={
                    'heading_bin': 'Dirección',
                    'count': 'Número de Vuelos',
                    'cluster_grouped': 'Cluster'
                },
                hover_data={'count': True}
            )
        except Exception as e:
            print(f"Error creando rosa de los vientos: {e}")
            fig_windrose = None

        # Mapa de densidad (nuevo)
        fig_density = px.density_mapbox(
            df,
            lat='latitude',
            lon='longitude',
            z='vel',
            radius=10,
            zoom=10,
            mapbox_style='open-street-map',
            title='Densidad de Vuelos por Velocidad',
            hover_data=['callsign', 'alt', 'vel']
        )


        # Visualizacion 3D (nuevo)
        fig_3d = px.scatter_3d(
            df,
            x='x',
            y='y',
            z='alt',
            color='cluster',
            color_discrete_map=self.cluster_colors,
            title='Distribución Espacial 3D de Vuelos',
            labels={'x': 'Coordenada X (m)', 'y': 'Coordenada Y (m)', 'alt': 'Altitud (ft)'},
            hover_data=['callsign', 'vel']
        )



        return (
            fig_vel, fig_alt, fig_scatter,
            fig_heading, fig_windrose,
            fig_density,
            fig_3d
        )


    def get_system_metrics(self, flight_df: pd.DataFrame, metrics_df: pd.DataFrame):
        """Calcula métricas del sistema."""
        metrics = {}
        metrics['total_flights'] = len(flight_df)
        metrics['avg_velocity'] = flight_df['vel'].mean() if not flight_df.empty else 0
        metrics['avg_altitude'] = flight_df['alt'].mean() if not flight_df.empty else 0

        if not metrics_df.empty:
            recent_error = metrics_df[metrics_df['key'] == 'prediction_error'].tail(1)
            metrics['latest_error'] = recent_error['value'].iloc[0] if not recent_error.empty else 0

            recent_lr = metrics_df[metrics_df['key'] == 'learning_rate'].tail(1)
            metrics['current_lr'] = recent_lr['value'].iloc[0] if not recent_lr.empty else 0
        else:
            metrics['latest_error'] = 0
            metrics['current_lr'] = 0

        return metrics

    def create_clustering_metrics(self, df: pd.DataFrame):
        """Calcula métricas de clustering para datos de vuelo."""
        if df.empty or 'cluster' not in df:
            return None, None, None, None, None

        # Numero de clusters
        n_clusters = df['cluster'].nunique()

        # Distribucion de puntos por cluster
        cluster_dist = df['cluster'].value_counts()

        # Cohesion intra-cluster (distancia promedio al centroide)
        intra_cluster_dists = []
        for cluster_id in df['cluster'].unique():
            cluster_points = df[df['cluster'] == cluster_id][['x', 'y']]
            centroid = cluster_points.mean()
            distances = np.sqrt(np.sum((cluster_points - centroid) ** 2, axis=1))
            intra_cluster_dists.extend(distances)
        avg_intra_dist = np.mean(intra_cluster_dists) if intra_cluster_dists else 0

        # Silhouette Score (requiere caracteristicas numericas)
        silhouette = None
        try:
            if n_clusters > 1 and len(df) > 1:
                # Seleccionar caracteristicas numericas relevantes
                features = df[['x', 'y', 'alt', 'vel']]
                # Escalar caracteristicas
                scaler = StandardScaler()
                features_scaled = scaler.fit_transform(features)
                # Calcular silhouette score
                silhouette = silhouette_score(features_scaled, df['cluster'])
        except:
            silhouette = None

        # Puntos outliers (cluster -1 o similar)
        n_outliers = len(df[df['cluster'] == -1]) if -1 in df['cluster'].values else 0

        return n_clusters, cluster_dist, avg_intra_dist, silhouette, n_outliers

    def create_clustering_plots(self, df: pd.DataFrame):
        """Crea gráficos de métricas para clustering."""
        if df.empty:
            return None, None, None, None

        # Calcular metricas
        n_clusters, cluster_dist, avg_intra_dist, silhouette, n_outliers = self.create_clustering_metrics(df)

        # Grafico de distribucion de clusters
        fig_dist = None
        if cluster_dist is not None:
            fig_dist = px.bar(
                x=cluster_dist.index.astype(str),
                y=cluster_dist.values,
                title='Distribución de Puntos por Cluster',
                labels={'x': 'Cluster ID', 'y': 'Número de Puntos'},
                color=cluster_dist.index.astype(str),
                color_discrete_sequence=px.colors.qualitative.Plotly
            )

        # Grafico de metricas clave
        metrics_data = {
            'Metric': ['Número de Clusters', 'Distancia Intra-Cluster Promedio',
                       'Silhouette Score', 'Puntos Outliers'],
            'Value': [n_clusters, avg_intra_dist, silhouette if silhouette is not None else 0, n_outliers]
        }
        fig_metrics = px.bar(
            metrics_data,
            x='Metric',
            y='Value',
            title='Métricas Clave de Clustering',
            text='Value',
            color='Metric',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_metrics.update_traces(texttemplate='%{text:.3f}', textposition='outside')

        # Visualizacion de clusters en espacio 2D
        fig_clusters = px.scatter(
            df,
            x='x',
            y='y',
            color='cluster',
            title='Distribución de Clusters en Espacio 2D',
            labels={'x': 'Coordenada X (m)', 'y': 'Coordenada Y (m)'},
            hover_data=['callsign', 'alt', 'vel'],
            color_discrete_sequence=px.colors.qualitative.Dark24
        )

        # Silhouette Visual (si hay suficientes datos)
        fig_silhouette = None
        try:
            if silhouette is not None and n_clusters > 1:


                # Seleccionar caracteristicas
                features = df[['x', 'y', 'alt', 'vel', 'sh', 'ch']]
                scaler = StandardScaler()
                features_scaled = scaler.fit_transform(features)

                # Calcular valores de silhouette para cada muestra
                silhouette_vals = silhouette_samples(features_scaled, df['cluster'])

                # Crear visualizacion
                fig_silhouette, ax = plt.subplots(figsize=(10, 6))
                y_lower = 10

                for i in range(n_clusters):
                    # Agregar los valores de silhouette para el i-esimo cluster
                    ith_cluster_silhouette_vals = silhouette_vals[df['cluster'] == i]
                    ith_cluster_silhouette_vals.sort()

                    size_cluster_i = ith_cluster_silhouette_vals.shape[0]
                    y_upper = y_lower + size_cluster_i

                    #color = plt.cm.Dark24(i / n_clusters)
                    color = plt.cm.tab20(i / n_clusters)
                    ax.fill_betweenx(
                        np.arange(y_lower, y_upper),
                        0,
                        ith_cluster_silhouette_vals,
                        facecolor=color,
                        edgecolor=color,
                        alpha=0.7
                    )

                    # Etiquetar los graficos de silhouette con sus numeros de cluster en el medio
                    ax.text(-0.05, y_lower + 0.5 * size_cluster_i, str(i))

                    # Calcular el nuevo y_lower para el siguiente cluster
                    y_lower = y_upper + 10

                ax.set_title("Visualización de Silhouette")
                ax.set_xlabel("Coeficiente de Silhouette")
                ax.set_ylabel("Cluster")

                # Linea vertical para el score promedio de silhouette
                ax.axvline(x=silhouette, color="red", linestyle="--")
                ax.text(silhouette + 0.01, y_lower * 0.9, f"Promedio: {silhouette:.3f}")

                ax.set_yticks([])  # Limpiar el eje y
                ax.set_xticks([-0.1, 0, 0.2, 0.4, 0.6, 0.8, 1])
                fig_silhouette.tight_layout()
        except Exception as e:
            print(f"Error creando visualización de silhouette: {e}")
            fig_silhouette = None

        return fig_dist, fig_metrics, fig_clusters, fig_silhouette
    def run_dashboard(self):
        """Ejecuta el dashboard principal."""
        st.set_page_config(
            page_title="Flight ML Dashboard",
            page_icon="✈️",
            layout="wide"
        )

        st.title("🛩️ Flight ML Pipeline Dashboard")
        st.markdown("---")

        # Sidebar con controles
        st.sidebar.header("⚙️ Configuración")
        auto_refresh = st.sidebar.checkbox("🔄 Actualización automática", value=True)
        refresh_interval = st.sidebar.slider(
            "Intervalo de actualización (segundos)",
            10, 300, DASHBOARD_CONFIG['update_frequency']  # Usar valor de configuración
        )

        time_range = st.sidebar.selectbox(
            "⏱️ Rango de tiempo",
            ["Últimos 5 minutos", "Últimos 15 minutos", "Últimos 25 minutos"],
            index=0
        )
        mins_map = {"Últimos 5 minutos": 5, "Últimos 15 minutos": 15, "Últimos 25 minutos": 25}
        mins = mins_map[time_range]

        # if st.sidebar.button("🔄 Actualizar ahora"):
        #     st.experimental_rerun()


        # Contenedor principal
        main_container = st.empty()

        while True:
            with main_container.container():
                # Cargar datos
                with st.spinner("📊 Cargando datos..."):
                    flight_df = self.load_recent_flight_data(mins)
                    metrics_df = self.load_mlflow_metrics()

                # Métricas principales
                col1, col2, col3, col4 = st.columns(4)
                system_metrics = self.get_system_metrics(flight_df, metrics_df)

                col1.metric("✈️ Total Vuelos", system_metrics['total_flights'])
                col2.metric("🚀 Velocidad Promedio", f"{system_metrics['avg_velocity']:.1f} kt")
                col3.metric("📈 Altitud Promedio", f"{system_metrics['avg_altitude']:.0f} ft")

                st.markdown("---")

                # Tabs de contenido
                tab1, tab2, tab3 = st.tabs([
                    "🗺️ Mapa de Vuelos",
                    "📊 Análisis de Vuelos",
                    "🤖 Métricas ML"
                ])

                with tab1:
                    st.header("🗺️ Mapa de Vuelos en Tiempo Real")

                    if not flight_df.empty:
                        flight_map = self.create_flight_map(flight_df)
                        map_data = st_folium(
                            flight_map,
                            width=1000,
                            height=600,
                            key="map"
                        )

                        # Actualizar estado del mapa solo si recibimos datos válidos
                        if map_data and isinstance(map_data, dict):
                            if 'center' in map_data and 'zoom' in map_data:
                                self.map_state = {
                                    'center': map_data['center'],
                                    'zoom': map_data['zoom']
                                }
                    else:
                        st.warning("No hay datos de vuelos disponibles")

                with tab2:
                    st.header("📊 Análisis de Datos de Vuelos")

                    if not flight_df.empty:
                        # Obtener todos los gráficos
                        (fig_vel, fig_alt, fig_scatter,
                         fig_heading, fig_windrose,
                         fig_density,
                         fig_3d) = self.create_flight_analytics(flight_df)

                        # Sección 1: Gráficos principales
                        st.subheader("Métricas Principales")
                        col1, col2 = st.columns(2)
                        col1.plotly_chart(fig_vel, use_container_width=True)
                        col2.plotly_chart(fig_alt, use_container_width=True)

                        st.plotly_chart(fig_scatter, use_container_width=True)

                        # Sección 2: Análisis de dirección
                        st.subheader("Análisis de Dirección de Vuelo")
                        col3, col4 = st.columns(2)
                        col3.plotly_chart(fig_heading, use_container_width=True)
                        col4.plotly_chart(fig_windrose, use_container_width=True)

                        # Sección 3: Distribución espacial
                        st.subheader("Distribución Espacial")
                        st.plotly_chart(fig_density, use_container_width=True)


                        # Sección 5: Análisis 3D
                        st.subheader("Visualización 3D")
                        st.plotly_chart(fig_3d, use_container_width=True)

                    else:
                        st.warning("No hay datos de vuelos disponibles")

                with tab3:
                    st.header("🤖 Métricas del Modelo de Clustering")

                    if not flight_df.empty:
                        # Calcular métricas de clustering
                        n_clusters, _, avg_intra_dist, silhouette, n_outliers = self.create_clustering_metrics(
                            flight_df)

                        # Mostrar KPIs principales
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("Número de Clusters", n_clusters)
                        col2.metric("Distancia Intra-Cluster", f"{avg_intra_dist:.2f} m")
                        col3.metric("Silhouette Score", f"{silhouette:.3f}" if silhouette is not None else "N/A")
                        col4.metric("Puntos Outliers", n_outliers)

                        # Crear y mostrar gráficos
                        fig_dist, fig_metrics, fig_clusters, fig_silhouette = self.create_clustering_plots(flight_df)

                        if fig_dist:
                            st.plotly_chart(fig_dist, use_container_width=True)
                        else:
                            st.warning("No hay datos de distribución de clusters")

                        if fig_metrics:
                            st.plotly_chart(fig_metrics, use_container_width=True)

                        if fig_clusters:
                            st.plotly_chart(fig_clusters, use_container_width=True)

                        if fig_silhouette:
                            st.pyplot(fig_silhouette)
                        else:
                            st.warning("No se pudo generar la visualización de silhouette")
                    else:
                        st.warning("No hay datos disponibles para calcular métricas de clustering")

                # Última actualización
                st.markdown("---")
                st.info(f"📅 Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            # Control de actualización usando el valor de configuración
            if auto_refresh:
                time.sleep(refresh_interval)
                st.rerun()
            else:
                break


if __name__ == "__main__":
    dashboard = FlightDashboard()
    dashboard.run_dashboard()
