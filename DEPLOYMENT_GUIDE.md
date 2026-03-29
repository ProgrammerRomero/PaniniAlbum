# Panini Album - Deployment Guide

## Table of Contents
1. [Recommended Hosting Options](#1-recommended-hosting-options)
2. [Architecture Overview](#2-architecture-overview)
3. [Setting Up Production Environment](#3-setting-up-production-environment)
4. [Setting Up UAT Environment](#4-setting-up-uat-environment)
5. [Database Setup](#5-database-setup)
6. [Environment Variables](#6-environment-variables)
7. [Deployment Workflow](#7-deployment-workflow)
8. [Daily Maintenance](#8-daily-maintenance)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Recommended Hosting Options

### Top Recommendation: Railway
**Why:**
- Generous free tier ($5 credit monthly = ~500 hours)
- Easy GitHub integration
- Automatic deployments
- Built-in PostgreSQL
- Simple environment variables management

**Pricing:**
- Free: 500 hours/month (good for testing)
- Starter: $5/month (sufficient for small apps)

### Alternative: Render
**Why:**
- Generous free tier
- Automatic deploys from Git
- Free PostgreSQL (expires after 90 days of inactivity)

### Alternative: Fly.io
**Why:**
- Very fast global deployment
- Free allowances generous for small apps
- Requires more technical setup

### Alternative: PythonAnywhere
**Why:**
- Specifically designed for Python
- Very beginner-friendly
- Free tier available
- Good for learning

---

## 2. Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐
│   UAT/Branch    │     │   Production    │
│   (staging)     │     │   (main)        │
│   railway-uat   │     │   railway-prod  │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
              ┌──────▼──────┐
              │   GitHub    │
              │  Repository │
              └─────────────┘
```

---

## 3. Setting Up Production Environment

### Step 3.1: Prepare Your Code for Production

Create a `requirements.txt` if you don't have one:
```bash
pip freeze > requirements.txt
```

Ensure these are in your requirements.txt:
```
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-Login==0.6.3
Flask-Mail==0.9.1
Flask-WTF==1.2.1
WTForms==3.1.1
Werkzeug==3.0.1
psycopg2-binary==2.9.9
Pillow==10.1.0
gunicorn==21.2.0
```

### Step 3.2: Create Required Files

**Create `Procfile`** (no extension):
```
web: gunicorn "album:create_app()"
```

**Create `runtime.txt`**:
```
python-3.12.0
```

**Update `album/__init__.py`** to use environment database:
```python
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

    # Database - use PostgreSQL in production, SQLite in development
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        # Railway/Render use postgres:// but SQLAlchemy requires postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///panini_album.db'

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Email configuration
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER')

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    mail.init_app(app)

    # Register blueprints
    from album.auth import auth_bp
    from album.album import album_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(album_bp)

    # Create tables
    with app.app_context():
        db.create_all()

    return app
```

### Step 3.3: Create Production Branch

```bash
# Ensure you're on main branch and everything is committed
git checkout main
git pull origin main

# Create production-ready branch (if not exists)
git checkout -b production

# Push to GitHub
git push -u origin production
```

### Step 3.4: Deploy to Railway (Production)

1. **Sign up at** [railway.app](https://railway.app) with GitHub

2. **Create New Project:**
   - Click "New Project"
   - Choose "Deploy from GitHub repo"
   - Select your panini_album repository
   - Select the `production` branch

3. **Add PostgreSQL Database:**
   - Click "New"
   - Select "Database" → "Add PostgreSQL"
   - This automatically creates a DATABASE_URL environment variable

4. **Configure Environment Variables:**
   Go to your service → Variables tab:
   ```
   SECRET_KEY=your-very-secret-random-key-here
   FLASK_ENV=production
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=true
   MAIL_USERNAME=your-email@gmail.com
   MAIL_PASSWORD=your-app-password
   MAIL_DEFAULT_SENDER=your-email@gmail.com
   ```

5. **Generate Secret Key:**
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

6. **Deploy:**
   - Railway auto-deploys on git push
   - Your app will be available at: `https://your-app-name.up.railway.app`

---

## 4. Setting Up UAT Environment

### Step 4.1: Create UAT Branch

```bash
# From main branch
git checkout main
git pull origin main

# Create UAT branch
git checkout -b uat

# Push to GitHub
git push -u origin uat
```

### Step 4.2: Deploy UAT to Railway

1. **Create second project in Railway:**
   - Same process as production
   - Select `uat` branch

2. **Add PostgreSQL Database** (separate from production)

3. **Set Environment Variables** (similar to prod, but):
   ```
   SECRET_KEY=different-secret-key-for-uat
   FLASK_ENV=development
   ```

4. **UAT URL will be:** `https://your-app-name-uat.up.railway.app`

### Step 4.3: Branch Protection Rules (GitHub)

1. Go to Repository → Settings → Branches
2. Add rule for `production`:
   - Require pull request reviews before merging
   - Require status checks to pass
   - Restrict pushes to administrators only
3. Add rule for `main`:
   - Require pull request reviews

---

## 5. Database Setup

### Step 5.1: Database Migration Strategy

**Option A: Auto-create (Simple but risky)**
- `db.create_all()` runs on startup
- Good for initial setup

**Option B: Flask-Migrate (Recommended)**

Install:
```bash
pip install Flask-Migrate
```

Update `__init__.py`:
```python
from flask_migrate import Migrate

migrate = Migrate(app, db)
```

Commands:
```bash
# Initialize migrations
flask db init

# Create migration
flask db migrate -m "Initial migration"

# Apply to database
flask db upgrade
```

### Step 5.2: Backup Database (Important!)

**Daily Backup Script** (`backup.sh`):
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump $DATABASE_URL > backup_$DATE.sql
```

---

## 6. Environment Variables

### Production Variables
| Variable | Description | Example |
|----------|-------------|---------|
| SECRET_KEY | Flask secret key | `d8b9c2e7f4a1...` |
| DATABASE_URL | PostgreSQL connection | `postgresql://...` |
| FLASK_ENV | Environment mode | `production` |
| MAIL_SERVER | SMTP server | `smtp.gmail.com` |
| MAIL_USERNAME | Email address | `yourapp@gmail.com` |
| MAIL_PASSWORD | App password | `abcd efgh ijkl mnop` |

### UAT Variables
| Variable | Description | Example |
|----------|-------------|---------|
| SECRET_KEY | Different from prod | `uat-secret-key...` |
| DATABASE_URL | Separate DB | `postgresql://...` |
| FLASK_ENV | Development mode | `development` |

---

## 7. Deployment Workflow

### Step 7.1: Feature Development Workflow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Feature   │ →  │     UAT     │ →  │   Review    │ →  │  Production │
│   Branch    │    │   Deploy    │    │   & Test    │    │   Deploy    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      │                  │                  │                  │
   git push          Auto-deploy        Manual check      Auto-deploy
```

### Step 7.2: Step-by-Step Deployment Process

**1. Create Feature Branch:**
```bash
git checkout main
git pull origin main
git checkout -b feature/new-search-functionality
```

**2. Develop & Test Locally:**
```bash
# Make changes
# Test locally
python run.py
```

**3. Commit & Push:**
```bash
git add .
git commit -m "Add search functionality for traders"
git push origin feature/new-search-functionality
```

**4. Deploy to UAT:**
```bash
# Create Pull Request: feature → uat
git checkout uat
git pull origin uat
git merge feature/new-search-functionality
git push origin uat
```
- Railway auto-deploys UAT
- Test at: `https://your-uat-url.up.railway.app`

**5. Test in UAT:**
- [ ] All features work
- [ ] No console errors
- [ ] Mobile responsive
- [ ] Database operations work
- [ ] Email sending works

**6. Deploy to Production:**
```bash
# Create Pull Request: uat → production
git checkout production
git pull origin production
git merge uat
git push origin production
```
- Railway auto-deploys production
- Monitor for errors

---

## 8. Daily Maintenance

### Step 8.1: Daily Checklist

**Every Morning (5 minutes):**
- [ ] Check Railway dashboard for errors
- [ ] Verify website loads
- [ ] Check database connections
- [ ] Review any user reports

**Weekly (15 minutes):**
- [ ] Check disk usage
- [ ] Review logs for errors
- [ ] Backup database
- [ ] Check for security updates

**Monthly (30 minutes):**
- [ ] Update dependencies
- [ ] Review and rotate logs
- [ ] Performance check
- [ ] Security review

### Step 8.2: Monitoring Commands

**Check Railway Logs:**
- Railway Dashboard → Service → Deployments → Logs

**Local Log Analysis:**
```bash
# If you have logs saved
tail -f app.log | grep ERROR
```

### Step 8.3: Updating Dependencies

```bash
# Update requirements
pip list --outdated
pip install --upgrade Flask
pip freeze > requirements.txt

# Test locally
# Commit changes
git add requirements.txt
git commit -m "Update Flask to latest version"
git push origin main
```

### Step 8.4: Database Maintenance

**Check Database Size:**
```sql
-- Connect to Railway database
SELECT pg_size_pretty(pg_database_size('railway'));
```

**Clean Old Data (if needed):**
```sql
-- Example: Delete old password reset tokens
DELETE FROM password_reset_token WHERE created_at < NOW() - INTERVAL '7 days';
```

---

## 9. Troubleshooting

### Problem: App Won't Start

**Check:**
1. Railway logs for error messages
2. Environment variables set correctly
3. Procfile syntax correct
4. Database URL accessible

### Problem: Database Connection Failed

**Solution:**
```bash
# Check if DATABASE_URL is set
railway variables --service your-service

# Test connection locally
psql $DATABASE_URL
```

### Problem: Static Files Not Loading

**Solution:**
Add to Flask app:
```python
from flask import send_from_directory

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)
```

### Problem: Memory Issues

**Solution:**
- Reduce worker count in Procfile:
  ```
  web: gunicorn --workers 2 "album:create_app()"
  ```
- Use connection pooling for database

### Emergency Rollback

If production breaks:
```bash
# In Railway dashboard
# Go to Deployments
# Click on previous working deployment
# Click "Redeploy"

# Or via Git
git revert HEAD
git push origin production
```

---

## Quick Reference Commands

```bash
# Development
git checkout -b feature/name
python run.py

# Deploy to UAT
git checkout uat
git merge feature/name
git push origin uat

# Deploy to Production
git checkout production
git merge uat
git push origin production

# Logs
railway logs

# Database backup
pg_dump $DATABASE_URL > backup.sql

# Restore database
psql $DATABASE_URL < backup.sql
```

---

## Cost Estimates

| Service | Free Tier | Paid Tier (Small) |
|---------|-----------|-------------------|
| Railway | $5 credit/mo | $5-10/mo |
| PostgreSQL | Included | Included |
| Domain (optional) | - | $10-15/year |
| **Total** | **Free** | **~$10/mo** |

---

## Security Checklist

- [ ] Use strong SECRET_KEY
- [ ] Enable HTTPS only (Railway does this automatically)
- [ ] Set secure session cookies
- [ ] Use app-specific email passwords
- [ ] Never commit .env files
- [ ] Enable 2FA on Railway
- [ ] Regular dependency updates

---

**Document Created:** 2026-03-29
**Last Updated:** 2026-03-29
**Version:** 1.0
