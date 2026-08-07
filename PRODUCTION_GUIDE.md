# Production Deployment Guide

## 🚀 Quick start for Production

### 1. Environment variables

```bash
# Copy the example env file
cp .env.example .env

# MUST change these keys!
DJANGO_SECRET_KEY=your-super-secure-django-secret-key-256-chars
JWT_SECRET_KEY=your-super-secure-jwt-secret-key-256-chars
```

### 2. Production security

```bash
# Enable all security settings
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
SECURE_HSTS_SECONDS=31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=true
```

### 3. Database with SSL

```bash
# For production, use PostgreSQL with SSL
DB_SSL_MODE=require
DB_SSL_CA=/path/to/ca-cert.pem
DB_SSL_CERT=/path/to/client-cert.pem
DB_SSL_KEY=/path/to/client-key.pem
DATABASE_URL=postgresql://user:pass@host:5432/dbname?sslmode=require
```

### 4. Running in Production

```bash
# Install dependencies
uv sync

# Migrations
make migrate

# Create a superuser
make createsuperuser

# Run with Gunicorn
make run.server.prod
```

## 🔒 Critical security settings

### SSL/HTTPS
```bash
# Required for production!
SECURE_SSL_REDIRECT=true
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

### Content Security Policy
```python
# Add to settings.py
MIDDLEWARE += [
    'django.middleware.security.SecurityMiddleware',
]

# CSP settings
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
```

### Rate Limiting
```bash
AXES_ENABLED=true
AXES_FAILURE_LIMIT=5
AXES_COOLOFF_TIME=1  # hour
```

## 📊 Monitoring and logging

### Sentry (errors)
```bash
USE_SENTRY=true
SENTRY_DSN=your-sentry-dsn
```

### Logging
```bash
LOG_LEVEL=INFO
LOG_FILE=/var/log/app.log
```

### Performance monitoring
```bash
USE_SILK=true  # Enable Django Silk for profiling
```

## 🗄️ Database setup

### PostgreSQL configuration
```python
# Already configured in database.py:
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "OPTIONS": {
            'sslmode': 'require',
            'connect_timeout': 10,
        },
        'CONN_MAX_AGE': 600,  # Connection pooling
    }
}
```

### Performance tuning
```sql
-- PostgreSQL settings for production
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
work_mem = 4MB
```

## 🔄 CI/CD Pipeline

### GitHub Actions example
```yaml
name: Django CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.11'
        
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        
    - name: Run migrations
      run: python manage.py migrate
      
    - name: Run tests
      run: |
        python manage.py test
        python manage.py check --deploy
```

## 📈 Scaling

### Horizontal scaling (multiple servers)
```bash
# Use a shared database and Redis
REDIS_HOST=shared-redis-host
DATABASE_URL=postgresql://user:pass@shared-db:5432/dbname
```

### Load Balancer (Nginx)
```nginx
upstream django_app {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
}

server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://django_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 🛠️ Troubleshooting

### Security checks
```bash
# Run Django check with production flags
python manage.py check --deploy

# Check SSL settings
python manage.py check --deploy --settings=api.config.settings.production
```

### Error logs
```bash
# Check logs for security issues
grep -i "security\|warning\|error" /var/log/app.log
```

### Database connection
```bash
# Verify DB connectivity
python manage.py dbshell
```

## ✅ Pre-production checklist

- [ ] Change all default secret keys
- [ ] Configure HTTPS/SSL certificates
- [ ] Enable SECURE_* settings
- [ ] Configure SSL for the database
- [ ] Set up monitoring (Sentry)
- [ ] Create a superuser
- [ ] Run a security audit (`python manage.py check --deploy`)
- [ ] Set up database backups
- [ ] Configure logging
- [ ] Test all API endpoints
- [ ] Set up a CI/CD pipeline

---

**Important**: Never run the app in production with default security settings!

