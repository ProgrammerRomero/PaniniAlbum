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

    # Profile information
    country = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(100), nullable=True)

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

    # Album version selection flag
    has_selected_version = db.Column(db.Boolean, default=False)

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

    def get_active_album_version(self):
        """Get currently selected album version."""
        active = UserAlbum.query.filter_by(
            user_id=self.id, is_active=True
        ).first()
        return active.version if active else None

    def has_album_version(self, version_id):
        """Check if user has a specific album version."""
        return UserAlbum.query.filter_by(
            user_id=self.id, album_version_id=version_id
        ).first() is not None


class AlbumVersion(db.Model):
    """
    Represents an album edition/version (Gold, Blue, Orange).
    """
    __tablename__ = "album_versions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(50), nullable=False)
    display_name = db.Column(db.String(100))
    theme_css_class = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)

    def __init__(self, code: str, name: str, display_name: str = None, theme_css_class: str = None):
        self.code = code
        self.name = name
        self.display_name = display_name or name
        self.theme_css_class = theme_css_class

    def __repr__(self) -> str:
        return f"<AlbumVersion {self.code}>"


class UserAlbum(db.Model):
    """
    Tracks which album versions a user has selected/collects.
    """
    __tablename__ = "user_albums"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    album_version_id = db.Column(db.Integer, db.ForeignKey("album_versions.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship("User", backref="albums")
    version = db.relationship("AlbumVersion")

    __table_args__ = (db.UniqueConstraint("user_id", "album_version_id", name="unique_user_album"),)

    def __init__(self, user_id: int, album_version_id: int, is_active: bool = False):
        self.user_id = user_id
        self.album_version_id = album_version_id
        self.is_active = is_active

    def __repr__(self) -> str:
        return f"<UserAlbum user={self.user_id} version={self.album_version_id}>"


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

    # Foreign key to album version
    album_version_id = db.Column(db.Integer, db.ForeignKey("album_versions.id"), nullable=False)

    # Unique constraint: each user can only have one entry per sticker per version
    __table_args__ = (db.UniqueConstraint("user_id", "sticker_id", "album_version_id", name="unique_user_sticker_version"),)

    def __init__(self, user_id: int, sticker_id: str, album_version_id: int, is_owned: bool = False, duplicate_count: int = 0):
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
        self.album_version_id = album_version_id
        self.is_owned = is_owned
        self.duplicate_count = duplicate_count

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "sticker_id": self.sticker_id,
            "album_version_id": self.album_version_id,
            "is_owned": self.is_owned,
            "duplicate_count": self.duplicate_count,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<UserSticker user={self.user_id} sticker={self.sticker_id}>"


class UserFeedback(db.Model):
    """
    User feedback/ratings system for peer-to-peer recognition.

    Users can give positive (👍) or negative (👎) feedback to other users
    for trading experiences. Each user can only give one feedback per
    target user, but can change their feedback from positive to negative
    or vice versa.

    Attributes:
        id: Primary key
        from_user_id: User giving the feedback
        to_user_id: User receiving the feedback
        feedback_type: 'good' (👍) or 'bad' (👎)
        created_at: When feedback was given
    """

    __tablename__ = "user_feedback"

    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    to_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    feedback_type = db.Column(db.String(10), nullable=False)  # 'good' or 'bad'
    comment = db.Column(db.Text, nullable=False)  # Required comment for feedback reason
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    from_user = db.relationship("User", foreign_keys=[from_user_id], backref="given_feedback")
    to_user = db.relationship("User", foreign_keys=[to_user_id], backref="received_feedback")

    # Unique constraint: one feedback per user pair
    __table_args__ = (db.UniqueConstraint("from_user_id", "to_user_id", name="unique_user_feedback_pair"),)

    def __init__(self, from_user_id: int, to_user_id: int, feedback_type: str, comment: str = ""):
        """
        Create a new feedback record.

        Args:
            from_user_id: ID of user giving feedback
            to_user_id: ID of user receiving feedback
            feedback_type: 'good' or 'bad'
            comment: Required comment explaining the feedback reason
        """
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.feedback_type = feedback_type
        self.comment = comment

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "from_user_id": self.from_user_id,
            "to_user_id": self.to_user_id,
            "feedback_type": self.feedback_type,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "from_username": self.from_user.username if self.from_user else None,
        }

    def __repr__(self) -> str:
        return f"<UserFeedback {self.from_user_id} -> {self.to_user_id}: {self.feedback_type}>"


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
        # Handle timezone-aware vs naive datetime comparison
        now = datetime.now(timezone.utc)
        if self.expires_at.tzinfo is None:
            # expires_at is naive, compare with naive now
            return now.replace(tzinfo=None) < self.expires_at
        return now < self.expires_at

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


class ConversationFavorite(db.Model):
    """
    Tracks favorited conversations at the conversation level.

    When a user favorites a conversation with another user, all messages
    in that conversation are effectively marked as favorite for that user.
    """

    __tablename__ = "conversation_favorites"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    other_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship("User", foreign_keys=[user_id], backref="favorite_conversations")
    other_user = db.relationship("User", foreign_keys=[other_user_id])

    # Unique constraint: each user can only favorite a conversation once
    __table_args__ = (db.UniqueConstraint("user_id", "other_user_id", name="unique_conversation_favorite"),)

    def __init__(self, user_id: int, other_user_id: int):
        self.user_id = user_id
        self.other_user_id = other_user_id

    def __repr__(self) -> str:
        return f"<ConversationFavorite user={self.user_id} other={self.other_user_id}>"


# Country name to ISO code mapping for flags
COUNTRY_CODES = {
    "Afghanistan": "AF",
    "Albania": "AL",
    "Algeria": "DZ",
    "Andorra": "AD",
    "Angola": "AO",
    "Antigua and Barbuda": "AG",
    "Argentina": "AR",
    "Armenia": "AM",
    "Australia": "AU",
    "Austria": "AT",
    "Azerbaijan": "AZ",
    "Bahamas": "BS",
    "Bahrain": "BH",
    "Bangladesh": "BD",
    "Barbados": "BB",
    "Belarus": "BY",
    "Belgium": "BE",
    "Belize": "BZ",
    "Benin": "BJ",
    "Bhutan": "BT",
    "Bolivia": "BO",
    "Bosnia and Herzegovina": "BA",
    "Botswana": "BW",
    "Brazil": "BR",
    "Brunei": "BN",
    "Bulgaria": "BG",
    "Burkina Faso": "BF",
    "Burundi": "BI",
    "Cambodia": "KH",
    "Cameroon": "CM",
    "Canada": "CA",
    "Cape Verde": "CV",
    "Central African Republic": "CF",
    "Chad": "TD",
    "Chile": "CL",
    "China": "CN",
    "Colombia": "CO",
    "Comoros": "KM",
    "Congo": "CG",
    "Costa Rica": "CR",
    "Croatia": "HR",
    "Cuba": "CU",
    "Cyprus": "CY",
    "Czech Republic": "CZ",
    "Denmark": "DK",
    "Djibouti": "DJ",
    "Dominica": "DM",
    "Dominican Republic": "DO",
    "Ecuador": "EC",
    "Egypt": "EG",
    "El Salvador": "SV",
    "Equatorial Guinea": "GQ",
    "Eritrea": "ER",
    "Estonia": "EE",
    "Eswatini": "SZ",
    "Ethiopia": "ET",
    "Fiji": "FJ",
    "Finland": "FI",
    "France": "FR",
    "Gabon": "GA",
    "Gambia": "GM",
    "Georgia": "GE",
    "Germany": "DE",
    "Ghana": "GH",
    "Greece": "GR",
    "Grenada": "GD",
    "Guatemala": "GT",
    "Guinea": "GN",
    "Guinea-Bissau": "GW",
    "Guyana": "GY",
    "Haiti": "HT",
    "Honduras": "HN",
    "Hungary": "HU",
    "Iceland": "IS",
    "India": "IN",
    "Indonesia": "ID",
    "Iran": "IR",
    "Iraq": "IQ",
    "Ireland": "IE",
    "Israel": "IL",
    "Italy": "IT",
    "Jamaica": "JM",
    "Japan": "JP",
    "Jordan": "JO",
    "Kazakhstan": "KZ",
    "Kenya": "KE",
    "Kiribati": "KI",
    "Kuwait": "KW",
    "Kyrgyzstan": "KG",
    "Laos": "LA",
    "Latvia": "LV",
    "Lebanon": "LB",
    "Lesotho": "LS",
    "Liberia": "LR",
    "Libya": "LY",
    "Liechtenstein": "LI",
    "Lithuania": "LT",
    "Luxembourg": "LU",
    "Madagascar": "MG",
    "Malawi": "MW",
    "Malaysia": "MY",
    "Maldives": "MV",
    "Mali": "ML",
    "Malta": "MT",
    "Marshall Islands": "MH",
    "Mauritania": "MR",
    "Mauritius": "MU",
    "Mexico": "MX",
    "Micronesia": "FM",
    "Moldova": "MD",
    "Monaco": "MC",
    "Mongolia": "MN",
    "Montenegro": "ME",
    "Morocco": "MA",
    "Mozambique": "MZ",
    "Myanmar": "MM",
    "Namibia": "NA",
    "Nauru": "NR",
    "Nepal": "NP",
    "Netherlands": "NL",
    "New Zealand": "NZ",
    "Nicaragua": "NI",
    "Niger": "NE",
    "Nigeria": "NG",
    "North Korea": "KP",
    "North Macedonia": "MK",
    "Norway": "NO",
    "Oman": "OM",
    "Pakistan": "PK",
    "Palau": "PW",
    "Panama": "PA",
    "Papua New Guinea": "PG",
    "Paraguay": "PY",
    "Peru": "PE",
    "Philippines": "PH",
    "Poland": "PL",
    "Portugal": "PT",
    "Qatar": "QA",
    "Romania": "RO",
    "Russia": "RU",
    "Rwanda": "RW",
    "Saint Kitts and Nevis": "KN",
    "Saint Lucia": "LC",
    "Saint Vincent and the Grenadines": "VC",
    "Samoa": "WS",
    "San Marino": "SM",
    "Sao Tome and Principe": "ST",
    "Saudi Arabia": "SA",
    "Senegal": "SN",
    "Serbia": "RS",
    "Seychelles": "SC",
    "Sierra Leone": "SL",
    "Singapore": "SG",
    "Slovakia": "SK",
    "Slovenia": "SI",
    "Solomon Islands": "SB",
    "Somalia": "SO",
    "South Africa": "ZA",
    "South Korea": "KR",
    "South Sudan": "SS",
    "Spain": "ES",
    "Sri Lanka": "LK",
    "Sudan": "SD",
    "Suriname": "SR",
    "Sweden": "SE",
    "Switzerland": "CH",
    "Syria": "SY",
    "Taiwan": "TW",
    "Tajikistan": "TJ",
    "Tanzania": "TZ",
    "Thailand": "TH",
    "Timor-Leste": "TL",
    "Togo": "TG",
    "Tonga": "TO",
    "Trinidad and Tobago": "TT",
    "Tunisia": "TN",
    "Turkey": "TR",
    "Turkmenistan": "TM",
    "Tuvalu": "TV",
    "Uganda": "UG",
    "Ukraine": "UA",
    "United Arab Emirates": "AE",
    "United Kingdom": "GB",
    "United States": "US",
    "Uruguay": "UY",
    "Uzbekistan": "UZ",
    "Vanuatu": "VU",
    "Vatican City": "VA",
    "Venezuela": "VE",
    "Vietnam": "VN",
    "Yemen": "YE",
    "Zambia": "ZM",
    "Zimbabwe": "ZW",
}

# List of countries for the profile country dropdown
COUNTRIES = [
    ("", "Select your country"),
    ("Afghanistan", "Afghanistan"),
    ("Albania", "Albania"),
    ("Algeria", "Algeria"),
    ("Andorra", "Andorra"),
    ("Angola", "Angola"),
    ("Antigua and Barbuda", "Antigua and Barbuda"),
    ("Argentina", "Argentina"),
    ("Armenia", "Armenia"),
    ("Australia", "Australia"),
    ("Austria", "Austria"),
    ("Azerbaijan", "Azerbaijan"),
    ("Bahamas", "Bahamas"),
    ("Bahrain", "Bahrain"),
    ("Bangladesh", "Bangladesh"),
    ("Barbados", "Barbados"),
    ("Belarus", "Belarus"),
    ("Belgium", "Belgium"),
    ("Belize", "Belize"),
    ("Benin", "Benin"),
    ("Bhutan", "Bhutan"),
    ("Bolivia", "Bolivia"),
    ("Bosnia and Herzegovina", "Bosnia and Herzegovina"),
    ("Botswana", "Botswana"),
    ("Brazil", "Brazil"),
    ("Brunei", "Brunei"),
    ("Bulgaria", "Bulgaria"),
    ("Burkina Faso", "Burkina Faso"),
    ("Burundi", "Burundi"),
    ("Cambodia", "Cambodia"),
    ("Cameroon", "Cameroon"),
    ("Canada", "Canada"),
    ("Cape Verde", "Cape Verde"),
    ("Central African Republic", "Central African Republic"),
    ("Chad", "Chad"),
    ("Chile", "Chile"),
    ("China", "China"),
    ("Colombia", "Colombia"),
    ("Comoros", "Comoros"),
    ("Congo", "Congo"),
    ("Costa Rica", "Costa Rica"),
    ("Croatia", "Croatia"),
    ("Cuba", "Cuba"),
    ("Cyprus", "Cyprus"),
    ("Czech Republic", "Czech Republic"),
    ("Denmark", "Denmark"),
    ("Djibouti", "Djibouti"),
    ("Dominica", "Dominica"),
    ("Dominican Republic", "Dominican Republic"),
    ("Ecuador", "Ecuador"),
    ("Egypt", "Egypt"),
    ("El Salvador", "El Salvador"),
    ("Equatorial Guinea", "Equatorial Guinea"),
    ("Eritrea", "Eritrea"),
    ("Estonia", "Estonia"),
    ("Eswatini", "Eswatini"),
    ("Ethiopia", "Ethiopia"),
    ("Fiji", "Fiji"),
    ("Finland", "Finland"),
    ("France", "France"),
    ("Gabon", "Gabon"),
    ("Gambia", "Gambia"),
    ("Georgia", "Georgia"),
    ("Germany", "Germany"),
    ("Ghana", "Ghana"),
    ("Greece", "Greece"),
    ("Grenada", "Grenada"),
    ("Guatemala", "Guatemala"),
    ("Guinea", "Guinea"),
    ("Guinea-Bissau", "Guinea-Bissau"),
    ("Guyana", "Guyana"),
    ("Haiti", "Haiti"),
    ("Honduras", "Honduras"),
    ("Hungary", "Hungary"),
    ("Iceland", "Iceland"),
    ("India", "India"),
    ("Indonesia", "Indonesia"),
    ("Iran", "Iran"),
    ("Iraq", "Iraq"),
    ("Ireland", "Ireland"),
    ("Israel", "Israel"),
    ("Italy", "Italy"),
    ("Jamaica", "Jamaica"),
    ("Japan", "Japan"),
    ("Jordan", "Jordan"),
    ("Kazakhstan", "Kazakhstan"),
    ("Kenya", "Kenya"),
    ("Kiribati", "Kiribati"),
    ("Kuwait", "Kuwait"),
    ("Kyrgyzstan", "Kyrgyzstan"),
    ("Laos", "Laos"),
    ("Latvia", "Latvia"),
    ("Lebanon", "Lebanon"),
    ("Lesotho", "Lesotho"),
    ("Liberia", "Liberia"),
    ("Libya", "Libya"),
    ("Liechtenstein", "Liechtenstein"),
    ("Lithuania", "Lithuania"),
    ("Luxembourg", "Luxembourg"),
    ("Madagascar", "Madagascar"),
    ("Malawi", "Malawi"),
    ("Malaysia", "Malaysia"),
    ("Maldives", "Maldives"),
    ("Mali", "Mali"),
    ("Malta", "Malta"),
    ("Marshall Islands", "Marshall Islands"),
    ("Mauritania", "Mauritania"),
    ("Mauritius", "Mauritius"),
    ("Mexico", "Mexico"),
    ("Micronesia", "Micronesia"),
    ("Moldova", "Moldova"),
    ("Monaco", "Monaco"),
    ("Mongolia", "Mongolia"),
    ("Montenegro", "Montenegro"),
    ("Morocco", "Morocco"),
    ("Mozambique", "Mozambique"),
    ("Myanmar", "Myanmar"),
    ("Namibia", "Namibia"),
    ("Nauru", "Nauru"),
    ("Nepal", "Nepal"),
    ("Netherlands", "Netherlands"),
    ("New Zealand", "New Zealand"),
    ("Nicaragua", "Nicaragua"),
    ("Niger", "Niger"),
    ("Nigeria", "Nigeria"),
    ("North Korea", "North Korea"),
    ("North Macedonia", "North Macedonia"),
    ("Norway", "Norway"),
    ("Oman", "Oman"),
    ("Pakistan", "Pakistan"),
    ("Palau", "Palau"),
    ("Panama", "Panama"),
    ("Papua New Guinea", "Papua New Guinea"),
    ("Paraguay", "Paraguay"),
    ("Peru", "Peru"),
    ("Philippines", "Philippines"),
    ("Poland", "Poland"),
    ("Portugal", "Portugal"),
    ("Qatar", "Qatar"),
    ("Romania", "Romania"),
    ("Russia", "Russia"),
    ("Rwanda", "Rwanda"),
    ("Saint Kitts and Nevis", "Saint Kitts and Nevis"),
    ("Saint Lucia", "Saint Lucia"),
    ("Saint Vincent and the Grenadines", "Saint Vincent and the Grenadines"),
    ("Samoa", "Samoa"),
    ("San Marino", "San Marino"),
    ("Sao Tome and Principe", "Sao Tome and Principe"),
    ("Saudi Arabia", "Saudi Arabia"),
    ("Senegal", "Senegal"),
    ("Serbia", "Serbia"),
    ("Seychelles", "Seychelles"),
    ("Sierra Leone", "Sierra Leone"),
    ("Singapore", "Singapore"),
    ("Slovakia", "Slovakia"),
    ("Slovenia", "Slovenia"),
    ("Solomon Islands", "Solomon Islands"),
    ("Somalia", "Somalia"),
    ("South Africa", "South Africa"),
    ("South Korea", "South Korea"),
    ("South Sudan", "South Sudan"),
    ("Spain", "Spain"),
    ("Sri Lanka", "Sri Lanka"),
    ("Sudan", "Sudan"),
    ("Suriname", "Suriname"),
    ("Sweden", "Sweden"),
    ("Switzerland", "Switzerland"),
    ("Syria", "Syria"),
    ("Taiwan", "Taiwan"),
    ("Tajikistan", "Tajikistan"),
    ("Tanzania", "Tanzania"),
    ("Thailand", "Thailand"),
    ("Timor-Leste", "Timor-Leste"),
    ("Togo", "Togo"),
    ("Tonga", "Tonga"),
    ("Trinidad and Tobago", "Trinidad and Tobago"),
    ("Tunisia", "Tunisia"),
    ("Turkey", "Turkey"),
    ("Turkmenistan", "Turkmenistan"),
    ("Tuvalu", "Tuvalu"),
    ("Uganda", "Uganda"),
    ("Ukraine", "Ukraine"),
    ("United Arab Emirates", "United Arab Emirates"),
    ("United Kingdom", "United Kingdom"),
    ("United States", "United States"),
    ("Uruguay", "Uruguay"),
    ("Uzbekistan", "Uzbekistan"),
    ("Vanuatu", "Vanuatu"),
    ("Vatican City", "Vatican City"),
    ("Venezuela", "Venezuela"),
    ("Vietnam", "Vietnam"),
    ("Yemen", "Yemen"),
    ("Zambia", "Zambia"),
    ("Zimbabwe", "Zimbabwe"),
]
