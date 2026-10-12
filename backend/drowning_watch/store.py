import sqlite3
from pathlib import Path


class Store:
    def __init__(self, database_url: str):
        if not database_url.startswith("sqlite:///"):
            raise ValueError("This prototype currently supports SQLite only; production PostgreSQL is not implemented.")
        raw_path = database_url.removeprefix("sqlite:///")
        self.path = Path(raw_path)
        if not self.path.is_absolute():
            self.path = Path.cwd() / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self):
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, filename TEXT NOT NULL, status TEXT NOT NULL,
              progress REAL NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
              output_path TEXT, error TEXT, summary TEXT
            );
            CREATE TABLE IF NOT EXISTS incidents (
              id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
              track_id INTEGER NOT NULL, state TEXT NOT NULL, score REAL,
              timestamp_seconds REAL NOT NULL, class_name TEXT,
              created_at TEXT NOT NULL, FOREIGN KEY(job_id) REFERENCES jobs(id)
            );
            """)

    def create_job(self, job_id: str, filename: str, created_at: str):
        with self.connect() as db:
            db.execute("INSERT INTO jobs(id,filename,status,created_at) VALUES(?,?,?,?)",
                       (job_id, filename, "queued", created_at))

    def update_job(self, job_id: str, **fields):
        allowed = {"status", "progress", "output_path", "error", "summary"}
        values = {k: v for k, v in fields.items() if k in allowed}
        if not values:
            return
        sql = ",".join(f"{key}=?" for key in values)
        with self.connect() as db:
            db.execute(f"UPDATE jobs SET {sql} WHERE id=?", (*values.values(), job_id))

    def add_incidents(self, job_id: str, events: list[dict], created_at: str):
        with self.connect() as db:
            db.executemany("INSERT INTO incidents(job_id,track_id,state,score,timestamp_seconds,class_name,created_at) VALUES(?,?,?,?,?,?,?)",
                            [(job_id, e["track_id"], e["state"], e["score"], e["timestamp_seconds"], e["class_name"], created_at) for e in events])

    def get_job(self, job_id: str):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list_jobs(self, limit: int = 50):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))]

    def list_incidents(self, limit: int = 100):
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM incidents ORDER BY created_at DESC LIMIT ?", (limit,))]
