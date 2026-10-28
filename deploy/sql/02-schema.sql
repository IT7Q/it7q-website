-- IT7Q website database: tables (PLAN.md §4.8). Run in database it7q_web as the
-- superuser, after 01-database.sql. Everything here is owned by it7q_web_owner;
-- the n8n role gets no table privileges at all (it calls the functions in 03).
-- Safe to re-run: every statement is IF NOT EXISTS.

SET ROLE it7q_web_owner;
SET search_path = web;

-- One row per NDA request. A new row per attempt: a rejected or revoked person can
-- ask again, but only one pending/approved row per email can exist (§4.3 step 4).
CREATE TABLE IF NOT EXISTS nda_requests (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email               text        NOT NULL CHECK (email = lower(email) AND length(email) <= 254),
    name                text        NOT NULL CHECK (length(name) <= 100),
    org                 text        NOT NULL DEFAULT '' CHECK (length(org) <= 150),
    reason              text        NOT NULL CHECK (length(reason) <= 1000),
    wants_investor      boolean     NOT NULL DEFAULT false,
    nda_version         text        NOT NULL,
    nda_sha256          text        NOT NULL CHECK (nda_sha256 ~ '^[0-9a-f]{64}$'),
    signature_text      text        NOT NULL CHECK (length(signature_text) <= 100),
    signed_at           timestamptz NOT NULL DEFAULT now(),
    signed_ip           inet,                       -- nulled after 12 months (§4.10)
    signed_ua           text,                       -- nulled after 12 months (§4.10)
    status              text        NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected', 'revoked')),
    approved_at         timestamptz,
    approved_divisions  text[]      NOT NULL DEFAULT ARRAY['msp','opus','mentis','tempestas','portus','fabricus','domus'],
    investor_access     boolean     NOT NULL DEFAULT false,
    expires_at          timestamptz,                -- signed_at + 3 years, set on approval (Q10)
    password_hash       text CHECK (password_hash IS NULL OR password_hash ~ '^scrypt\$16384\$8\$1\$[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+$'),
    password_set_at     timestamptz,
    rejected_at         timestamptz,
    revoked_at          timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS nda_requests_one_live_per_email
    ON nda_requests (email) WHERE status IN ('pending', 'approved');
CREATE INDEX IF NOT EXISTS nda_requests_email ON nda_requests (email);

-- One-time review links (§4.4): only the SHA-256 of the token is stored.
CREATE TABLE IF NOT EXISTS nda_review_tokens (
    token_sha256  bytea       PRIMARY KEY CHECK (length(token_sha256) = 32),
    request_id    bigint      NOT NULL REFERENCES nda_requests (id) ON DELETE CASCADE,
    created_at    timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz NOT NULL,
    used_at       timestamptz
);

-- Login sessions (§4.5): 8 h absolute, 1 h idle. Only the SHA-256 of the token is stored.
CREATE TABLE IF NOT EXISTS nda_sessions (
    token_sha256  bytea       PRIMARY KEY CHECK (length(token_sha256) = 32),
    request_id    bigint      NOT NULL REFERENCES nda_requests (id) ON DELETE CASCADE,
    created_at    timestamptz NOT NULL DEFAULT now(),
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz NOT NULL,
    ip            inet,
    ua            text
);
CREATE INDEX IF NOT EXISTS nda_sessions_request ON nda_sessions (request_id);

-- Gated detail, seeded from gated/*.json by tools/gated_sql.py after Chris's review (§4.9).
-- project_id '_page' holds the investor area's sections.
CREATE TABLE IF NOT EXISTS nda_content (
    division    text        NOT NULL,
    project_id  text        NOT NULL,
    version     integer     NOT NULL DEFAULT 1,
    body        jsonb       NOT NULL,
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (division, project_id)
);

-- Fixed-window counters for rate limits and login lockout (§4.2).
CREATE TABLE IF NOT EXISTS nda_rate (
    key           text        NOT NULL,
    window_start  timestamptz NOT NULL,
    count         integer     NOT NULL DEFAULT 0,
    PRIMARY KEY (key, window_start)
);

-- Every event (§4.2 Audit), kept 12 months (§4.10). request_id is not a foreign key so
-- the trail outlives a deleted request until its own 12 months are up.
CREATE TABLE IF NOT EXISTS nda_audit (
    id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at          timestamptz NOT NULL DEFAULT now(),
    event       text        NOT NULL,
    request_id  bigint,
    ip          inet,
    ua          text,
    detail      jsonb       NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS nda_audit_at ON nda_audit (at);

-- Contact-form messages (§4.7), kept 12 months.
CREATE TABLE IF NOT EXISTS enquiries (
    id        bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at        timestamptz NOT NULL DEFAULT now(),
    name      text        NOT NULL CHECK (length(name) <= 100),
    email     text        NOT NULL CHECK (length(email) <= 254),
    phone     text        NOT NULL DEFAULT '' CHECK (length(phone) <= 30),
    service   text        NOT NULL,
    division  text        NOT NULL DEFAULT '',
    message   text        NOT NULL CHECK (length(message) <= 2000),
    ip        inet
);
CREATE INDEX IF NOT EXISTS enquiries_at ON enquiries (at);

REVOKE ALL ON ALL TABLES IN SCHEMA web FROM PUBLIC, it7q_web;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA web FROM PUBLIC, it7q_web;
RESET ROLE;
