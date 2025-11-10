import streamlit as st
import pandas as pd
import os
from datetime import date
import plotly.express as px
import plotly.graph_objects as go
from app import db


DB_PATH = os.getenv('DB_PATH', os.path.join(os.getcwd(), 'pmv.db'))
db.init_db(DB_PATH)


st.set_page_config(page_title='PMV - Registro', layout='wide')
st.title('PMV - Registro de Acciones (Saque / Ataque / Recepción)')


# safe rerun helper (Streamlit versions vary)
def _safe_rerun():
    try:
        st.experimental_rerun()
    except Exception:
        # fallback: stop execution and ask user to refresh
        st.info('Por favor refresca la página para ver los cambios')
        st.stop()


# --- Juegos disponibles y creación ---
games_df = db.get_games_df(DB_PATH)
games = []
if not games_df.empty:
    games = [f"{int(r.id)} - {r.created_at.strftime('%Y-%m-%d %H:%M:%S')}" for r in games_df.itertuples()]

col_top = st.columns([2, 4, 3])
with col_top[0]:
    if st.button('Juego Nuevo'):
        conn = db.get_conn(DB_PATH)
        new_id = db.start_new_game(conn=conn)
        conn.close()
        st.success(f'Juego nuevo creado: id={new_id}')
        _safe_rerun()

with col_top[1]:
    # allow multiple selection of games; default to latest if none selected
    selected_games = st.multiselect('Seleccionar Juego(s) (opcional)', options=['--Último--'] + games, default=['--Último--'] if games else [])

with col_top[2]:
    st.write('DB:')
    st.write(DB_PATH)

# parse selected_games to ids
selected_game_ids = None
if selected_games:
    # handle the special token '--Último--'
    if '--Último--' in selected_games:
        last = db.get_current_game_id(DB_PATH)
        if last:
            selected_game_ids = [last]
    else:
        ids = []
        for s in selected_games:
            try:
                ids.append(int(s.split(' - ')[0]))
            except Exception:
                continue
        selected_game_ids = ids if ids else None
else:
    # default: use latest game
    lg = db.get_current_game_id(DB_PATH)
    selected_game_ids = [lg] if lg else None


# --- Cargar eventos y jugadores (filtrados por juego si aplica) ---
events_df = db.get_events_df(DB_PATH, game_ids=selected_game_ids)
existing_players = db.list_players(DB_PATH)
players = sorted(existing_players)


# --- Crear / seleccionar jugador con confirmación y evitar duplicados ---
st.markdown('### Jugador')
colp1, colp2 = st.columns([3, 1])
with colp1:
    new_player = st.text_input('Nuevo jugador (escribir nombre y luego presionar Crear)')
with colp2:
    if st.button('Crear jugador'):
        name = new_player.strip()
        if not name:
            st.warning('El nombre está vacío')
        elif name in players:
            st.warning('Jugador ya existe')
        else:
            db.add_player(name, db_path=DB_PATH)
            st.success(f'Jugador "{name}" creado')
            _safe_rerun()

selected_player = st.selectbox('Jugador', options=['--Seleccionar--'] + players)
if selected_player == '--Seleccionar--':
    selected_player = None

if not selected_player:
    st.info('Selecciona o crea un jugador para comenzar a registrar acciones')


# --- Filtros por fecha ---
st.markdown('### Filtros')
min_date = events_df['created_at'].min().date() if (not events_df.empty) else date.today()
max_date = events_df['created_at'].max().date() if (not events_df.empty) else date.today()
start_date, end_date = st.date_input('Rango de fechas', value=(min_date, max_date))
start_iso = pd.to_datetime(start_date).isoformat() if start_date else None
end_iso = pd.to_datetime(end_date).isoformat() if end_date else None


# --- Botones de acción ---
if selected_player:
    st.markdown('### Acciones')
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button('Saque Punto'):
            gid = selected_game_ids[0] if selected_game_ids else None
            db.insert_event(selected_player, 'serve_point', game_id=gid, db_path=DB_PATH)
            _safe_rerun()
        if st.button('Saque Error'):
            gid = selected_game_ids[0] if selected_game_ids else None
            db.insert_event(selected_player, 'serve_error', game_id=gid, db_path=DB_PATH)
            _safe_rerun()
    with c2:
        if st.button('Ataque Punto'):
            gid = selected_game_ids[0] if selected_game_ids else None
            db.insert_event(selected_player, 'attack_point', game_id=gid, db_path=DB_PATH)
            _safe_rerun()
        if st.button('Ataque Error'):
            gid = selected_game_ids[0] if selected_game_ids else None
            db.insert_event(selected_player, 'attack_error', game_id=gid, db_path=DB_PATH)
            _safe_rerun()
    with c3:
        if st.button('Recepción Buena'):
            gid = selected_game_ids[0] if selected_game_ids else None
            db.insert_event(selected_player, 'reception_good', game_id=gid, db_path=DB_PATH)
            _safe_rerun()
        if st.button('Recepción Mala'):
            gid = selected_game_ids[0] if selected_game_ids else None
            db.insert_event(selected_player, 'reception_bad', game_id=gid, db_path=DB_PATH)
            _safe_rerun()


# --- Cargar eventos filtrados ---
filtered_events = db.get_events_df(DB_PATH, game_ids=selected_game_ids, start_date=start_iso, end_date=end_iso)

st.markdown('## Estadísticas por jugador')
if filtered_events.empty:
    st.write('No hay datos en el rango seleccionado. Registra acciones para ver estadísticas.')
else:
    # calcular estadísticas con pandas directamente sobre el df filtrado
    stats_rows = []
    for p in sorted(filtered_events['player'].unique()):
        sub = filtered_events[filtered_events['player'] == p]
        attack_points = int((sub['action'] == 'attack_point').sum())
        attack_errors = int((sub['action'] == 'attack_error').sum())
        attacks_total = attack_points + attack_errors
        attack_pct = round((attack_points / attacks_total) * 100, 1) if attacks_total > 0 else None

        serve_points = int((sub['action'] == 'serve_point').sum())
        serve_errors = int((sub['action'] == 'serve_error').sum())
        serves_total = serve_points + serve_errors
        serve_pct = round((serve_points / serves_total) * 100, 1) if serves_total > 0 else None

        reception_good = int((sub['action'] == 'reception_good').sum())
        reception_bad = int((sub['action'] == 'reception_bad').sum())
        reception_total = reception_good + reception_bad
        reception_pct = round((reception_good / reception_total) * 100, 1) if reception_total > 0 else None

        stats_rows.append({
            'Jugador': p,
            'Ataques Totales': attacks_total,
            'Puntos (Ataque)': attack_points,
            'Errores (Ataque)': attack_errors,
            'Eficacia Ataque (%)': attack_pct,
            'Saque Totales': serves_total,
            'Puntos (Saque)': serve_points,
            'Errores (Saque)': serve_errors,
            'Eficacia Saque (%)': serve_pct,
            'Recepciones Totales': reception_total,
            'Recepciones Buenas': reception_good,
            'Recepciones Malas': reception_bad,
            'Eficacia Recepción (%)': reception_pct,
        })

    stats_df = pd.DataFrame(stats_rows)

    # aplicar estilo sencillo: gradiente sobre eficacia de ataque
    try:
        styler = stats_df.style.background_gradient(subset=['Eficacia Ataque (%)'], cmap='Greens')
        st.dataframe(styler, use_container_width=True)
    except Exception:
        st.dataframe(stats_df, use_container_width=True)

    # exportar CSV de eventos filtrados
    with st.expander('Ver eventos (raw)'):
        st.dataframe(filtered_events.sort_values('created_at', ascending=False).reset_index(drop=True))
        csv = filtered_events.to_csv(index=False).encode('utf-8')
        st.download_button('Descargar eventos (CSV)', data=csv, file_name='pmv_events.csv', mime='text/csv')

    # --- Visualizaciones específicas de voleibol ---
    st.markdown('## Visualizaciones')

    # 1. Radar chart de eficacia por jugador
    if not stats_df.empty:
        st.subheader('Eficacia por Jugador (Radar Chart)')
        
        # preparar datos para radar chart
        fig = go.Figure()
        for jugador in stats_df['Jugador'].unique():
            row = stats_df[stats_df['Jugador'] == jugador].iloc[0]
            fig.add_trace(go.Scatterpolar(
                r=[
                    row['Eficacia Ataque (%)'] or 0,
                    row['Eficacia Saque (%)'] or 0,
                    row['Eficacia Recepción (%)'] or 0
                ],
                theta=['Ataque', 'Saque', 'Recepción'],
                fill='toself',
                name=jugador
            ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )),
            showlegend=True,
            title='Eficacia en Ataque, Saque y Recepción (%)'
        )
        st.plotly_chart(fig, use_container_width=True)

        # 2. Barras apiladas de puntos vs errores
        st.subheader('Puntos vs Errores por Jugador')
        
        # preparar datos para barras
        fig_bars = go.Figure()
        
        # ataque
        fig_bars.add_trace(go.Bar(
            name='Puntos (Ataque)',
            x=stats_df['Jugador'],
            y=stats_df['Puntos (Ataque)'],
            marker_color='#2ecc71'
        ))
        fig_bars.add_trace(go.Bar(
            name='Errores (Ataque)',
            x=stats_df['Jugador'],
            y=stats_df['Errores (Ataque)'],
            marker_color='#e74c3c'
        ))
        
        # saque
        fig_bars.add_trace(go.Bar(
            name='Puntos (Saque)',
            x=stats_df['Jugador'],
            y=stats_df['Puntos (Saque)'],
            marker_color='#3498db'
        ))
        fig_bars.add_trace(go.Bar(
            name='Errores (Saque)',
            x=stats_df['Jugador'],
            y=stats_df['Errores (Saque)'],
            marker_color='#e67e22'
        ))

        fig_bars.update_layout(
            barmode='group',
            title='Distribución de Puntos y Errores por Jugador',
            xaxis_title='Jugador',
            yaxis_title='Cantidad'
        )
        st.plotly_chart(fig_bars, use_container_width=True)

        # 3. Timeline de acciones en el juego
        if not filtered_events.empty:
            st.subheader('Línea de Tiempo de Acciones')
            
            # preparar datos para timeline
            timeline_df = filtered_events.copy()
            timeline_df['action_type'] = timeline_df['action'].apply(lambda x: 'Punto' if 'point' in x else 'Error' if 'error' in x else 'Recepción')
            timeline_df['color'] = timeline_df['action_type'].map({
                'Punto': '#2ecc71',
                'Error': '#e74c3c',
                'Recepción': '#3498db'
            })

            fig_timeline = px.scatter(
                timeline_df,
                x='created_at',
                y='player',
                color='action_type',
                color_discrete_map={
                    'Punto': '#2ecc71',
                    'Error': '#e74c3c',
                    'Recepción': '#3498db'
                },
                hover_data=['action'],
                title='Acciones por Jugador en el Tiempo'
            )

            fig_timeline.update_traces(marker=dict(size=10))
            fig_timeline.update_layout(
                xaxis_title='Tiempo',
                yaxis_title='Jugador',
                showlegend=True
            )

            st.plotly_chart(fig_timeline, use_container_width=True)

            # 4. Distribución de acciones
            st.subheader('Distribución de Acciones por Tipo')
            
            # contar acciones por tipo
            action_counts = timeline_df['action_type'].value_counts()
            
            fig_pie = go.Figure(data=[go.Pie(
                labels=action_counts.index,
                values=action_counts.values,
                hole=.3,
                marker_colors=['#2ecc71', '#e74c3c', '#3498db']
            )])

            fig_pie.update_layout(title='Distribución de Tipos de Acciones')
            st.plotly_chart(fig_pie, use_container_width=True)

