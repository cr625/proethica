-- Enable pgvector extension on the ai_ethical_dm database
\c ai_ethical_dm;
CREATE EXTENSION IF NOT EXISTS vector;
