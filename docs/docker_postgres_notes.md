# Docker PostgreSQL Setup for Ontology Case Analysis

This document provides information about using Docker PostgreSQL with the ontology case analysis functionality.

## Docker PostgreSQL Configuration

The project uses a Docker container for PostgreSQL with the following configuration:

- **Port**: 5433 (mapped from standard port 5432 inside the container)
- **Default Database**: proethica
- **Default User**: postgres
- **Default Password**: postgres (should be changed in production)

## Connection Details

When connecting to the PostgreSQL database in Docker, use these settings:

```
Host: localhost
Port: 5433
Database: proethica
User: postgres
Password: postgres (or as configured in .env)
```

Or use the connection string:

```
postgresql://postgres:postgres@localhost:5433/proethica
```

## Environment Variables

The following environment variables are used to connect to the database:

- `DATABASE_URL`: Complete connection string (if set, other variables are ignored)
- `DB_HOST`: Database host (default: localhost)
- `DB_PORT`: Database port (default: 5433)
- `DB_NAME`: Database name (default: proethica)
- `DB_USER`: Database user (default: postgres)
- `DB_PASSWORD`: Database password (default: postgres)

## Docker Commands

### Starting the PostgreSQL Container

```bash
# Start PostgreSQL container
docker-compose up -d postgres
```

### Checking Container Status

```bash
# Check if the container is running
docker-compose ps postgres

# View container logs
docker-compose logs -f postgres
```

### Accessing the PostgreSQL Shell

```bash
# Connect to PostgreSQL shell
docker-compose exec postgres psql -U postgres -d proethica
```

### Backing Up and Restoring

```bash
# Backup database
docker-compose exec postgres pg_dump -U postgres proethica > backup.sql

# Restore database
cat backup.sql | docker-compose exec -T postgres psql -U postgres -d proethica
```

## Notes for Developers

- All database scripts should use port 5433 when not using the `DATABASE_URL` environment variable
- When developing locally without Docker, remember to adjust the port to match your PostgreSQL installation
- For CI/CD environments, always use the `DATABASE_URL` variable for flexibility
