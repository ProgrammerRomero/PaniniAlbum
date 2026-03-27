"""
Email Test Script for Panini Album

Run this to verify your email configuration is working:
    python test_email.py

Before running:
1. Update album/__init__.py with your SMTP settings
2. Set MAIL_SUPPRESS_SEND = False
3. Restart your Flask app
"""

import os
import sys

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from album import create_app
from flask_mail import Message, Mail

app = create_app()

def test_email():
    """Send a test email to verify configuration."""

    with app.app_context():
        mail = Mail(app)

        # Get config
        suppress = app.config.get("MAIL_SUPPRESS_SEND", True)
        server = app.config.get("MAIL_SERVER", None)
        sender = app.config.get("MAIL_DEFAULT_SENDER", "test@example.com")

        print("=" * 60)
        print("EMAIL CONFIGURATION TEST")
        print("=" * 60)
        print(f"\nMAIL_SUPPRESS_SEND: {suppress}")
        print(f"MAIL_SERVER: {server}")
        print(f"MAIL_DEFAULT_SENDER: {sender}")

        if suppress:
            print("\n⚠️  WARNING: MAIL_SUPPRESS_SEND is True")
            print("    Emails will only print to console, NOT actually sent!")
            print("\n    To send real emails:")
            print("    1. Set MAIL_SUPPRESS_SEND = False in album/__init__.py")
            print("    2. Configure SMTP settings (MAIL_SERVER, MAIL_PORT, etc.)")
            print("    3. Restart the app")

        # Ask for recipient
        recipient = input("\nEnter recipient email address: ").strip()

        if not recipient or "@" not in recipient:
            print("❌ Invalid email address!")
            return

        print(f"\n📧 Sending test email to: {recipient}")
        print("Please wait...")

        try:
            msg = Message(
                subject="Panini Album - Test Email",
                recipients=[recipient],
                body="""Hello!

This is a test email from your Panini Album application.

If you're seeing this email, your email configuration is working correctly!

Best regards,
Panini Album
""",
                html="""
<h2>Panini Album - Test Email</h2>

<p>Hello!</p>

<p>This is a test email from your <strong>Panini Album</strong> application.</p>

<p style="color: green; font-size: 18px;">✅ If you're seeing this email, your email configuration is working correctly!</p>

<p>Best regards,<br>
<em>Panini Album</em></p>
"""
            )

            mail.send(msg)

            if suppress:
                print("\n✅ Test email was printed to console (check above)")
                print("   Note: To actually SEND emails, set MAIL_SUPPRESS_SEND = False")
            else:
                print("\n✅ Test email SENT successfully!")
                print(f"   Check the inbox of: {recipient}")

        except Exception as e:
            print(f"\n❌ Failed to send email!")
            print(f"   Error: {e}")
            print("\n   Troubleshooting:")
            print("   - Check your SMTP settings in album/__init__.py")
            print("   - Verify username/password are correct")
            print("   - For Gmail, use App Password (not regular password)")
            print("   - Check firewall isn't blocking SMTP port")

if __name__ == "__main__":
    test_email()
