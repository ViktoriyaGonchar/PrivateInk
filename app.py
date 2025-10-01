import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    g,
)
from werkzeug.security import generate_password_hash, check_password_hash

# Markdown rendering and HTML sanitization
import markdown as md
import bleach


# ------------------------------------------------------------
# App configuration
# ------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
app.config["DATABASE_PATH"] = os.path.join(os.path.dirname(__file__), "blog.db")


# ------------------------------------------------------------
# Database helpers (using sqlite3 directly)
# ------------------------------------------------------------
def get_db_connection() -> sqlite3.Connection:
    """Create a new SQLite connection with row factory for dict-like access."""
    connection = sqlite3.connect(app.config["DATABASE_PATH"]) 
    connection.row_factory = sqlite3.Row
    # Enforce foreign keys
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def init_db() -> None:
    """Create tables if they do not exist. Idempotent."""
    connection = get_db_connection()
    try:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content_md TEXT NOT NULL,
                content_html TEXT NOT NULL,
                created_at TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


# ------------------------------------------------------------
# Security: Markdown + Bleach sanitization
# ------------------------------------------------------------
ALLOWED_TAGS = [
    "a",
    "abbr",
    "acronym",
    "b",
    "blockquote",
    "code",
    "em",
    "i",
    "li",
    "ol",
    "strong",
    "ul",
    "p",
    "pre",
    "br",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
]
ALLOWED_ATTRS = {
    "a": ["href", "title", "rel", "target"],
}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def render_markdown_safe(markdown_text: str) -> str:
    """Convert Markdown to sanitized HTML to mitigate XSS."""
    # Convert Markdown to HTML
    html = md.markdown(markdown_text, extensions=["extra", "fenced_code", "tables"])  # type: ignore
    # Sanitize with bleach
    cleaned = bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    # Linkify plain URLs
    return bleach.linkify(cleaned, callbacks=[bleach.linkifier.DEFAULT_CALLBACK])


# ------------------------------------------------------------
# Auth helpers
# ------------------------------------------------------------
def login_required(view_func):
    """Decorator that redirects to login if user is not authenticated."""
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Пожалуйста, войдите в аккаунт.", "warning")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


@app.before_request
def load_logged_in_user():
    """Attach user dict to global request context for templates."""
    user_id = session.get("user_id")
    g.user = None
    if user_id:
        connection = get_db_connection()
        try:
            user = connection.execute(
                "SELECT id, username, email, created_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if user:
                g.user = dict(user)
        finally:
            connection.close()


# ------------------------------------------------------------
# Routes: Home with pagination
# ------------------------------------------------------------
POSTS_PER_PAGE = 5


def fetch_posts_page(page_number: int):
    """Fetch posts and pagination metadata for the given page number."""
    page = max(1, page_number)
    offset = (page - 1) * POSTS_PER_PAGE

    connection = get_db_connection()
    try:
        total_count = connection.execute("SELECT COUNT(*) as c FROM posts").fetchone()[0]
        total_pages = max(1, (total_count + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE)

        rows = connection.execute(
            """
            SELECT posts.id, posts.title, posts.content_html, posts.created_at,
                   users.username AS author
            FROM posts
            JOIN users ON users.id = posts.user_id
            ORDER BY datetime(posts.created_at) DESC
            LIMIT ? OFFSET ?
            """,
            (POSTS_PER_PAGE, offset),
        ).fetchall()

        posts = [dict(r) for r in rows]
        return posts, page, total_pages
    finally:
        connection.close()


@app.get("/")
def index():
    posts, page, total_pages = fetch_posts_page(1)
    return render_template("index.html", posts=posts, page=page, total_pages=total_pages)


@app.get("/page/<int:page>")
def index_page(page: int):
    posts, page, total_pages = fetch_posts_page(page)
    return render_template("index.html", posts=posts, page=page, total_pages=total_pages)


# ------------------------------------------------------------
# Routes: Registration, Login, Logout
# ------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        # Server-side validation
        errors = []
        if not username or len(username) < 3:
            errors.append("Имя пользователя должно содержать минимум 3 символа.")
        if not email or "@" not in email:
            errors.append("Введите корректный email.")
        if not password or len(password) < 6:
            errors.append("Пароль должен содержать минимум 6 символов.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("register.html")

        connection = get_db_connection()
        try:
            # Check duplicates
            existing = connection.execute(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (username, email),
            ).fetchone()
            if existing:
                flash("Такой логин или email уже зарегистрирован.", "danger")
                return render_template("register.html")

            password_hash = generate_password_hash(password)
            created_at = datetime.utcnow().isoformat()
            cursor = connection.execute(
                "INSERT INTO users (username, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (username, email, password_hash, created_at),
            )
            connection.commit()

            # Auto-login after registration
            session["user_id"] = cursor.lastrowid
            flash("Регистрация успешна!", "success")
            return redirect(url_for("index"))
        finally:
            connection.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        connection = get_db_connection()
        try:
            user = connection.execute(
                "SELECT id, username, email, password_hash FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if not user or not check_password_hash(user["password_hash"], password):
                flash("Неверные учетные данные.", "danger")
                return render_template("login.html")

            session["user_id"] = user["id"]
            flash("Вы вошли в систему.", "success")
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        finally:
            connection.close()

    return render_template("login.html")


@app.get("/logout")
def logout():
    session.clear()
    flash("Вы вышли из аккаунта.", "info")
    return redirect(url_for("index"))


# ------------------------------------------------------------
# Routes: Posts CRUD
# ------------------------------------------------------------
@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content_md = (request.form.get("content") or "").strip()

        if not title or not content_md:
            flash("Заполните все поля.", "danger")
            return render_template("create.html", title_value=title, content_value=content_md)

        content_html = render_markdown_safe(content_md)
        created_at = datetime.utcnow().isoformat()

        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO posts (title, content_md, content_html, created_at, user_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, content_md, content_html, created_at, session["user_id"]),
            )
            connection.commit()
            flash("Пост создан.", "success")
            return redirect(url_for("index"))
        finally:
            connection.close()

    return render_template("create.html")


def fetch_post_or_404(post_id: int):
    connection = get_db_connection()
    try:
        row = connection.execute(
            """
            SELECT posts.id, posts.title, posts.content_md, posts.content_html, posts.created_at, posts.user_id,
                   users.username AS author
            FROM posts
            JOIN users ON users.id = posts.user_id
            WHERE posts.id = ?
            """,
            (post_id,),
        ).fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        connection.close()


@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
@login_required
def edit(post_id: int):
    post = fetch_post_or_404(post_id)
    if not post:
        flash("Пост не найден.", "warning")
        return redirect(url_for("index"))
    if post["user_id"] != session.get("user_id"):
        flash("Вы можете редактировать только свои посты.", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content_md = (request.form.get("content") or "").strip()
        if not title or not content_md:
            flash("Заполните все поля.", "danger")
            return render_template("edit.html", post=post, title_value=title, content_value=content_md)

        content_html = render_markdown_safe(content_md)
        connection = get_db_connection()
        try:
            connection.execute(
                "UPDATE posts SET title = ?, content_md = ?, content_html = ? WHERE id = ?",
                (title, content_md, content_html, post_id),
            )
            connection.commit()
            flash("Пост обновлен.", "success")
            return redirect(url_for("profile"))
        finally:
            connection.close()

    return render_template("edit.html", post=post)


@app.post("/delete/<int:post_id>")
@login_required
def delete(post_id: int):
    post = fetch_post_or_404(post_id)
    if not post:
        flash("Пост не найден.", "warning")
        return redirect(url_for("index"))
    if post["user_id"] != session.get("user_id"):
        flash("Вы можете удалять только свои посты.", "danger")
        return redirect(url_for("index"))

    connection = get_db_connection()
    try:
        connection.execute("DELETE FROM posts WHERE id = ?", (post_id,))
        connection.commit()
        flash("Пост удален.", "info")
    finally:
        connection.close()
    return redirect(url_for("profile"))


# ------------------------------------------------------------
# Routes: Profile
# ------------------------------------------------------------
@app.get("/profile")
@login_required
def profile():
    connection = get_db_connection()
    try:
        rows = connection.execute(
            """
            SELECT posts.id, posts.title, posts.created_at
            FROM posts
            WHERE user_id = ?
            ORDER BY datetime(created_at) DESC
            """,
            (session["user_id"],),
        ).fetchall()
        my_posts = [dict(r) for r in rows]
    finally:
        connection.close()

    return render_template("profile.html", my_posts=my_posts)


# ------------------------------------------------------------
# CLI and startup
# ------------------------------------------------------------
@app.cli.command("init-db")
def init_db_command():
    """Initialize the database via CLI: `flask --app app init-db`."""
    init_db()
    print("Initialized the database.")


@app.context_processor
def inject_now():
    return {"now": datetime.utcnow()}


def ensure_db_exists():
    if not os.path.exists(app.config["DATABASE_PATH"]):
        init_db()


if __name__ == "__main__":
    # Ensure DB on first launch
    ensure_db_exists()
    # Run development server
    app.run(host="127.0.0.1", port=5000, debug=True)



