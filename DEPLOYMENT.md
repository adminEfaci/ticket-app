# Deployment Guide

## Prerequisites

1. A server with Docker and Docker Compose installed
2. A domain name pointing to your server
3. GitHub account with repository access
4. Docker Hub account (or another container registry)

## Setup GitHub Secrets

Add the following secrets to your GitHub repository:

1. **DOCKER_USERNAME**: Your Docker Hub username
2. **DOCKER_PASSWORD**: Your Docker Hub password
3. **DEPLOY_HOST**: Your server's IP address or hostname
4. **DEPLOY_USER**: SSH user for deployment
5. **DEPLOY_KEY**: SSH private key for deployment

## Server Setup

1. **Create deployment directory:**
   ```bash
   sudo mkdir -p /opt/ticket-app
   sudo chown $USER:$USER /opt/ticket-app
   cd /opt/ticket-app
   ```

2. **Create environment file:**
   ```bash
   cat > .env << EOF
   # Database
   DB_USER=ticketapp
   DB_PASSWORD=your-secure-password
   DB_NAME=ticketapp

   # Backend
   SECRET_KEY=your-secret-key-here
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30

   # Domain
   DOMAIN=yourdomain.com
   FRONTEND_URL=https://yourdomain.com

   # Docker
   DOCKER_USERNAME=your-docker-username

   # Traefik
   TRAEFIK_AUTH=admin:$$2y$$10$$your-hashed-password
   EOF
   ```

3. **Create Traefik configuration:**
   ```bash
   mkdir -p traefik
   touch traefik/acme.json
   chmod 600 traefik/acme.json
   ```

   Create `traefik/traefik.yml`:
   ```yaml
   api:
     dashboard: true

   entryPoints:
     web:
       address: ":80"
       http:
         redirections:
           entryPoint:
             to: websecure
             scheme: https
     websecure:
       address: ":443"

   certificatesResolvers:
     letsencrypt:
       acme:
         email: your-email@example.com
         storage: /acme.json
         httpChallenge:
           entryPoint: web

   providers:
     docker:
       exposedByDefault: false
   ```

4. **Copy docker-compose.prod.yml to server:**
   ```bash
   scp docker-compose.prod.yml user@server:/opt/ticket-app/docker-compose.yml
   ```

## Initial Deployment

1. **Pull and start services:**
   ```bash
   cd /opt/ticket-app
   docker-compose pull
   docker-compose up -d
   ```

2. **Create initial admin user:**
   ```bash
   docker-compose exec backend python -m backend.scripts.create_admin
   ```

3. **Check logs:**
   ```bash
   docker-compose logs -f
   ```

## GitHub Actions Workflow

The CI/CD pipeline will:
1. Run tests for both backend and frontend
2. Build Docker images
3. Push to Docker Hub
4. Deploy to production server

## Monitoring

- Backend API: https://api.yourdomain.com
- Frontend: https://yourdomain.com
- Traefik Dashboard: https://traefik.yourdomain.com

## Backup

Create a backup script at `/opt/ticket-app/backup.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/ticket-app"
mkdir -p $BACKUP_DIR

# Backup database
docker-compose exec -T postgres pg_dump -U ticketapp ticketapp | gzip > $BACKUP_DIR/db_$(date +%Y%m%d_%H%M%S).sql.gz

# Backup volumes
tar -czf $BACKUP_DIR/volumes_$(date +%Y%m%d_%H%M%S).tar.gz volumes/

# Keep only last 7 days of backups
find $BACKUP_DIR -type f -mtime +7 -delete
```

Add to crontab:
```bash
0 2 * * * /opt/ticket-app/backup.sh
```

## SSL Certificate Renewal

Traefik handles SSL certificate renewal automatically via Let's Encrypt.

## Troubleshooting

1. **Check container status:**
   ```bash
   docker-compose ps
   ```

2. **View logs:**
   ```bash
   docker-compose logs [service-name]
   ```

3. **Restart services:**
   ```bash
   docker-compose restart [service-name]
   ```

4. **Full restart:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```