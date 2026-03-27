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

    # Reliability stars for trade completion
    star_count = db.Column(db.Integer, default=0)

    # Profile photo URL
    photo_url = db.Column(db.String(255), nullable=True)

    # Relationships for messages
    sent_messages = db.relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    received_messages = db.relationship(
        "Message",
        foreign_keys="Message.recipient_id",
        back_populates="recipient",
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


class Message(db.Model):
    """
    Internal messaging between users.

    Stores conversations for the in-app messaging system.
    Messages can optionally be linked to a trade.
    """

    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)
    read_at = db.Column(db.DateTime, nullable=True)
    trade_id = db.Column(db.Integer, db.ForeignKey("trades.id"), nullable=True, index=True)

    # Relationships
    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    recipient = db.relationship("User", foreign_keys=[recipient_id], back_populates="received_messages")
    trade = db.relationship("Trade", back_populates="messages")

    def __init__(self, sender_id: int, recipient_id: int, content: str, trade_id: int = None):
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.content = content
        self.trade_id = trade_id

    def mark_as_read(self):
        """Mark message as read."""
        self.is_read = True
        self.read_at = datetime.now(timezone.utc)
        db.session.commit()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_username": self.sender.username if self.sender else None,
            "recipient_id": self.recipient_id,
            "content": self.content,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "is_read": self.is_read,
            "trade_id": self.trade_id,
        }

    def __repr__(self) -> str:
        return f"<Message from={self.sender_id} to={self.recipient_id}>"


class Trade(db.Model):
    """
    Tracks trade transactions between users.

    A trade represents an exchange of stickers between two users.
    Status: pending -> completed (both confirm) or cancelled
    """

    __tablename__ = "trades"

    id = db.Column(db.Integer, primary_key=True)
    initiator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(20), default="pending")  # pending, completed, cancelled
    stickers_offered = db.Column(db.Text)  # JSON list of sticker IDs
    stickers_requested = db.Column(db.Text)  # JSON list of sticker IDs
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    initiator = db.relationship("User", foreign_keys=[initiator_id])
    recipient = db.relationship("User", foreign_keys=[recipient_id])
    messages = db.relationship("Message", back_populates="trade", lazy="dynamic", cascade="all, delete-orphan")
    confirmations = db.relationship("TradeConfirmation", back_populates="trade", lazy="dynamic", cascade="all, delete-orphan")

    def __init__(self, initiator_id: int, recipient_id: int, stickers_offered: str = "[]", stickers_requested: str = "[]"):
        self.initiator_id = initiator_id
        self.recipient_id = recipient_id
        self.stickers_offered = stickers_offered
        self.stickers_requested = stickers_requested
        self.status = "pending"

    def is_fully_confirmed(self) -> bool:
        """Check if both users have confirmed the trade."""
        confirmed_users = {c.user_id for c in self.confirmations}
        return len(confirmed_users) == 2

    def complete_trade(self):
        """Mark trade as completed and award stars to both users."""
        if self.status == "completed":
            return

        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)

        # Award stars to both users
        from flask import current_app
        initiator = User.query.get(self.initiator_id)
        recipient = User.query.get(self.recipient_id)

        if initiator:
            initiator.star_count += 1
        if recipient:
            recipient.star_count += 1

        db.session.commit()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        import json
        return {
            "id": self.id,
            "initiator_id": self.initiator_id,
            "initiator_username": self.initiator.username if self.initiator else None,
            "recipient_id": self.recipient_id,
            "recipient_username": self.recipient.username if self.recipient else None,
            "status": self.status,
            "stickers_offered": json.loads(self.stickers_offered) if self.stickers_offered else [],
            "stickers_requested": json.loads(self.stickers_requested) if self.stickers_requested else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "is_fully_confirmed": self.is_fully_confirmed(),
        }

    def __repr__(self) -> str:
        return f"<Trade id={self.id} status={self.status}>"


class TradeConfirmation(db.Model):
    """
    Records when a user confirms a trade is complete.

    Both users must confirm for trade to be marked complete and stars awarded.
    """

    __tablename__ = "trade_confirmations"

    id = db.Column(db.Integer, primary_key=True)
    trade_id = db.Column(db.Integer, db.ForeignKey("trades.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    confirmed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    trade = db.relationship("Trade", back_populates="confirmations")
    user = db.relationship("User")

    # Unique constraint: each user can only confirm a trade once
    __table_args__ = (db.UniqueConstraint("trade_id", "user_id", name="unique_trade_confirmation"),)

    def __init__(self, trade_id: int, user_id: int):
        self.trade_id = trade_id
        self.user_id = user_id

    def __repr__(self) -> str:
        return f"<TradeConfirmation trade={self.trade_id} user={self.user_id}>"
