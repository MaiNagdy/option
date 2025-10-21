# Production Deployment Guide

## 🚀 Quick Start - Production Deployment

### Option 1: Docker Deployment (Recommended)

1. **Clone and setup**
```bash
git clone <your-repo>
cd option1
cp .env.example .env
```

2. **Configure environment**
Edit `.env` file with your production values:
```env
APP_ENV=production
SECRET_KEY=your-super-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

3. **Build and run**
```bash
docker-compose up -d
```

4. **Access your application**
- HTTP: `http://yourdomain.com`
- HTTPS: `https://yourdomain.com` (after SSL setup)

### Option 2: Direct Python Deployment

1. **Install dependencies**
```bash
pip install -r requirements.txt
```

2. **Set environment variables**
```bash
export APP_ENV=production
export HOST=0.0.0.0
export PORT=8000
export SECRET_KEY=your-secret-key
```

3. **Run the application**
```bash
python app.py
```

### Option 3: Cloud Deployment

#### Deploy to AWS EC2

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Clone and deploy
git clone <your-repo>
cd option1
docker-compose up -d
```

#### Deploy to Heroku

```bash
# Install Heroku CLI
heroku login
heroku create your-app-name

# Set environment variables
heroku config:set APP_ENV=production
heroku config:set SECRET_KEY=your-secret-key

# Deploy
git push heroku main
```

#### Deploy to DigitalOcean

```bash
# Use DigitalOcean App Platform
# 1. Connect your GitHub repo
# 2. Select Dockerfile deployment
# 3. Set environment variables in dashboard
# 4. Deploy
```

#### Deploy to Railway.app

```bash
# Simplest deployment
railway login
railway init
railway up
```

## 🔒 Production Checklist

### Security
- [ ] Change SECRET_KEY to a strong random value
- [ ] Set ALLOWED_HOSTS to your domain(s)
- [ ] Configure CORS_ORIGINS properly
- [ ] Enable HTTPS/SSL
- [ ] Set SESSION_COOKIE_SECURE=True
- [ ] Configure firewall rules
- [ ] Enable rate limiting

### Database
- [ ] Set up PostgreSQL (recommended for production)
- [ ] Configure DATABASE_URL
- [ ] Run database migrations
- [ ] Set up automated backups

### Performance
- [ ] Enable Redis for session storage
- [ ] Configure CDN for static files
- [ ] Set up caching
- [ ] Use multiple workers (uvicorn)

### Monitoring
- [ ] Set up error tracking (Sentry)
- [ ] Configure logging
- [ ] Set up uptime monitoring
- [ ] Enable health checks

### Features
- [ ] Configure Stripe for payments (optional)
- [ ] Set up email notifications (optional)
- [ ] Configure API keys for financial data

## 🌐 Domain & SSL Setup

### 1. Point your domain to your server
```
A Record: @ -> Your Server IP
A Record: www -> Your Server IP
```

### 2. Get free SSL certificate (Let's Encrypt)
```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

### 3. Auto-renew SSL
```bash
sudo certbot renew --dry-run
```

## 📊 Scaling

### Horizontal Scaling
```yaml
# docker-compose.yml
services:
  app:
    deploy:
      replicas: 4
```

### Load Balancing
Use Nginx or cloud load balancer to distribute traffic across multiple instances.

## 🔧 Environment Variables

### Required
- `APP_ENV`: Set to "production"
- `SECRET_KEY`: Strong random secret
- `HOST`: 0.0.0.0 for production
- `PORT`: 8000 (or your preferred port)

### Optional but Recommended
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `STRIPE_SECRET_KEY`: For payment processing
- `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`: For emails

## 📈 Monitoring Endpoints

- Health Check: `GET /`
- API Docs: `GET /api/docs` (disabled in production by default)

## 🆘 Troubleshooting

### App won't start
```bash
# Check logs
docker-compose logs app

# Check environment
docker-compose exec app env
```

### Can't access from internet
```bash
# Check firewall
sudo ufw status
sudo ufw allow 80
sudo ufw allow 443
```

### Performance issues
```bash
# Monitor resources
docker stats

# Scale up workers
# Edit docker-compose.yml or app.py workers setting
```

## 📱 Full Features Enabled

All features are enabled in production:
- ✅ **Full Profile Access** - Complete user profile management
- ✅ **Unlimited Analysis** - No restrictions on analysis
- ✅ **All Valuation Models** - Graham, DCF, Lynch calculations
- ✅ **CSV Export** - Full data export capabilities
- ✅ **Real-time Data** - Yahoo Finance integration
- ✅ **Subscription Management** - Upgrade/downgrade plans
- ✅ **Payment Processing** - Stripe integration ready
- ✅ **Account Settings** - Full user customization
- ✅ **Usage Statistics** - Track your analysis history
- ✅ **Multi-stock Support** - Analyze 100+ stocks simultaneously

## 🎯 Production URL Structure

- **Landing**: `https://yourdomain.com/`
- **Login**: `https://yourdomain.com/login`
- **Signup**: `https://yourdomain.com/signup`
- **Dashboard**: `https://yourdomain.com/dashboard`
- **Profile**: `https://yourdomain.com/profile`
- **API**: `https://yourdomain.com/api/analyze`

## 💡 Best Practices

1. **Always use HTTPS** in production
2. **Regular backups** of user data and analysis history
3. **Monitor error rates** and performance metrics
4. **Keep dependencies updated** for security patches
5. **Use environment-specific configs** (dev vs prod)
6. **Implement proper logging** for debugging
7. **Set up alerts** for downtime or errors

## 📞 Support

For deployment issues or questions:
- Check logs: `docker-compose logs -f`
- Review environment: Check `.env` file
- Test locally first: `APP_ENV=development python app.py`


