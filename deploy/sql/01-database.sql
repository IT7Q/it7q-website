-- IT7Q website database: roles and database (PLAN.md §4.8, §4.11; DEPLOY.md step 2).
-- Run once as the Postgres superuser, in psql. No passwords in this file:
-- set the login role's password afterwards with \password it7q_web.
--
--   it7q_web_owner  owns every table and function. NOLOGIN: nobody connects as it.
--   it7q_web        what n8n logs in as. It can only EXECUTE the web.* functions
--                   in 03-functions.sql: no direct SELECT/INSERT/UPDATE/DELETE on any table.

CREATE ROLE it7q_web_owner NOLOGIN;
CREATE ROLE it7q_web LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT 10;

CREATE DATABASE it7q_web OWNER it7q_web_owner ENCODING 'UTF8' TEMPLATE template0;
REVOKE ALL ON DATABASE it7q_web FROM PUBLIC;
GRANT CONNECT ON DATABASE it7q_web TO it7q_web;

\connect it7q_web

REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA web AUTHORIZATION it7q_web_owner;
GRANT USAGE ON SCHEMA web TO it7q_web;
ALTER ROLE it7q_web IN DATABASE it7q_web SET search_path = web;
-- Functions default to EXECUTE for PUBLIC; switch that off for everything the owner creates.
ALTER DEFAULT PRIVILEGES FOR ROLE it7q_web_owner REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;
