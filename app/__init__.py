"""Flask application factory."""
import logging

from flask import Flask, send_from_directory

from .config import settings
from .routes import blueprints


def create_app() -> Flask:
    logging.basicConfig(level=settings.log_level)
    app = Flask(__name__, static_folder=None)

    from .routes._auth import load_principal
    app.before_request(load_principal)

    for bp in blueprints:
        app.register_blueprint(bp)

    # Serve the built UI in production; in dev the mock lives in ui/mock.
    @app.get("/")
    def index():
        return send_from_directory("../ui/mock", "index.html")

    @app.get("/ui/<path:path>")
    def ui(path):
        return send_from_directory("../ui/mock", path)

    @app.get("/chat")
    def chat_page():
        # The in-app AI dashboard builder (chat window).
        return send_from_directory("../ui/mock", "chat.html")

    return app


# Note: the app is built on demand via create_app() (see wsgi.py), not at
# import time — so importing app.generator / app.pdc_client from the MCP
# server doesn't construct a Flask app or register routes.
