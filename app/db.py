import sqlite3
import os
from datetime import datetime
import pandas as pd


def _default_db_path():
    return os.getenv("DB_PATH", os.path.join(os.getcwd(), "pmv.db"))


def get_conn(db_path: str | None = None):
    if db_path is None:
        db_path = _default_db_path()
    # allow multi-threaded access from streamlit
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    return conn


def init_db(db_path: str | None = None):
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER,
            player TEXT,
            action TEXT,
            created_at TEXT,
            FOREIGN KEY(game_id) REFERENCES games(id)
        )
        """
    )
    # players table to persist players across sessions
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def start_new_game(conn=None, db_path: str | None = None) -> int:
    close_after = False
    if conn is None:
        conn = get_conn(db_path)
        close_after = True
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute("INSERT INTO games (created_at) VALUES (?)", (now,))
    conn.commit()
    game_id = cur.lastrowid
    if close_after:
        conn.close()
    return game_id


def get_current_game_id(db_path: str | None = None) -> int | None:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id FROM games ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def get_games_df(db_path: str | None = None) -> pd.DataFrame:
    conn = get_conn(db_path)
    df = pd.read_sql_query("SELECT * FROM games ORDER BY id DESC", conn)
    conn.close()
    if not df.empty and 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at'])
    return df


def add_player(name: str, db_path: str | None = None) -> int:
    name = name.strip()
    if not name:
        raise ValueError('empty name')
    conn = get_conn(db_path)
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    try:
        cur.execute("INSERT INTO players (name, created_at) VALUES (?, ?)", (name, now))
        conn.commit()
        player_id = cur.lastrowid
    except sqlite3.IntegrityError:
        # already exists: return existing id
        cur.execute("SELECT id FROM players WHERE name = ?", (name,))
        row = cur.fetchone()
        player_id = row[0] if row else None
    conn.close()
    return player_id


def list_players(db_path: str | None = None) -> list:
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM players ORDER BY name COLLATE NOCASE")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


def insert_event(player: str, action: str, game_id: int | None = None, db_path: str | None = None):
    conn = get_conn(db_path)
    cur = conn.cursor()
    # ensure player exists in players table
    cur.execute("SELECT id FROM players WHERE name = ?", (player,))
    r = cur.fetchone()
    if not r:
        # create player
        now = datetime.utcnow().isoformat()
        try:
            cur.execute("INSERT INTO players (name, created_at) VALUES (?, ?)", (player, now))
            conn.commit()
        except sqlite3.IntegrityError:
            pass

    if game_id is None:
        cur.execute("SELECT id FROM games ORDER BY id DESC LIMIT 1")
        r = cur.fetchone()
        if r:
            game_id = r[0]
        else:
            game_id = start_new_game(conn=conn)

    now = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO events (game_id, player, action, created_at) VALUES (?, ?, ?, ?)",
        (game_id, player, action, now),
    )
    conn.commit()
    conn.close()


def get_events_df(db_path: str | None = None, game_id: int | None = None, game_ids: list | None = None, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    conn = get_conn(db_path)
    query = "SELECT * FROM events"
    params = []
    clauses = []

    # support multiple game ids
    if game_ids:
        placeholders = ','.join('?' for _ in game_ids)
        clauses.append(f"game_id IN ({placeholders})")
        params.extend(game_ids)
    elif game_id is not None:
        clauses.append("game_id = ?")
        params.append(game_id)

    if start_date is not None:
        clauses.append("created_at >= ?")
        params.append(start_date)
    if end_date is not None:
        clauses.append("created_at <= ?")
        params.append(end_date)
    if clauses:
        query = query + " WHERE " + " AND ".join(clauses)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    if not df.empty and 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at'])
    return df


def get_stats(db_path: str | None = None) -> pd.DataFrame:
    df = get_events_df(db_path)
    if df.empty:
        return pd.DataFrame()

    # normalize action names
    # actions: serve_point, serve_error, attack_point, attack_error, reception_good, reception_bad
    players = df['player'].unique()
    rows = []
    for p in players:
        sub = df[df['player'] == p]
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

        rows.append(
            {
                'player': p,
                'attacks_total': attacks_total,
                'attack_points': attack_points,
                'attack_errors': attack_errors,
                'attack_success_pct': attack_pct,
                'serves_total': serves_total,
                'serve_points': serve_points,
                'serve_errors': serve_errors,
                'serve_success_pct': serve_pct,
                'reception_total': reception_total,
                'reception_good': reception_good,
                'reception_bad': reception_bad,
                'reception_efficiency_pct': reception_pct,
            }
        )

    result = pd.DataFrame(rows)
    result = result.sort_values('player').reset_index(drop=True)
    return result
