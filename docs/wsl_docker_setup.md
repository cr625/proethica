# Docker PostgreSQL Setup for WSL

This document provides instructions for setting up the PostgreSQL Docker container in Windows Subsystem for Linux (WSL) for the ProEthica application.

## Prerequisites

- WSL2 installed and configured
- Docker Desktop for Windows with WSL2 backend enabled
- Docker CLI available in your WSL distribution

## Port Configuration

The application is configured to use PostgreSQL on port 5433 to avoid conflicts with any native PostgreSQL installation:

- The Docker container exposes PostgreSQL on port 5433 on the host
- All database connection strings use port 5433

## Setting Up the Environment

### 1. Stop Native PostgreSQL (if running)

If you have PostgreSQL installed natively in WSL, stop it to avoid port conflicts:

```bash
sudo service postgresql stop
```

To permanently disable it from starting automatically:

```bash
sudo systemctl disable postgresql
```

### 2. Create the Docker Container

Create the PostgreSQL container with pgvector support:

```bash
docker run -d --name postgres17-pgvector \
  -p 5433:5432 \
  -e POSTGRES_PASSWORD=PASS \
  -e POSTGRES_DB=ai_ethical_dm \
  -v pgvector_data:/var/lib/postgresql/data \
  pgvector/pgvector:pg17
```

This command:
- Creates a container named `postgres17-pgvector`
- Maps host port 5433 to container port 5432
- Sets the PostgreSQL password to "PASS"
- Creates a database named "ai_ethical_dm"
- Uses a named volume for data persistence
- Uses the official pgvector image with PostgreSQL 17

### 3. Verify Container Status

Check if the container is running:

```bash
docker ps
```

You should see the `postgres17-pgvector` container in the list.

### 4. Restore Database (if needed)

If you have an existing database backup, restore it to the Docker container:

```bash
bash backups/restore_database.sh backups/ai_ethical_dm_backup_YYYYMMDD_HHMMSS.dump
```

The restore script has been updated to use port 5433, which matches the Docker container configuration.

## Starting the Application

The `start_proethica.sh` script has been updated to:

1. Detect WSL environment
2. Stop native PostgreSQL if running
3. Check for and start the Docker PostgreSQL container
4. Configure the application to use the Docker container

To start the application:

```bash
./start_proethica.sh
```

This will automatically handle the Docker container setup and launch the application.

## Troubleshooting

### Container Won't Start

If the Docker container fails to start:

```bash
docker logs postgres17-pgvector
```

### Database Connection Issues

If the application can't connect to the database:

1. Verify the container is running:
   ```bash
   docker ps
   ```

2. Check the database URL in `.env` file:
   ```
   DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
   ```

3. Test the connection directly:
   ```bash
   PGPASSWORD=PASS psql -h localhost -p 5433 -U postgres -d ai_ethical_dm
   ```

### Native PostgreSQL Conflicts

If you're still experiencing port conflicts:

1. Verify native PostgreSQL is stopped:
   ```bash
   sudo service postgresql status
   ```

2. Check what's using port 5433:
   ```bash
   sudo lsof -i :5433
   ```

## Production Deployment Notes

For production environments:

1. Use the same Docker-based approach for consistency
2. Adjust credentials and security settings as needed
3. Consider using Docker Compose for orchestration
4. Update connection strings to match your production configuration
