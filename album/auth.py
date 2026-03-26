"""
Authentication Blueprint

Handles user registration, login, logout, and password reset functionality.
All routes use CSRF protection (via Flask-WTF implicitly) and secure password hashing.
"""

from datetime import datetime, timezone
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    current_app,
    abort,
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_mail import Message

from .models import db, User, PasswordResetToken
from .utils import validate_email

# Create blueprint
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# =============================================================================
# REGISTRATION
# =============================================================================

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    User registration page.

    GET: Displays registration form
    POST: Processes form submission, creates new user if validation passes

    Validation rules:
    - Username: 3-80 characters, alphanumeric + underscore
    - Email: Valid email format, unique
    - Password: Minimum 6 characters
    """
    # Redirect already logged-in users to album
    if current_user.is_authenticated:
        return redirect(url_for("album.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation
        errors = []

        if not username or len(username) < 3:
            errors.append("El usuario debe tener al menos 3 caracteres.")

        if not email or not validate_email(email):
            errors.append("Ingresa un correo electrónico válido.")

        if not password or len(password) < 6:
            errors.append("La contraseña debe tener al menos 6 caracteres.")

        if password != confirm_password:
            errors.append("Las contraseñas no coinciden.")

        # Check for existing user
        if User.query.filter_by(username=username).first():
            errors.append("Este nombre de usuario ya está registrado.")

        if User.query.filter_by(email=email).first():
            errors.append("Este correo electrónico ya está registrado.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("auth/register.html"), 400

        # Create new user
        try:
            user = User(username=username, email=email, password=password)
            db.session.add(user)
            db.session.commit()

            # Log in the new user
            login_user(user)
            flash(f"¡Bienvenido, {username}! Tu cuenta ha sido creada.", "success")
            return redirect(url_for("album.index"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration error: {e}")
            flash("Ocurrió un error al crear tu cuenta. Por favor intenta de nuevo.", "error")
            return render_template("auth/register.html"), 500

    return render_template("auth/register.html")


# =============================================================================
# LOGIN / LOGOUT
# =============================================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    User login page.

    GET: Displays login form
    POST: Validates credentials and creates session

    Uses Flask-Login's login_user() to manage the session.
    """
    # Redirect already logged-in users
    if current_user.is_authenticated:
        return redirect(url_for("album.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = request.form.get("remember", False) == "on"

        # Find user by username or email
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash("Esta cuenta ha sido desactivada. Contacta soporte.", "error")
                return render_template("auth/login.html"), 403

            # Log in the user
            login_user(user, remember=remember)
            user.update_last_login()

            # Redirect to requested page or album
            next_page = request.args.get("next")
            # Validate next_page to prevent open redirects
            if next_page and not next_page.startswith("/"):
                next_page = None

            flash(f"¡Bienvenido de nuevo, {user.username}!", "success")
            return redirect(next_page or url_for("album.index"))

        else:
            flash("Usuario o contraseña incorrectos.", "error")
            return render_template("auth/login.html"), 401

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """
    Log out the current user.

    Clears the session and redirects to login page.
    """
    logout_user()
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for("auth.login"))


# =============================================================================
# PASSWORD RESET (Forgot Password)
# =============================================================================

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """
    Request password reset email.

    GET: Displays form to enter email
    POST: Sends reset email if account exists

    Security notes:
    - Always shows success message even if email doesn't exist (prevents enumeration)
    - Token expires after 1 hour
    - Console output in development mode (no real email sent)
    """
    if current_user.is_authenticated:
        return redirect(url_for("album.index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            flash("Por favor ingresa tu correo electrónico.", "error")
            return render_template("auth/forgot_password.html"), 400

        user = User.query.filter_by(email=email).first()

        if user:
            # Generate reset token
            token = PasswordResetToken(user_id=user.id)
            db.session.add(token)
            db.session.commit()

            # Send email
            send_password_reset_email(user.email, token.token)

        # Always show success (prevents email enumeration)
        flash(
            "Si existe una cuenta con ese correo, hemos enviado instrucciones para restablecer tu contraseña.",
            "success"
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    """
    Reset password using token from email.

    GET: Displays form to enter new password (validates token first)
    POST: Validates token and updates password

    Query parameters:
    - token: The reset token from the email
    """
    if current_user.is_authenticated:
        return redirect(url_for("album.index"))

    token_value = request.args.get("token") or request.form.get("token")

    if not token_value:
        flash("Enlace de recuperación inválido.", "error")
        return redirect(url_for("auth.forgot_password"))

    # Find and validate token
    reset_token = PasswordResetToken.query.filter_by(token=token_value).first()

    if not reset_token or not reset_token.is_valid():
        flash(
            "El enlace de recuperación ha expirado o es inválido. "
            "Por favor solicita uno nuevo.",
            "error"
        )
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []

        if not password or len(password) < 6:
            errors.append("La contraseña debe tener al menos 6 caracteres.")

        if password != confirm_password:
            errors.append("Las contraseñas no coinciden.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("auth/reset_password.html", token=token_value), 400

        # Update password
        try:
            user = User.query.get(reset_token.user_id)
            user.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
            reset_token.mark_as_used()

            flash(
                "Tu contraseña ha sido actualizada correctamente. "
                "Ya puedes iniciar sesión con tu nueva contraseña.",
                "success"
            )
            return redirect(url_for("auth.login"))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Password reset error: {e}")
            flash("Ocurrió un error al actualizar tu contraseña. Por favor intenta de nuevo.", "error")
            return render_template("auth/reset_password.html", token=token_value), 500

    return render_template("auth/reset_password.html", token=token_value)


# =============================================================================
# PROFILE
# =============================================================================

@auth_bp.route("/profile")
@login_required
def profile():
    """
    User profile page.

    Displays user information and collection stats.
    """
    # Count owned stickers
    owned_count = current_user.stickers.filter_by(is_owned=True).count()

    # Count total duplicates
    duplicates_count = db.session.query(db.func.sum(UserSticker.duplicate_count)).filter_by(
        user_id=current_user.id
    ).scalar() or 0

    stats = {
        "owned": owned_count,
        "duplicates": duplicates_count,
        "member_since": current_user.created_at.strftime("%d/%m/%Y"),
    }

    return render_template("auth/profile.html", stats=stats)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def send_password_reset_email(to_email: str, token: str):
    """
    Send password reset email.

    In development mode, prints to console instead of sending actual email.
    In production, configure Flask-Mail with SMTP settings.

    Args:
        to_email: Recipient email address
        token: Reset token to include in the link
    """
    reset_url = url_for("auth.reset_password", token=token, _external=True)

    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        # Development mode: print to console
        print("=" * 60)
        print("PASSWORD RESET EMAIL")
        print("=" * 60)
        print(f"To: {to_email}")
        print(f"Subject: Recuperación de contraseña - Panini Album")
        print("-" * 60)
        print(f"Para restablecer tu contraseña, haz clic en el siguiente enlace:")
        print(f"{reset_url}")
        print("-" * 60)
        print(f"Este enlace expirará en 1 hora.")
        print("=" * 60)
    else:
        # Production mode: send actual email
        from flask_mail import Mail
        mail = Mail(current_app)

        msg = Message(
            subject="Recuperación de contraseña - Panini Album",
            recipients=[to_email],
            body=f"""Para restablecer tu contraseña, haz clic en el siguiente enlace:

{reset_url}

Este enlace expirará en 1 hora.

Si no solicitaste este cambio, ignora este correo.
""",
            html=render_template("emails/reset_password.html", reset_url=reset_url),
        )
        mail.send(msg)
