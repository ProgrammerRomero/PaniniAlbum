from flask import Flask

from .routes import bp as album_blueprint


def create_app() -> Flask:
    """
    Application factory for the Panini Album web app.

    Using an app factory keeps the project modular and makes it
    easier to test or extend later (e.g. adding APIs, multiple blueprints).
    """
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    # Secret key is required for some Flask features (e.g. sessions, CSRF).
    # In a real project you would inject this from environment variables,
    # but here we use a fixed value for simplicity.
    app.config["SECRET_KEY"] = "dev-panini-album-change-me"

    # Register the main blueprint that contains all routes.
    app.register_blueprint(album_blueprint)

    return app

