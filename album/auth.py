"""
Authentication Blueprint

Handles user registration, login, logout, and password reset functionality.
All routes use CSRF protection (via Flask-WTF implicitly) and secure password hashing.
"""

from datetime import datetime, timezone
from functools import wraps
import json

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

from .models import db, User, PasswordResetToken, UserSticker, bcrypt, Message, Trade, TradeConfirmation
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
    Handle profile photo upload with cropping.

    Processes the uploaded image with PIL/Pillow to apply cropping
    based on user adjustments (drag position and zoom scale).
    Outputs a square 300x300px cropped image centered in a circle.
    """
    from PIL import Image
    import io

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

    # Get crop parameters from form
    crop_x = float(request.form.get("crop_x", 0))
    crop_y = float(request.form.get("crop_y", 0))
    crop_scale = float(request.form.get("crop_scale", 1))

    # Validate file size (max 2MB)
    photo.seek(0, 2)  # Seek to end of file
    file_size = photo.tell()
    photo.seek(0)  # Reset to beginning

    if file_size > 2 * 1024 * 1024:  # 2MB
        flash("File too large. Maximum size is 2MB.", "error")
        return redirect(url_for("auth.profile"))

    try:
        # Create uploads directory if it doesn't exist
        import os

        uploads_dir = os.path.join(current_app.root_path, "static", "uploads", "photos")
        os.makedirs(uploads_dir, exist_ok=True)

        # Open image with PIL
        image = Image.open(photo)

        # Convert to RGB if necessary (for PNG with transparency)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        # Image dimensions
        img_width, img_height = image.size

        # The crop parameters from frontend are percentages:
        # crop_x: 0-100 (background-position-x: 0 = left, 50 = center, 100 = right)
        # crop_y: 0-100 (background-position-y: 0 = top, 50 = center, 100 = bottom)
        # crop_scale: zoom percentage (50-500, where 100 = image fits frame)

        # Frame output size
        frame_size = 300

        # The frontend uses CSS background-size and background-position
        # background-size: Z% means the image is Z% of the container size
        # At 100%: image fills container exactly
        # At 200%: image is 2x container size (zoomed in 2x)
        # At 50%: image is 0.5x container size (zoomed out)

        # For the crop calculation:
        # At zoom 100%, we want to capture an area that when resized to 300px,
        # it fills the frame. For a square image, that's 300x300.
        # At zoom 200%, we want 2x zoom, so capture 150x150 and resize to 300.

        # Clamp zoom to minimum 100% (can't zoom out beyond fitting)
        zoom_pct = max(100, crop_scale)
        zoom_factor = zoom_pct / 100

        # Calculate how many pixels from the original image to capture
        # At 100% zoom: capture 300px (full frame size)
        # At 200% zoom: capture 150px (half frame size = 2x zoom)
        crop_pixels = int(frame_size / zoom_factor)

        # Convert percentage position to actual coordinates
        # CSS background-position works by aligning a point in the image
        # with a point in the container based on percentage
        # At 50%, the centers align
        # At 0%, the left/top edges align
        # At 100%, the right/bottom edges align

        # For cropping, we calculate the position of the crop box center
        # When background-position is 50%, crop is centered
        # When 0%, crop's left edge is at image's left edge
        # When 100%, crop's right edge is at image's right edge

        center_x = int((crop_x / 100) * img_width)
        center_y = int((crop_y / 100) * img_height)

        # Calculate crop box
        half_crop = crop_pixels // 2

        left = center_x - half_crop
        top = center_y - half_crop
        right = left + crop_pixels
        bottom = top + crop_pixels

        # Clamp to image bounds (this will shift the crop if near edges)
        if left < 0:
            left = 0
            right = min(crop_pixels, img_width)
        if top < 0:
            top = 0
            bottom = min(crop_pixels, img_height)
        if right > img_width:
            right = img_width
            left = max(0, right - crop_pixels)
        if bottom > img_height:
            bottom = img_height
            top = max(0, bottom - crop_pixels)

        # Ensure crop box is valid
        if right > img_width:
            right = img_width
            left = max(0, right - crop_size)
        if bottom > img_height:
            bottom = img_height
            top = max(0, bottom - crop_size)

        # Crop the image
        cropped_image = image.crop((left, top, right, bottom))

        # Resize to output size (300x300)
        if cropped_image.size != (frame_size, frame_size):
            cropped_image = cropped_image.resize((frame_size, frame_size), Image.Resampling.LANCZOS)

        # Generate unique filename: user_id_timestamp.jpg (always save as JPEG)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"user_{current_user.id}_{timestamp}.jpg"
        filepath = os.path.join(uploads_dir, filename)

        # Save the cropped image with quality optimization
        cropped_image.save(filepath, "JPEG", quality=90, optimize=True)

        # Delete old photo if exists (optional cleanup)
        if current_user.photo_url:
            old_filename = current_user.photo_url.split("/")[-1]
            old_filepath = os.path.join(uploads_dir, old_filename)
            if os.path.exists(old_filepath):
                try:
                    os.remove(old_filepath)
                except OSError:
                    pass  # Ignore errors deleting old file

        # Update user's photo_url in database
        photo_url = f"/static/uploads/photos/{filename}"
        current_user.photo_url = photo_url
        db.session.commit()

        flash("Profile photo updated successfully! 🎉", "success")

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Photo upload error: {e}")
        flash("Failed to upload photo. Please try again.", "error")

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


# =============================================================================
# MESSAGING SYSTEM
# =============================================================================

@auth_bp.route("/messages")
@login_required
def messages_inbox():
    """
    Display the user's message inbox.

    Shows all conversations grouped by other user.
    """
    # Get all messages where user is sender or recipient
    sent = current_user.sent_messages.order_by(Message.created_at.desc()).all()
    received = current_user.received_messages.order_by(Message.created_at.desc()).all()

    # Group messages by conversation partner
    conversations = {}

    for msg in sent + received:
        # Determine the other user in the conversation
        other_user_id = msg.recipient_id if msg.sender_id == current_user.id else msg.sender_id
        other_user = User.query.get(other_user_id)

        if not other_user:
            continue

        if other_user_id not in conversations:
            conversations[other_user_id] = {
                "user": other_user,
                "last_message": msg,
                "unread_count": 0,
                "message_count": 0
            }

        # Track unread messages
        if msg.recipient_id == current_user.id and not msg.is_read:
            conversations[other_user_id]["unread_count"] += 1

        conversations[other_user_id]["message_count"] += 1

        # Update last message if this is more recent
        if msg.created_at > conversations[other_user_id]["last_message"].created_at:
            conversations[other_user_id]["last_message"] = msg

    # Sort by last message time
    sorted_conversations = sorted(
        conversations.values(),
        key=lambda x: x["last_message"].created_at,
        reverse=True
    )

    return render_template("auth/messages.html", conversations=sorted_conversations)


@auth_bp.route("/messages/<username>")
@login_required
def messages_conversation(username):
    """
    Display conversation thread with a specific user.

    Shows all messages between current user and the specified user.
    """
    other_user = User.query.filter_by(username=username).first_or_404()

    if other_user.id == current_user.id:
        flash("Cannot message yourself.", "error")
        return redirect(url_for("auth.messages_inbox"))

    # Get all messages between these two users
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.recipient_id == other_user.id)) |
        ((Message.sender_id == other_user.id) & (Message.recipient_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()

    # Mark received messages as read
    for msg in messages:
        if msg.recipient_id == current_user.id and not msg.is_read:
            msg.mark_as_read()

    # Get active trade if any
    trade = Trade.query.filter(
        ((Trade.initiator_id == current_user.id) & (Trade.recipient_id == other_user.id)) |
        ((Trade.initiator_id == other_user.id) & (Trade.recipient_id == current_user.id)),
        Trade.status == "pending"
    ).order_by(Trade.created_at.desc()).first()

    # Check if current user has confirmed the trade
    trade_confirmed = False
    stickers_offered = []
    stickers_requested = []

    if trade:
        trade_confirmed = TradeConfirmation.query.filter_by(
            trade_id=trade.id,
            user_id=current_user.id
        ).first() is not None

        # Parse stickers JSON for template
        if trade.stickers_offered:
            stickers_offered = json.loads(trade.stickers_offered)
        if trade.stickers_requested:
            stickers_requested = json.loads(trade.stickers_requested)

    return render_template(
        "auth/conversation.html",
        other_user=other_user,
        messages=messages,
        trade=trade,
        trade_confirmed=trade_confirmed,
        now=datetime.now(timezone.utc),
        stickers_offered=stickers_offered,
        stickers_requested=stickers_requested
    )


@auth_bp.route("/api/messages/send", methods=["POST"])
@login_required
def send_message():
    """
    API endpoint to send a message to another user.

    Request body (JSON):
        - recipient_username: Username of recipient
        - content: Message content
        - trade_id: Optional trade ID to link message to
        - stickers: Optional list of stickers for trade context

    Returns:
        JSON with success status
    """
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "No data provided"}), 400

    recipient_username = data.get("recipient_username", "").strip()
    content = data.get("content", "").strip()
    trade_id = data.get("trade_id")
    stickers = data.get("stickers", [])
    trade_type = data.get("trade_type", "receive")

    # Validation
    if not recipient_username:
        return jsonify({"success": False, "error": "Recipient is required"}), 400

    if not content:
        return jsonify({"success": False, "error": "Message content is required"}), 400

    # Find recipient
    recipient = User.query.filter_by(username=recipient_username).first()
    if not recipient:
        return jsonify({"success": False, "error": "Recipient not found"}), 404

    if recipient.id == current_user.id:
        return jsonify({"success": False, "error": "Cannot send message to yourself"}), 400

    try:
        # If stickers provided and no trade_id, create a trade
        if stickers and not trade_id:
            import json
            if trade_type == "receive":
                # User wants stickers from recipient
                new_trade = Trade(
                    initiator_id=current_user.id,
                    recipient_id=recipient.id,
                    stickers_requested=json.dumps(stickers),
                    stickers_offered="[]"
                )
            else:
                # User offers stickers to recipient
                new_trade = Trade(
                    initiator_id=current_user.id,
                    recipient_id=recipient.id,
                    stickers_offered=json.dumps(stickers),
                    stickers_requested="[]"
                )
            db.session.add(new_trade)
            db.session.flush()  # Get trade.id
            trade_id = new_trade.id

        # Create message
        message = Message(
            sender_id=current_user.id,
            recipient_id=recipient.id,
            content=content,
            trade_id=trade_id
        )
        db.session.add(message)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Message sent successfully",
            "message_id": message.id,
            "trade_id": trade_id
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to send message: {e}")
        return jsonify({"success": False, "error": "Failed to send message"}), 500


@auth_bp.route("/api/messages/unread-count")
@login_required
def unread_count():
    """
    Get count of unread messages for current user.
    """
    count = current_user.received_messages.filter_by(is_read=False).count()
    return jsonify({"count": count})


@auth_bp.route("/api/messages/mark-read", methods=["POST"])
@login_required
def mark_messages_read():
    """
    Mark messages from a specific user as read.

    Request body (JSON):
        - sender_id: ID of sender whose messages to mark as read
    """
    data = request.get_json() or {}
    sender_id = data.get("sender_id")

    if not sender_id:
        return jsonify({"success": False, "error": "Sender ID required"}), 400

    try:
        messages = Message.query.filter_by(
            sender_id=sender_id,
            recipient_id=current_user.id,
            is_read=False
        ).all()

        for msg in messages:
            msg.is_read = True
            msg.read_at = datetime.now(timezone.utc)

        db.session.commit()
        return jsonify({"success": True, "marked_count": len(messages)})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to mark messages as read: {e}")
        return jsonify({"success": False, "error": "Failed to update messages"}), 500


@auth_bp.route("/api/trade/confirm", methods=["POST"])
@login_required
def confirm_trade():
    """
    Confirm a trade as complete.

    Both users must confirm before trade is marked complete and stars awarded.

    Request body (JSON):
        - trade_id: ID of trade to confirm
    """
    data = request.get_json() or {}
    trade_id = data.get("trade_id")

    if not trade_id:
        return jsonify({"success": False, "error": "Trade ID required"}), 400

    trade = Trade.query.get(trade_id)
    if not trade:
        return jsonify({"success": False, "error": "Trade not found"}), 404

    # Verify user is part of this trade
    if current_user.id not in [trade.initiator_id, trade.recipient_id]:
        return jsonify({"success": False, "error": "Not authorized"}), 403

    # Check if already confirmed
    existing = TradeConfirmation.query.filter_by(
        trade_id=trade_id,
        user_id=current_user.id
    ).first()

    if existing:
        return jsonify({"success": False, "error": "Already confirmed"}), 400

    try:
        # Create confirmation
        confirmation = TradeConfirmation(trade_id=trade_id, user_id=current_user.id)
        db.session.add(confirmation)
        db.session.flush()

        # Check if both users have confirmed
        if trade.is_fully_confirmed():
            trade.complete_trade()
            both_confirmed = True
        else:
            db.session.commit()
            both_confirmed = False

        return jsonify({
            "success": True,
            "both_confirmed": both_confirmed,
            "message": "Trade confirmed!" if both_confirmed else "Waiting for other user to confirm."
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to confirm trade: {e}")
        return jsonify({"success": False, "error": "Failed to confirm trade"}), 500

