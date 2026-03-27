from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail

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
    # IMPORTANT: Change this to a random secure value in production!
    app.config["SECRET_KEY"] = "dev-panini-album-change-me"

    # Database configuration (SQLite for simplicity)
    # Uses instance folder for database persistence
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///album.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Mail configuration
    # For development: emails print to console
    # For production: configure with real SMTP server (see EMAIL_CONFIG.md)
    app.config["MAIL_SUPPRESS_SEND"] = True  # Set to False to actually send emails
    app.config["MAIL_DEFAULT_SENDER"] = ("Panini Album", "noreply@paninialbum.local")

    # SMTP Settings (only used when MAIL_SUPPRESS_SEND = False)
    # Uncomment and fill in for your email provider:
    # app.config["MAIL_SERVER"] = "smtp.gmail.com"      # or smtp.sendgrid.net
    # app.config["MAIL_PORT"] = 587
    # app.config["MAIL_USE_TLS"] = True
    # app.config["MAIL_USERNAME"] = "your-email@gmail.com"
    # app.config["MAIL_PASSWORD"] = "your-app-password"  # NOT your regular password!

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
    login_manager.login_message = "Por favor inicia sesión para acceder a esta página."
    login_manager.login_message_category = "info"

    # Initialize Flask-Mail
    mail = Mail()
    mail.init_app(app)

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
    # CREATE DATABASE TABLES
    # =========================================================================

    with app.app_context():
        # Create all tables defined in models.py
        db.create_all()

    # =========================================================================
    # REGISTER BLUEPRINTS
    # =========================================================================

    # Main album blueprint (routes for album, stats, exports)
    app.register_blueprint(album_blueprint)

    # Auth blueprint (routes for login, register, password reset)
    app.register_blueprint(auth_bp)

    return app

