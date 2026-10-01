"""
Main entry point for the Social Media Crisis Management System.
"""

import os
import secrets
from datetime import datetime

from flask import Flask, session, request, abort, render_template
from flask_login import LoginManager
from werkzeug.security import generate_password_hash

from config import Config, BASE
from models import db, User, Keyword, Setting, DEFAULTS, get_setting


# ---------------------------------------------------------
# STATUS / LABEL COLORS
# ---------------------------------------------------------

COLORS = {
    "CRITICAL": "danger",
    "WARNING": "warning",
    "NORMAL": "success",

    "Negative": "danger",
    "Positive": "success",
    "Neutral": "secondary",

    "New": "danger",
    "Reviewing": "warning",
    "Resolved": "success",
}


# ---------------------------------------------------------
# DEFAULT KEYWORDS
# ---------------------------------------------------------

SEED_KEYWORDS = {
    "scam": 3,
    "fraud": 3,
    "fake": 2,
    "refund": 2,
    "complaint": 2,
    "unsafe": 3,
    "danger": 3,
    "terrible": 2,
    "worst": 2,
    "angry": 2,
    "cheating": 3,
    "problem": 1,
    "issue": 1,
    "failure": 2,
    "hack": 3,
    "leak": 3,
    "boycott": 3,
    "lawsuit": 3,
}


# ---------------------------------------------------------
# TIME HELPER
# ---------------------------------------------------------

def ago(dt):
    """
    Convert a datetime value into a human-readable
    relative time such as:
        5 min ago
        2 h ago
        3 d ago
    """

    if not dt:
        return ""

    minutes = int(
        (datetime.utcnow() - dt).total_seconds() // 60
    )

    if minutes < 60:
        return f"{minutes} min ago"

    if minutes < 1440:
        return f"{minutes // 60} h ago"

    return f"{minutes // 1440} d ago"


# ---------------------------------------------------------
# APPLICATION FACTORY
# ---------------------------------------------------------

def create_app():

    # Create Flask application
    app = Flask(__name__)

    # Load application configuration
    app.config.from_object(Config)

    # -----------------------------------------------------
    # DATABASE DIRECTORY
    # -----------------------------------------------------

    os.makedirs(
        os.path.join(BASE, "database"),
        exist_ok=True
    )

    # -----------------------------------------------------
    # DATABASE INITIALIZATION
    # -----------------------------------------------------

    db.init_app(app)

    # -----------------------------------------------------
    # LOGIN MANAGER
    # -----------------------------------------------------

    login_manager = LoginManager()

    login_manager.init_app(app)

    login_manager.login_view = "main.login"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    # -----------------------------------------------------
    # JINJA CUSTOM FILTERS
    # -----------------------------------------------------

    app.jinja_env.filters["color"] = (
        lambda value: COLORS.get(value, "secondary")
    )

    app.jinja_env.filters["ago"] = ago

    # -----------------------------------------------------
    # CSRF PROTECTION
    # -----------------------------------------------------

    @app.before_request
    def csrf_check():

        if request.method != "POST":
            return

        csrf_token = session.get("_csrf")

        submitted_token = request.form.get("_csrf")

        if (
            not csrf_token
            or not submitted_token
            or submitted_token != csrf_token
        ):
            abort(400)

    # -----------------------------------------------------
    # GLOBAL TEMPLATE VARIABLES
    # -----------------------------------------------------

    @app.context_processor
    def inject():

        # Generate CSRF token if it does not exist
        session.setdefault(
            "_csrf",
            secrets.token_hex(16)
        )

        # Get refresh interval
        try:
            refresh = get_setting("refresh_seconds")
        except Exception:
            refresh = DEFAULTS["refresh_seconds"]

        return {
            "csrf": session["_csrf"],
            "refresh": int(float(refresh)),
        }

    # -----------------------------------------------------
    # ERROR HANDLERS
    # -----------------------------------------------------

    error_messages = {
        400: "Bad request or expired form. Please go back and retry.",
        404: "Page not found.",
        413: "File too large (max 2 MB).",
        500: "Something went wrong on our side.",
    }

    for status_code, message in error_messages.items():

        def error_handler(
            error,
            message=message,
            status_code=status_code
        ):
            return (
                render_template(
                    "error.html",
                    msg=message
                ),
                status_code,
            )

        app.register_error_handler(
            status_code,
            error_handler
        )

    # -----------------------------------------------------
    # REGISTER ROUTES
    # -----------------------------------------------------

    from routes import bp

    app.register_blueprint(bp)

    # -----------------------------------------------------
    # DATABASE SETUP
    # -----------------------------------------------------

    with app.app_context():

        # Create database tables
        db.create_all()

        # -------------------------------------------------
        # CREATE DEFAULT ADMIN
        # -------------------------------------------------

        admin_username = os.getenv(
            "ADMIN_USERNAME",
            "admin"
        )

        admin_password = os.getenv(
            "ADMIN_PASSWORD"
        )

        # Only create admin if password is supplied.
        # This avoids putting a real password in GitHub.
        if admin_password:

            existing_admin = User.query.filter_by(
                username=admin_username
            ).first()

            if not existing_admin:

                db.session.add(
                    User(
                        username=admin_username,
                        password_hash=generate_password_hash(
                            admin_password
                        ),
                    )
                )

        # -------------------------------------------------
        # DEFAULT KEYWORDS
        # -------------------------------------------------

        if Keyword.query.count() == 0:

            for keyword, severity in SEED_KEYWORDS.items():

                db.session.add(
                    Keyword(
                        keyword=keyword,
                        severity=severity
                    )
                )

        # -------------------------------------------------
        # DEFAULT SETTINGS
        # -------------------------------------------------

        for setting_name, setting_value in DEFAULTS.items():

            existing_setting = Setting.query.filter_by(
                setting_name=setting_name
            ).first()

            if not existing_setting:

                db.session.add(
                    Setting(
                        setting_name=setting_name,
                        setting_value=setting_value
                    )
                )

        # Save database changes
        db.session.commit()

    return app


# ---------------------------------------------------------
# CREATE APPLICATION
# ---------------------------------------------------------

app = create_app()


# ---------------------------------------------------------
# RUN APPLICATION
# ---------------------------------------------------------

if __name__ == "__main__":

    # Docker / Render can provide PORT.
    # Local development defaults to 5000.
    port = int(
        os.getenv("PORT", "5000")
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
    )