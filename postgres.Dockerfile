FROM postgres:17

ENV PG_MAJOR=17

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    postgresql-server-dev-$PG_MAJOR \
    && rm -rf /var/lib/apt/lists/*

# Clone and install pgvector
RUN git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git \
    && cd pgvector \
    && make \
    && make install

# Add initialization script to enable extension automatically
COPY ./init-pgvector.sql /docker-entrypoint-initdb.d/
