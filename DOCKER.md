# Docker Deployment Guide

This guide explains how to deploy the GenAI CCM Platform using Docker and Docker Compose.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- SQL Server database (accessible from Docker containers)
- Azure OpenAI account with API credentials

## Quick Start

### 1. Configure Environment Variables

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with your actual configuration:

```bash
# Required: Azure OpenAI
AZURE_OPENAI_API_KEY=your-azure-openai-api-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# Required: SQL Server databases
DB_SERVER=your-sql-server.database.windows.net
DB_NAME=ccm_genai
DB_USERNAME=your-db-username
DB_PASSWORD=your-db-password

KB_DB_SERVER=your-sql-server.database.windows.net
KB_DB_NAME=regulatory_data_mart
KB_DB_USERNAME=your-db-username
KB_DB_PASSWORD=your-db-password
```

### 2. Build and Start Services

```bash
docker-compose up --build
```

Or run in detached mode:

```bash
docker-compose up -d --build
```

### 3. Access the Application

- **Frontend**: http://localhost:80
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/docs

## Initialization on First Run

On the **first run**, the backend container automatically:

1. **Seeds initial users** (admin, approver, and sample users)
2. **Builds the knowledge base** (schema + sample data from the regulatory database)

### Default Users Created

| Username | Password | Role | Department |
|----------|----------|------|------------|
| admin.user | admin123 | admin | IT Administration |
| approver.user | approver123 | approver | Risk Management |
| john.doe | user123 | user | Operations |
| jane.smith | user123 | user | Compliance |

⚠️ **Change these passwords immediately in production!**

### Controlling Initialization

You can control the initialization behavior via environment variables in `.env`:

```bash
# Skip knowledge base build entirely
SKIP_KB_BUILD=true

# Or choose build mode: full, schema, or skip
KB_BUILD_MODE=full    # Default: schema + sample data
KB_BUILD_MODE=schema  # Only schema, no sample data
KB_BUILD_MODE=skip    # Skip KB build
```

### Re-running Initialization

To re-run initialization scripts:

```bash
# Stop containers
docker-compose down

# Remove the backend data volume (this deletes the initialization flag)
docker volume rm reportgenai-main_backend_data

# Start again (will trigger initialization)
docker-compose up --build
```

## Container Management

### View Logs

```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Frontend only
docker-compose logs -f frontend
```

### Stop Services

```bash
docker-compose down
```

### Stop and Remove Volumes (Complete Reset)

```bash
docker-compose down -v
```

### Restart a Specific Service

```bash
docker-compose restart backend
docker-compose restart frontend
```

## Data Persistence

The application uses Docker volumes for data persistence:

| Volume | Purpose | Contents |
|--------|---------|----------|
| `backend_data` | Application data | Vector database, initialization flag |
| `backend_logs` | Application logs | Backend application logs |

### Backup Data

```bash
# Backup backend data
docker run --rm -v reportgenai-main_backend_data:/data -v $(pwd):/backup alpine tar czf /backup/backend_data_backup.tar.gz -C /data .

# Backup logs
docker run --rm -v reportgenai-main_backend_logs:/data -v $(pwd):/backup alpine tar czf /backup/backend_logs_backup.tar.gz -C /data .
```

### Restore Data

```bash
# Restore backend data
docker run --rm -v reportgenai-main_backend_data:/data -v $(pwd):/backup alpine tar xzf /backup/backend_data_backup.tar.gz -C /data
```

## Troubleshooting

### Backend won't start / Database connection issues

1. Check database connectivity:
   ```bash
   docker-compose exec backend python -c "from app.core.database import get_engine; print(get_engine())"
   ```

2. Verify environment variables:
   ```bash
   docker-compose exec backend env | grep DB_
   ```

3. Check logs:
   ```bash
   docker-compose logs backend
   ```

### Knowledge base build fails

If KB build fails on first run, you can:

1. **Skip it and build manually later**:
   ```bash
   # In .env, set:
   SKIP_KB_BUILD=true
   
   # Restart
   docker-compose restart backend
   
   # Build manually
   docker-compose exec backend python scripts/build_knowledge_base.py
   ```

2. **Use schema-only mode**:
   ```bash
   # In .env, set:
   KB_BUILD_MODE=schema
   ```

### Frontend shows connection errors

1. Check if backend is healthy:
   ```bash
   curl http://localhost:8000/api/health
   ```

2. Check backend logs:
   ```bash
   docker-compose logs backend
   ```

3. Verify CORS settings in `.env`:
   ```bash
   CORS_ORIGINS=http://localhost:3000,http://localhost:80,http://localhost
   ```

### Manual initialization

Run initialization scripts manually:

```bash
# Seed users
docker-compose exec backend python scripts/seed_users.py

# Build knowledge base (interactive)
docker-compose exec backend python scripts/build_knowledge_base.py
```

## Production Deployment

For production deployments, consider:

1. **Use secrets management** instead of `.env` files
2. **Enable SSL/TLS** (add reverse proxy like Traefik or nginx)
3. **Set `DEBUG=false`** in environment
4. **Change default passwords** immediately
5. **Configure proper CORS origins**
6. **Set up monitoring and logging**
7. **Use managed SQL Server** with proper backups
8. **Scale backend horizontally** if needed:
   ```yaml
   services:
     backend:
       deploy:
         replicas: 3
   ```

## Architecture

```
┌─────────────────────────────────────────────┐
│  Docker Host                                │
│                                             │
│  ┌──────────────┐      ┌─────────────────┐│
│  │   Frontend   │      │    Backend      ││
│  │   (nginx)    │──────│   (FastAPI)     ││
│  │   Port 80    │ HTTP │   Port 8000     ││
│  └──────────────┘      └────────┬────────┘│
│                                  │         │
│                        ┌─────────▼────────┐│
│                        │  Volumes         ││
│                        │  - backend_data  ││
│                        │  - backend_logs  ││
│                        └──────────────────┘│
└─────────────────────────────────────────────┘
           │                     │
           │                     │
      [Browser]            [SQL Server]
                          (External)
```

## Environment Variables Reference

See [.env.example](.env.example) for a complete list of configuration options.

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Review [README.md](README.md) for application details
- Inspect running containers: `docker-compose ps`
