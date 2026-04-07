import logging
import os
from datetime import timedelta
from logging.handlers import RotatingFileHandler

from flask import Flask, request, g
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

from .routes import bp as album_blueprint
from .auth import auth_bp
from .models import db, bcrypt, User
from .config import team_pages_by_code


def create_app() -> Flask:
    """
    Application factory for the Panini Album web app.

    Using an app factory keeps the project modular and makes it
    easier to test or extend later (e.g. adding APIs, multiple blueprints).

    Features added:
    - SQLAlchemy database integration
    - Flask-Login for session management
    - Flask-Bcrypt for password hashing
    - Flask-Mail for password reset emails
    """
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    # =========================================================================
    # CONFIGURATION
    # =========================================================================

    # Secret key for sessions and CSRF protection
    # Use environment variable in production, fallback for development
    # Try FLASK_SECRET_KEY first (user preference), then SECRET_KEY (Railway default)
    secret_key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY")
    if not secret_key:
        secret_key = "dev-panini-album-change-me"
    app.config["SECRET_KEY"] = secret_key

    # Database configuration
    # Use PostgreSQL from environment variable in production, SQLite locally
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        # Railway uses postgres:// but SQLAlchemy requires postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    else:
        # SQLite for local development
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///album.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Create upload directory for user photos (Railway compatible)
    upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'photos')
    os.makedirs(upload_folder, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_folder

    # =========================================================================
    # SECURITY CONFIGURATION
    # =========================================================================

    # Session cookie security settings
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=1)

    # Mail configuration
    # Check if email is configured via environment variables
    mail_server = os.environ.get("MAIL_SERVER", "").strip()
    mail_suppress_val = os.environ.get("MAIL_SUPPRESS_SEND", "true").strip().lower().strip('"')
    mail_suppress = mail_suppress_val in ("true", "1", "yes", "on")

    if mail_server and not mail_suppress:
        # Production: Use real SMTP server
        app.config["MAIL_SUPPRESS_SEND"] = False
        app.config["MAIL_SERVER"] = mail_server
        app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
        app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
        app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
        app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
        app.config["MAIL_DEFAULT_SENDER"] = (
            "Panini Album",
            os.environ.get("MAIL_DEFAULT_SENDER", os.environ.get("MAIL_USERNAME"))
        )
    else:
        # Development: emails print to console
        app.config["MAIL_SUPPRESS_SEND"] = True
        app.config["MAIL_DEFAULT_SENDER"] = ("Panini Album", "noreply@paninialbum.local")

    # =========================================================================
    # INITIALIZE EXTENSIONS
    # =========================================================================

    # Initialize database
    db.init_app(app)

    # Initialize bcrypt for password hashing
    bcrypt.init_app(app)

    # Initialize Flask-Login
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"  # Route name for login page
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "info"

    # Initialize Flask-Mail
    mail = Mail()
    mail.init_app(app)

    # Initialize CSRF Protection
    csrf = CSRFProtect()
    csrf.init_app(app)

    # =========================================================================
    # LOGGING CONFIGURATION (for monitoring)
    # =========================================================================

    if not app.debug:
        # Production logging
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        stream_handler.setFormatter(formatter)
        app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info("Panini Album startup")

    # =========================================================================
    # USER LOADER (required by Flask-Login)
    # =========================================================================

    @login_manager.user_loader
    def load_user(user_id):
        """
        Load user from database by ID.

        This callback is required by Flask-Login to manage user sessions.
        It receives the user_id from the session cookie and returns the User object.
        """
        return User.query.get(int(user_id))

    # =========================================================================
    # JINJA2 FILTERS
    # =========================================================================

    from datetime import datetime, timezone

    @app.template_filter("aus_time")
    def aus_time_filter(dt, format_str="%b %d, %I:%M %p"):
        """
        Convert UTC datetime to Australian Eastern Time (UTC+10 or UTC+11 for DST).

        Usage in templates:
            {{ message.created_at|aus_time }}
            {{ message.created_at|aus_time("%Y-%m-%d %H:%M") }}
        """
        if dt is None:
            return ""

        # Make sure datetime is timezone-aware (assume UTC if naive)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        # Australian Eastern Time (UTC+10 standard, UTC+11 during DST)
        # DST is from first Sunday in October to first Sunday in April
        aus_tz = timezone(timedelta(hours=10))  # AEST (standard time)
        aus_dt = dt.astimezone(aus_tz)

        return aus_dt.strftime(format_str)

    @app.template_filter("aus_time_short")
    def aus_time_short_filter(dt):
        """Short format: HH:MM AM/PM"""
        return aus_time_filter(dt, "%I:%M %p")

    @app.template_filter("aus_date")
    def aus_date_filter(dt):
        """Date only format: Month DD, YYYY"""
        return aus_time_filter(dt, "%B %d, %Y")

    # =========================================================================
    # CONTEXT PROCESSOR (inject variables into all templates)
    # =========================================================================

    @app.context_processor
    def inject_team_pages():
        """
        Inject team_pages into all templates.

        This makes the teams dropdown available in all templates without
        having to pass it explicitly in every route.
        """
        return dict(team_pages=team_pages_by_code())

    # =========================================================================
    # SECURITY HEADERS MIDDLEWARE
    # =========================================================================

    @app.after_request
    def add_security_headers(response):
        """
        Add security headers to all responses.
        """
        # Prevent clickjacking attacks
        response.headers["X-Frame-Options"] = "SAMEORIGIN"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content Security Policy - restrictive but allows necessary resources
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://flagcdn.com; "
            "img-src 'self' data: https://flagcdn.com; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

        # Referrer Policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        return response

    # =========================================================================
    # CREATE DATABASE TABLES
    # =========================================================================

    with app.app_context():
        # Create all tables defined in models.py
        db.create_all()

        # Auto-migrate: Add missing columns and tables for multi-album feature
        from sqlalchemy import text, inspect

        def column_exists(table_name, column_name):
            """Check if a column exists in a table."""
            try:
                # Try PostgreSQL information_schema first
                result = db.session.execute(text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = :table AND column_name = :column"
                ), {"table": table_name, "column": column_name}).fetchone()
                return result is not None
            except:
                # Fall back to SQLAlchemy inspector (works for SQLite)
                try:
                    inspector = inspect(db.engine)
                    columns = [col['name'] for col in inspector.get_columns(table_name)]
                    return column_name in columns
                except:
                    return False

        def add_column(table_name, column_name, data_type):
            """Add a column if it doesn't exist."""
            if not column_exists(table_name, column_name):
                try:
                    db.session.execute(text(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {data_type}"
                    ))
                    db.session.commit()
                    app.logger.info(f"Auto-migrated: Added {column_name} column to {table_name} table")
                    return True
                except Exception as e:
                    app.logger.warning(f"Could not add {column_name} column: {e}")
                    db.session.rollback()
                    return False
            return True

        # Add missing columns to users table
        add_column("users", "city", "VARCHAR(100)")
        add_column("users", "has_selected_version", "BOOLEAN DEFAULT FALSE")

        # Add missing column to user_stickers table
        add_column("user_stickers", "album_version_id", "INTEGER")

        # Create album_versions table if it doesn't exist
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()

            if 'album_versions' not in tables:
                db.session.execute(text("""
                    CREATE TABLE album_versions (
                        id SERIAL PRIMARY KEY,
                        code VARCHAR(20) UNIQUE NOT NULL,
                        name VARCHAR(50) NOT NULL,
                        display_name VARCHAR(100),
                        theme_css_class VARCHAR(50),
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """))
                db.session.commit()
                app.logger.info("Auto-migrated: Created album_versions table")

                # Insert default versions
                db.session.execute(text("""
                    INSERT INTO album_versions (code, name, display_name, theme_css_class, is_active) VALUES
                    ('gold', 'Gold', 'Gold Edition', 'theme-gold', TRUE),
                    ('blue', 'Blue', 'Blue Edition', 'theme-blue', TRUE),
                    ('orange', 'Orange', 'Orange Edition', 'theme-orange', TRUE)
                """))
                db.session.commit()
                app.logger.info("Auto-migrated: Inserted default album versions")

            if 'user_albums' not in tables:
                db.session.execute(text("""
                    CREATE TABLE user_albums (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        album_version_id INTEGER NOT NULL,
                        is_active BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                db.session.commit()
                app.logger.info("Auto-migrated: Created user_albums table")

        except Exception as e:
            app.logger.warning(f"Could not create tables: {e}")
            db.session.rollback()

    # =========================================================================
    # REGISTER BLUEPRINTS
    # =========================================================================

    # Main album blueprint (routes for album, stats, exports)
    app.register_blueprint(album_blueprint)

    # Auth blueprint (routes for login, register, password reset)
    app.register_blueprint(auth_bp)

    return app

