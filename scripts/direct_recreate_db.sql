-- Direct Database Recreation Script
-- WARNING: This will completely drop and recreate the database.
-- Run as PostgreSQL superuser (postgres):
-- psql -U postgres -f scripts/direct_recreate_db.sql

-- Variables (adjust these as needed)
\set db_name 'ai_ethical_dm'
\set db_user 'postgres'

-- Drop connections
SELECT pg_terminate_backend(pg_stat_activity.pid)
FROM pg_stat_activity
WHERE pg_stat_activity.datname = :'db_name'
AND pid <> pg_backend_pid();

-- Drop and recreate database
DROP DATABASE IF EXISTS :db_name;
CREATE DATABASE :db_name WITH OWNER = :db_user ENCODING = 'UTF8';

-- Connect to the newly created database
\c :db_name

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- Output confirmation
\echo '\n=== Database has been recreated ==='
\echo 'Database: ' :db_name
\echo 'Owner: ' :db_user
\echo '\nNext steps:'
\echo '1. Run database migrations: flask db upgrade'
\echo '2. Create admin user: python scripts/create_admin_user.py'
