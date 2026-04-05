import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "storage.db"

DEFAULT_QUOTA_MB = 100
ALLOWED_EXTENSIONS = {
    "txt",
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "zip",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "csv",
    "json",
    "mp4",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def format_file_size(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size_bytes} B"


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
    app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
    app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
    app.config["DATABASE"] = str(DB_PATH)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    app.teardown_appcontext(close_db)
    app.jinja_env.filters["filesize"] = format_file_size

    with app.app_context():
        init_db()

    register_routes(app)
    return app


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(error=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        storage_quota_mb INTEGER NOT NULL DEFAULT 100,
        used_storage_bytes INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        original_name TEXT NOT NULL,
        stored_name TEXT NOT NULL UNIQUE,
        mime_type TEXT,
        size_bytes INTEGER NOT NULL,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS shared_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id INTEGER NOT NULL,
        token TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
    CREATE INDEX IF NOT EXISTS idx_shared_links_file_id ON shared_links(file_id);
    CREATE INDEX IF NOT EXISTS idx_shared_links_token ON shared_links(token);
    """

    db = get_db()
    db.executescript(schema)
    db.commit()


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    db = get_db()
    return db.execute(
        """
        SELECT id, name, email, storage_quota_mb, used_storage_bytes
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if g.user is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)

    return wrapped_view


def get_owned_file(file_id: int):
    return get_db().execute(
        """
        SELECT id, user_id, original_name, stored_name, mime_type, size_bytes, uploaded_at
        FROM files
        WHERE id = ? AND user_id = ?
        """,
        (file_id, g.user["id"]),
    ).fetchone()


def resolve_shared_link(token: str):
    return get_db().execute(
        """
        SELECT
            l.id AS link_id,
            l.token,
            l.expires_at,
            l.is_active,
            f.id AS file_id,
            f.original_name,
            f.stored_name,
            f.mime_type,
            f.size_bytes,
            u.name AS owner_name
        FROM shared_links l
        JOIN files f ON f.id = l.file_id
        JOIN users u ON u.id = f.user_id
        WHERE l.token = ?
        """,
        (token,),
    ).fetchone()


def register_routes(app: Flask) -> None:
    @app.before_request
    def load_user():
        g.user = get_current_user()

    @app.context_processor
    def inject_globals():
        return {"year": datetime.now().year}

    @app.route("/")
    def index():
        if g.user:
            return redirect(url_for("dashboard"))
        return render_template("index.html")

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not name or not email or not password:
                flash("All fields are required.", "error")
                return render_template("auth/register.html")
            if len(password) < 8:
                flash("Password must be at least 8 characters.", "error")
                return render_template("auth/register.html")
            if password != confirm_password:
                flash("Passwords do not match.", "error")
                return render_template("auth/register.html")

            db = get_db()
            existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                flash("An account with this email already exists.", "error")
                return render_template("auth/register.html")

            db.execute(
                """
                INSERT INTO users (name, email, password_hash, storage_quota_mb, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    generate_password_hash(password),
                    DEFAULT_QUOTA_MB,
                    utc_now_iso(),
                ),
            )
            db.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("auth/register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            db = get_db()
            user = db.execute(
                "SELECT id, password_hash FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Invalid email or password.", "error")
                return render_template("auth/login.html")

            session.clear()
            session["user_id"] = user["id"]
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))

        return render_template("auth/login.html")

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        session.clear()
        flash("You have been logged out.", "success")
        return redirect(url_for("index"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        db = get_db()
        files = db.execute(
            """
            SELECT id, original_name, size_bytes, mime_type, uploaded_at
            FROM files
            WHERE user_id = ?
            ORDER BY uploaded_at DESC
            """,
            (g.user["id"],),
        ).fetchall()

        links = db.execute(
            """
            SELECT
                l.token,
                l.expires_at,
                l.created_at,
                f.original_name
            FROM shared_links l
            JOIN files f ON f.id = l.file_id
            WHERE f.user_id = ? AND l.is_active = 1
            ORDER BY l.created_at DESC
            LIMIT 20
            """,
            (g.user["id"],),
        ).fetchall()

        quota_bytes = g.user["storage_quota_mb"] * 1024 * 1024
        used_bytes = g.user["used_storage_bytes"]
        usage_percent = int((used_bytes / quota_bytes) * 100) if quota_bytes else 0

        return render_template(
            "dashboard.html",
            files=files,
            links=links,
            quota_bytes=quota_bytes,
            used_bytes=used_bytes,
            usage_percent=min(usage_percent, 100),
        )

    @app.route("/upload", methods=["POST"])
    @login_required
    def upload_file():
        file_obj = request.files.get("file")
        if file_obj is None or file_obj.filename == "":
            flash("Please choose a file first.", "error")
            return redirect(url_for("dashboard"))

        original_name = secure_filename(file_obj.filename)
        if not original_name:
            flash("Invalid file name.", "error")
            return redirect(url_for("dashboard"))
        if not allowed_file(original_name):
            flash("File type not allowed.", "error")
            return redirect(url_for("dashboard"))

        file_obj.stream.seek(0, os.SEEK_END)
        size_bytes = file_obj.stream.tell()
        file_obj.stream.seek(0)

        user_quota_bytes = g.user["storage_quota_mb"] * 1024 * 1024
        remaining = user_quota_bytes - g.user["used_storage_bytes"]
        if size_bytes > remaining:
            flash("Upload exceeds your remaining storage quota.", "error")
            return redirect(url_for("dashboard"))

        stored_name = f"{uuid4().hex}_{original_name}"
        save_path = UPLOAD_DIR / stored_name
        file_obj.save(save_path)

        db = get_db()
        db.execute(
            """
            INSERT INTO files (user_id, original_name, stored_name, mime_type, size_bytes, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                g.user["id"],
                original_name,
                stored_name,
                file_obj.mimetype,
                size_bytes,
                utc_now_iso(),
            ),
        )
        db.execute(
            "UPDATE users SET used_storage_bytes = used_storage_bytes + ? WHERE id = ?",
            (size_bytes, g.user["id"]),
        )
        db.commit()

        flash(f"Uploaded: {original_name}", "success")
        return redirect(url_for("dashboard"))

    @app.route("/download/<int:file_id>")
    @login_required
    def download_file(file_id: int):
        file_row = get_owned_file(file_id)
        if file_row is None:
            abort(404)

        return send_from_directory(
            directory=app.config["UPLOAD_FOLDER"],
            path=file_row["stored_name"],
            as_attachment=True,
            download_name=file_row["original_name"],
        )

    @app.route("/delete/<int:file_id>", methods=["POST"])
    @login_required
    def delete_file(file_id: int):
        file_row = get_owned_file(file_id)
        if file_row is None:
            abort(404)

        file_path = UPLOAD_DIR / file_row["stored_name"]
        if file_path.exists():
            file_path.unlink()

        db = get_db()
        db.execute("DELETE FROM files WHERE id = ? AND user_id = ?", (file_id, g.user["id"]))
        db.execute(
            """
            UPDATE users
            SET used_storage_bytes = CASE
                WHEN used_storage_bytes - ? < 0 THEN 0
                ELSE used_storage_bytes - ?
            END
            WHERE id = ?
            """,
            (file_row["size_bytes"], file_row["size_bytes"], g.user["id"]),
        )
        db.commit()

        flash(f"Deleted: {file_row['original_name']}", "success")
        return redirect(url_for("dashboard"))

    @app.route("/share/<int:file_id>", methods=["POST"])
    @login_required
    def share_file(file_id: int):
        file_row = get_owned_file(file_id)
        if file_row is None:
            abort(404)

        expires_days_raw = request.form.get("expires_days", "7").strip()
        try:
            expires_days = int(expires_days_raw)
        except ValueError:
            expires_days = 7

        expires_days = min(max(expires_days, 1), 30)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
        token = secrets.token_urlsafe(24)

        db = get_db()
        db.execute(
            """
            INSERT INTO shared_links (file_id, token, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (file_row["id"], token, expires_at.isoformat(), utc_now_iso()),
        )
        db.commit()

        shared_url = url_for("shared_file", token=token, _external=True)
        flash(f"Share link created: {shared_url}", "success")
        return redirect(url_for("dashboard"))

    @app.route("/s/<token>")
    def shared_file(token: str):
        link_row = resolve_shared_link(token)
        if link_row is None or int(link_row["is_active"]) != 1:
            return render_template("shared_file.html", link=None, is_expired=True), 404

        expires_at = parse_iso_datetime(link_row["expires_at"])
        is_expired = datetime.now(timezone.utc) > expires_at
        if link_row["stored_name"] is None:
            abort(404)
        if is_expired:
            db = get_db()
            db.execute("UPDATE shared_links SET is_active = 0 WHERE id = ?", (link_row["link_id"],))
            db.commit()

        return render_template("shared_file.html", link=link_row, is_expired=is_expired)

    @app.route("/s/<token>/download")
    def shared_download(token: str):
        link_row = resolve_shared_link(token)
        if link_row is None or int(link_row["is_active"]) != 1:
            abort(404)

        expires_at = parse_iso_datetime(link_row["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            db = get_db()
            db.execute("UPDATE shared_links SET is_active = 0 WHERE id = ?", (link_row["link_id"],))
            db.commit()
            abort(410)

        return send_from_directory(
            directory=app.config["UPLOAD_FOLDER"],
            path=link_row["stored_name"],
            as_attachment=True,
            download_name=link_row["original_name"],
        )

    @app.errorhandler(413)
    def payload_too_large(error):
        flash("File is too large. Maximum upload size is 25 MB.", "error")
        return redirect(url_for("dashboard"))


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
