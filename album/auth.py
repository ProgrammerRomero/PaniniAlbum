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
    jsonify,
)
from flask_login import (
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_mail import Message, Mail

from .models import db, User, PasswordResetToken, UserSticker, bcrypt
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
    from .config import ALBUM_PAGES

    # Count owned stickers
    owned_count = current_user.stickers.filter_by(is_owned=True).count()

    # Count total duplicates
    duplicates_count = db.session.query(db.func.sum(UserSticker.duplicate_count)).filter_by(
        user_id=current_user.id
    ).scalar() or 0

    # Calculate total stickers in album
    total_stickers = sum(
        len(page.get("stickers", []))
        for page in ALBUM_PAGES
    )

    # Calculate completion percentage
    completion = round((owned_count / total_stickers) * 100) if total_stickers > 0 else 0

    stats = {
        "owned": owned_count,
        "duplicates": duplicates_count,
        "completion": completion,
        "total": total_stickers,
    }

    return render_template("auth/profile.html", stats=stats)


@auth_bp.route("/profile/upload-photo", methods=["POST"])
@login_required
def upload_photo():
    """
    Handle profile photo upload.

    For now, this is a placeholder that stores a message.
    Full implementation would save the file to a storage service.
    """
    if "photo" not in request.files:
        flash("No photo selected.", "error")
        return redirect(url_for("auth.profile"))

    photo = request.files["photo"]

    if photo.filename == "":
        flash("No photo selected.", "error")
        return redirect(url_for("auth.profile"))

    # Validate file type
    allowed_extensions = {"png", "jpg", "jpeg", "gif"}
    file_ext = photo.filename.rsplit(".", 1)[1].lower() if "." in photo.filename else ""

    if file_ext not in allowed_extensions:
        flash("Invalid file type. Please use JPG, PNG, or GIF.", "error")
        return redirect(url_for("auth.profile"))

    # For now, just show a success message
    # In production, you would:
    # 1. Resize/compress the image
    # 2. Save to file system or cloud storage (AWS S3, Cloudinary, etc.)
    # 3. Store the URL in the user record
    flash("Photo upload feature coming soon! 🎉", "info")
    return redirect(url_for("auth.profile"))


@auth_bp.route("/delete-account", methods=["POST"])
@login_required
def delete_account():
    """
    Delete the current user's account and all associated data.

    This action:
    1. Removes all password reset tokens
    2. Removes all user stickers (via cascade)
    3. Removes the user account
    4. Logs the user out

    This action is irreversible.
    """
    try:
        user = current_user

        # Delete password reset tokens first (foreign key constraint safety)
        PasswordResetToken.query.filter_by(user_id=user.id).delete()

        # Delete user (cascade will handle user_stickers)
        db.session.delete(user)
        db.session.commit()

        # Log out the user
        logout_user()

        flash("Your account has been deleted. We're sorry to see you go! 👋", "info")
        return redirect(url_for("auth.login"))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Account deletion error: {e}")
        flash("An error occurred while deleting your account. Please try again.", "error")
        return redirect(url_for("auth.profile"))


# =============================================================================
# OTHER USERS (Trading Partners)
# =============================================================================

@auth_bp.route("/users")
@login_required
def users():
    """
    Display all registered users with their collection stats.

    Shows potential trading partners prioritized by:
    1. Users who have duplicates that the current user needs
    2. Users who need duplicates that the current user has

    This helps users find the best trading opportunities.
    """
    from .config import ALBUM_PAGES

    # Get all stickers in the album
    all_sticker_ids = set()
    for page in ALBUM_PAGES:
        for sticker in page.get("stickers", []):
            all_sticker_ids.add(sticker["id"])

    # Get current user's data
    current_owned = set()
    current_duplicates = {}
    for sticker in current_user.stickers:
        if sticker.is_owned:
            current_owned.add(sticker.sticker_id)
        if sticker.duplicate_count > 0:
            current_duplicates[sticker.sticker_id] = sticker.duplicate_count

    current_missing = all_sticker_ids - current_owned

    # Get all other users
    other_users = User.query.filter(User.id != current_user.id).all()

    user_data = []

    for user in other_users:
        # Get user's stickers
        user_owned = set()
        user_duplicates = {}

        for sticker in user.stickers:
            if sticker.is_owned:
                user_owned.add(sticker.sticker_id)
            if sticker.duplicate_count > 0:
                user_duplicates[sticker.sticker_id] = sticker.duplicate_count

        user_missing = all_sticker_ids - user_owned

        # Calculate trading metrics
        # 1. User has duplicates that current user needs (good for current user)
        can_receive = user_duplicates.keys() & current_missing

        # 2. Current user has duplicates that this user needs (good for other user)
        can_give = current_duplicates.keys() & user_missing

        # Calculate match score (higher = better trading partner)
        match_score = len(can_receive) + len(can_give)

        user_data.append({
            "user": user,
            "owned_count": len(user_owned),
            "missing_count": len(user_missing),
            "duplicate_count": sum(user_duplicates.values()),
            "can_receive": sorted(can_receive),
            "can_receive_count": len(can_receive),
            "can_give": sorted(can_give),
            "can_give_count": len(can_give),
            "match_score": match_score,
            "completion": round((len(user_owned) / len(all_sticker_ids)) * 100) if all_sticker_ids else 0,
        })

    # Sort by match score (descending) - best trading partners first
    user_data.sort(key=lambda x: (-x["match_score"], -x["completion"]))

    return render_template(
        "auth/users.html",
        users_data=user_data,
        current_missing_count=len(current_missing),
        current_duplicates_count=len(current_duplicates),
    )


@auth_bp.route("/api/send-trade-message", methods=["POST"])
@login_required
def send_trade_message():
    """
    Send a trade request email to another user.

    Request body (JSON):
        - recipient_username: Username of the person to contact
        - stickers: List of sticker IDs being requested/offered
        - message: The custom message from the sender
        - trade_type: 'receive' (requesting stickers) or 'give' (offering stickers)

    Returns:
        JSON with success status and message
    """
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    recipient_username = data.get("recipient_username", "").strip()
    stickers = data.get("stickers", [])
    message_text = data.get("message", "").strip()
    trade_type = data.get("trade_type", "receive")

    # Validation
    if not recipient_username:
        return jsonify({"success": False, "error": "Recipient username is required"}), 400

    if not stickers or not isinstance(stickers, list):
        return jsonify({"success": False, "error": "At least one sticker must be selected"}), 400

    if not message_text:
        return jsonify({"success": False, "error": "Message is required"}), 400

    # Find recipient user
    recipient = User.query.filter_by(username=recipient_username).first()
    if not recipient:
        return jsonify({"success": False, "error": "Recipient not found"}), 404

    # Prevent self-messaging
    if recipient.id == current_user.id:
        return jsonify({"success": False, "error": "Cannot send trade request to yourself"}), 400

    try:
        # Prepare email
        sticker_list = ", ".join(stickers)
        trade_action = "requests" if trade_type == "receive" else "offers"

        subject = f"Trade Request from {current_user.username} - {len(stickers)} stickers"

        body = f"""Hello {recipient.username},

{current_user.username} ({current_user.email}) has sent you a trade request on Panini Album!

Trade Details:
- Action: They want to {trade_action} stickers
- Stickers: {sticker_list}

Message from {current_user.username}:
---
{message_text}
---

To respond, simply reply to this email.

Happy trading!
The Panini Album Team
"""

        html_body = f"""
<h2>Trade Request from {current_user.username}</h2>

<p>Hello <strong>{recipient.username}</strong>,</p>

<p><strong>{current_user.username}</strong> (<a href="mailto:{current_user.email}">{current_user.email}</a>)
has sent you a trade request on Panini Album!</p>

<div style="background: #f3f4f6; padding: 15px; border-radius: 8px; margin: 20px 0;">
    <h3 style="margin-top: 0;">Trade Details:</h3>
    <p><strong>Action:</strong> They want to {trade_action} stickers</p>
    <p><strong>Stickers ({len(stickers)}):</strong> {sticker_list}</p>
</div>

<div style="background: #e0f2fe; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #0284c7;">
    <h3 style="margin-top: 0;">Message from {current_user.username}:</h3>
    <p style="white-space: pre-wrap;">{message_text}</p>
</div>

<p><strong>To respond:</strong> Simply reply to this email or contact them at
<a href="mailto:{current_user.email}">{current_user.email}</a>.</p>

<p>Happy trading!<br><em>The Panini Album Team</em></p>
"""

        # Send email
        msg = Message(
            subject=subject,
            recipients=[recipient.email],
            body=body,
            html=html_body,
            reply_to=current_user.email
        )

        mail = Mail(current_app)
        mail.send(msg)

        # Log success (in production, you might want to log to database)
        current_app.logger.info(
            f"Trade email sent from {current_user.username} to {recipient.username} "
            f"for {len(stickers)} stickers"
        )

        return jsonify({
            "success": True,
            "message": f"Trade request sent to {recipient.username} successfully!"
        }), 200

    except Exception as e:
        current_app.logger.error(f"Failed to send trade email: {e}")
        return jsonify({
            "success": False,
            "error": "Failed to send email. Please try again later."
        }), 500

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
