"""
Email Configuration Guide for Panini Album

This app uses Flask-Mail to send emails. By default, emails are printed to the console
instead of being sent (for development).

To enable real email sending, you have several options:

================================================================================
OPTION 1: Gmail (Good for testing, limited to 100 emails/day)
================================================================================

1. Go to your Google Account → Security → 2-Step Verification → App passwords
2. Generate an app password for "Mail"
3. Update __init__.py with these settings:

    app.config["MAIL_SUPPRESS_SEND"] = False
    app.config["MAIL_SERVER"] = "smtp.gmail.com"
    app.config["MAIL_PORT"] = 587
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = "your-email@gmail.com"
    app.config["MAIL_PASSWORD"] = "your-app-password"  # NOT your regular password!
    app.config["MAIL_DEFAULT_SENDER"] = ("Panini Album", "your-email@gmail.com")

================================================================================
OPTION 2: SendGrid (Recommended for production, 100 emails/day free)
================================================================================

1. Sign up at https://sendgrid.com
2. Create an API key (Settings → API Keys)
3. Update __init__.py with these settings:

    app.config["MAIL_SUPPRESS_SEND"] = False
    app.config["MAIL_SERVER"] = "smtp.sendgrid.net"
    app.config["MAIL_PORT"] = 587
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = "apikey"  # Literally "apikey"
    app.config["MAIL_PASSWORD"] = "SG.xxxxxxxx"  # Your SendGrid API key
    app.config["MAIL_DEFAULT_SENDER"] = ("Panini Album", "noreply@yourdomain.com")

================================================================================
OPTION 3: Mailgun (Good for production)
================================================================================

1. Sign up at https://www.mailgun.com
2. Get your SMTP credentials from the dashboard
3. Update __init__.py with these settings:

    app.config["MAIL_SUPPRESS_SEND"] = False
    app.config["MAIL_SERVER"] = "smtp.mailgun.org"
    app.config["MAIL_PORT"] = 587
    app.config["MAIL_USE_TLS"] = True
    app.config["MAIL_USERNAME"] = "postmaster@your-domain.mailgun.org"
    app.config["MAIL_PASSWORD"] = "your-mailgun-password"
    app.config["MAIL_DEFAULT_SENDER"] = ("Panini Album", "noreply@yourdomain.com")

================================================================================
OPTION 4: Keep Console Mode (Development Only)
================================================================================

If you want to keep testing without sending real emails, leave the settings as is.
Emails will be printed to your console/terminal where you ran the Flask app.

Look for output like:
    ============================
    TRADE REQUEST EMAIL
    ============================
    To: recipient@example.com
    Subject: Trade Request from username - 3 stickers
    ...

================================================================================
QUICK TEST
================================================================================

After updating the configuration:

1. Restart your Flask app (stop and run again: python app.py)
2. Go to "Other Users" page
3. Click on a trade card
4. Select stickers and send a trade request
5. Check:
   - Your email (if using real SMTP)
   - Or the console (if using development mode)

================================================================================
TROUBLESHOOTING
================================================================================

1. "Authentication failed":
   - Double-check your username/password
   - For Gmail, make sure you're using an App Password, not your regular password

2. "Connection refused":
   - Check your MAIL_SERVER and MAIL_PORT settings
   - Make sure your firewall allows outbound SMTP connections

3. Emails not arriving:
   - Check spam/junk folders
   - Verify the recipient email address is correct
   - Check console for error messages

4. "MAIL_SUPPRESS_SEND is True":
   - Set it to False to actually send emails
   - Keep it True for development/testing
"""
