"""
Database Models for Panini Album App

This module defines the SQLAlchemy models for user accounts, sticker collections,
and password reset tokens.
"""

from datetime import datetime, timedelta, timezone
import secrets

from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import UserMixin

# Initialize extensions (will be bound to app in __init__.py)
db = SQLAlchemy()
bcrypt = Bcrypt()


class User(UserMixin, db.Model):
    """
    User account model.

    Stores user credentials and profile information.
    Passwords are hashed using bcrypt for security.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    # Relationship to user's stickers
    stickers = db.relationship(
        "UserSticker",
        back_populates="user",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )

    def __init__(self, username: str, email: str, password: str):
        """
        Create a new user with hashed password.

        Args:
            username: Unique username (3-80 characters)
            email: Unique email address
            password: Plain text password (will be hashed)
        """
        self.username = username
        self.email = email
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        """
        Verify a password against the stored hash.

        Args:
            password: Plain text password to verify

        Returns:
            True if password matches, False otherwise
        """
        return bcrypt.check_password_hash(self.password_hash, password)

    def update_last_login(self):
        """Update the last login timestamp to current time."""
        self.last_login = datetime.now(timezone.utc)
        db.session.commit()

    def get_id(self) -> str:
        """Required by Flask-Login. Returns user ID as string."""
        return str(self.id)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class UserSticker(db.Model):
    """
    Tracks which stickers a user owns and how many duplicates they have.

    This replaces the localStorage functionality with database persistence,
    allowing users to access their collection from any device.
    """

    __tablename__ = "user_stickers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    sticker_id = db.Column(db.String(20), nullable=False, index=True)
    is_owned = db.Column(db.Boolean, default=False)
    duplicate_count = db.Column(db.Integer, default=0)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationship to user
    user = db.relationship("User", back_populates="stickers")

    # Unique constraint: each user can only have one entry per sticker
    __table_args__ = (db.UniqueConstraint("user_id", "sticker_id", name="unique_user_sticker"),)

    def __init__(self, user_id: int, sticker_id: str, is_owned: bool = False, duplicate_count: int = 0):
        """
        Create a new user sticker record.

        Args:
            user_id: ID of the owning user
            sticker_id: Sticker identifier (e.g., "ARG-1")
            is_owned: Whether the user owns this sticker
            duplicate_count: Number of duplicate copies (0 or more)
        """
        self.user_id = user_id
        self.sticker_id = sticker_id
        self.is_owned = is_owned
        self.duplicate_count = duplicate_count

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "sticker_id": self.sticker_id,
            "is_owned": self.is_owned,
            "duplicate_count": self.duplicate_count,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<UserSticker user={self.user_id} sticker={self.sticker_id}>"


class PasswordResetToken(db.Model):
    """
    Password reset token for "Forgot Password" functionality.

    Tokens are cryptographically secure random strings that expire after
    a set duration (default 1 hour). Each token can only be used once.
    """

    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    token = db.Column(db.String(100), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __init__(self, user_id: int, expires_hours: int = 1):
        """
        Create a new password reset token.

        Args:
            user_id: ID of the user requesting password reset
            expires_hours: Token validity duration in hours (default: 1)
        """
        self.user_id = user_id
        # Generate cryptographically secure random token
        self.token = secrets.token_urlsafe(32)
        self.expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)

    def is_valid(self) -> bool:
        """
        Check if token is still valid (not expired and not used).

        Returns:
            True if token can be used for password reset
        """
        if self.used:
            return False
        return datetime.now(timezone.utc) < self.expires_at

    def mark_as_used(self):
        """Mark token as used after successful password reset."""
        self.used = True
        db.session.commit()

    @classmethod
    def cleanup_expired(cls):
        """Remove expired tokens from database (maintenance)."""
        expired = cls.query.filter(
            cls.expires_at < datetime.now(timezone.utc),
            cls.used == False
        ).all()
        for token in expired:
            db.session.delete(token)
        db.session.commit()

    def __repr__(self) -> str:
        return f"<PasswordResetToken user={self.user_id} valid={self.is_valid()}>"
