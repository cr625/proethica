# Use the official pgvector image for Postgres 17
FROM pgvector/pgvector:pg17

# Add initialization script to enable extension automatically
COPY ./init-pgvector.sql /docker-entrypoint-initdb.d/
