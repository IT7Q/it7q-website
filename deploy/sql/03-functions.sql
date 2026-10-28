-- IT7Q website database: the only way in (PLAN.md §4.2 "Least-privilege DB").
-- Run in database it7q_web as the superuser, after 02-schema.sql. Safe to re-run.
--
-- n8n (role it7q_web) can EXECUTE the nine functions granted at the bottom and
-- nothing else. Each takes one jsonb argument and returns jsonb, so every n8n
-- Postgres node is the same shape:  SELECT web.<fn>($1::jsonb) AS r
-- Tokens never reach the database: n8n sends their SHA-256 (64 hex chars).
-- Passwords never reach the database: n8n sends an scrypt hash.

SET ROLE it7q_web_owner;
SET search_path = web;

-- ------------------------------------------------------------------ helpers (not granted)

CREATE OR REPLACE FUNCTION _audit(p_event text, p_request bigint, p_ip inet, p_ua text, p_detail jsonb DEFAULT '{}')
RETURNS void LANGUAGE sql AS $$
    INSERT INTO nda_audit (event, request_id, ip, ua, detail)
    VALUES (p_event, p_request, p_ip, left(p_ua, 400), coalesce(p_detail, '{}'));
$$;

CREATE OR REPLACE FUNCTION _ip(p text) RETURNS inet LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    RETURN p::inet;
EXCEPTION WHEN others THEN
    RETURN NULL;
END $$;

CREATE OR REPLACE FUNCTION _hex32(p text) RETURNS bytea LANGUAGE plpgsql IMMUTABLE AS $$
BEGIN
    IF p IS NULL OR p !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'expected a 64-character hex SHA-256';
    END IF;
    RETURN decode(p, 'hex');
END $$;

CREATE OR REPLACE FUNCTION _window(p_secs integer) RETURNS timestamptz LANGUAGE sql STABLE AS $$
    SELECT to_timestamp(floor(extract(epoch FROM now()) / p_secs) * p_secs);
$$;

-- Count one hit; true while the window's count is within the limit.
CREATE OR REPLACE FUNCTION _hit(p_key text, p_secs integer, p_limit integer) RETURNS boolean
LANGUAGE plpgsql AS $$
DECLARE n integer;
BEGIN
    INSERT INTO nda_rate AS r (key, window_start, count) VALUES (p_key, _window(p_secs), 1)
    ON CONFLICT (key, window_start) DO UPDATE SET count = r.count + 1
    RETURNING r.count INTO n;
    RETURN n <= p_limit;
END $$;

CREATE OR REPLACE FUNCTION _count(p_key text, p_secs integer) RETURNS integer LANGUAGE sql STABLE AS $$
    SELECT coalesce((SELECT count FROM nda_rate WHERE key = p_key AND window_start = _window(p_secs)), 0);
$$;

CREATE OR REPLACE FUNCTION _divisions() RETURNS text[] LANGUAGE sql IMMUTABLE AS $$
    SELECT ARRAY['msp','opus','mentis','tempestas','portus','fabricus','domus'];
$$;

-- An approved, unrevoked, unexpired NDA with a password: the only rows that may log in.
CREATE OR REPLACE FUNCTION _live(p_email text) RETURNS nda_requests LANGUAGE sql STABLE AS $$
    SELECT * FROM nda_requests
    WHERE email = lower(p_email) AND status = 'approved' AND revoked_at IS NULL
      AND expires_at > now() AND password_hash IS NOT NULL
    LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION _public(r nda_requests) RETURNS jsonb LANGUAGE sql STABLE AS $$
    SELECT jsonb_build_object(
        'id', r.id, 'email', r.email, 'name', r.name, 'org', r.org, 'reason', r.reason,
        'wants_investor', r.wants_investor, 'nda_version', r.nda_version, 'signed_at', r.signed_at,
        'status', r.status, 'approved_at', r.approved_at, 'approved_divisions', to_jsonb(r.approved_divisions),
        'investor_access', r.investor_access, 'expires_at', r.expires_at, 'rejected_at', r.rejected_at,
        'revoked_at', r.revoked_at, 'has_password', r.password_hash IS NOT NULL,
        'active_sessions', (SELECT count(*) FROM nda_sessions s WHERE s.request_id = r.id AND s.expires_at > now()));
$$;

-- ------------------------------------------------------------------ nda-submission (§4.3)
-- p: name, email, org, reason, wants_investor, nda_version, nda_sha256, signature, ip, ua, review_sha256
-- result: created | duplicate | limited

CREATE OR REPLACE FUNCTION submit_nda(p jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = web, pg_temp AS $$
DECLARE
    v_email text := lower(p->>'email');
    v_ip inet := _ip(p->>'ip');
    v_ok_ip boolean;
    v_ok_email boolean;
    v_id bigint;
BEGIN
    v_ok_ip := _hit('nda:ip:' || coalesce(host(v_ip), '?'), 3600, 5);
    v_ok_email := _hit('nda:email:' || v_email, 86400, 3);
    IF NOT (v_ok_ip AND v_ok_email) THEN
        PERFORM _audit('nda_rate_limited', NULL, v_ip, p->>'ua', jsonb_build_object('email', v_email));
        RETURN jsonb_build_object('result', 'limited');
    END IF;

    SELECT id INTO v_id FROM nda_requests WHERE email = v_email AND status IN ('pending', 'approved');
    IF FOUND THEN
        PERFORM _audit('nda_duplicate', v_id, v_ip, p->>'ua');
        RETURN jsonb_build_object('result', 'duplicate');
    END IF;

    BEGIN
        INSERT INTO nda_requests (email, name, org, reason, wants_investor, nda_version, nda_sha256,
                                  signature_text, signed_ip, signed_ua)
        VALUES (v_email, p->>'name', coalesce(p->>'org', ''), p->>'reason',
                coalesce((p->>'wants_investor')::boolean, false), p->>'nda_version', p->>'nda_sha256',
                p->>'signature', v_ip, left(p->>'ua', 400))
        RETURNING id INTO v_id;
    EXCEPTION WHEN unique_violation THEN  -- two submissions racing
        RETURN jsonb_build_object('result', 'duplicate');
    END;

    INSERT INTO nda_review_tokens (token_sha256, request_id, expires_at)
    VALUES (_hex32(p->>'review_sha256'), v_id, now() + interval '7 days');
    PERFORM _audit('nda_submitted', v_id, v_ip, p->>'ua',
                   jsonb_build_object('nda_version', p->>'nda_version', 'wants_investor', p->'wants_investor'));
    RETURN jsonb_build_object('result', 'created', 'request_id', v_id,
                              'signed_at', (SELECT signed_at FROM nda_requests WHERE id = v_id));
END $$;

-- ------------------------------------------------------------------ nda-review (§4.4)
-- review_view p: {review_sha256?}. With a token: that request (if the token is live). Without: the list.

CREATE OR REPLACE FUNCTION review_view(p jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = web, pg_temp AS $$
DECLARE r nda_requests;
BEGIN
    IF coalesce(p->>'review_sha256', '') <> '' THEN
        SELECT q.* INTO r FROM nda_review_tokens t JOIN nda_requests q ON q.id = t.request_id
        WHERE t.token_sha256 = _hex32(p->>'review_sha256') AND t.used_at IS NULL AND t.expires_at > now();
        IF NOT FOUND THEN
            RETURN jsonb_build_object('mode', 'invalid');
        END IF;
        RETURN jsonb_build_object('mode', 'request', 'request', _public(r));
    END IF;
    RETURN jsonb_build_object('mode', 'list', 'requests', coalesce(
        (SELECT jsonb_agg(x.j ORDER BY x.created_at DESC)
         FROM (SELECT _public(q) AS j, q.created_at FROM nda_requests q ORDER BY q.created_at DESC LIMIT 200) x),
        '[]'));
END $$;

-- review_post p: {action, actor, ip, review_sha256 (approve/reject), request_id (others),
--                 divisions[], investor, password_hash (approve/reset), new_review_sha256 (new_review_link)}
-- Only POST reaches this (GET never changes state, §4.4).

CREATE OR REPLACE FUNCTION review_post(p jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = web, pg_temp AS $$
DECLARE
    v_action text := p->>'action';
    v_ip inet := _ip(p->>'ip');
    v_detail jsonb := jsonb_build_object('actor', p->>'actor');
    r nda_requests;
    v_id bigint;
    v_divs text[] := ARRAY(SELECT d FROM jsonb_array_elements_text(coalesce(p->'divisions', '[]')) d
                           WHERE d = ANY(_divisions()));
BEGIN
    IF v_action IN ('approve', 'reject') THEN
        IF v_action = 'approve' AND cardinality(v_divs) = 0 THEN  -- checked before the link is used up
            RETURN jsonb_build_object('ok', false, 'error', 'Pick at least one division.');
        END IF;
        -- The one-time link: use up the token, then lock the request.
        UPDATE nda_review_tokens SET used_at = now()
        WHERE token_sha256 = _hex32(p->>'review_sha256') AND used_at IS NULL AND expires_at > now()
        RETURNING request_id INTO v_id;
        IF v_id IS NULL THEN
            RETURN jsonb_build_object('ok', false, 'error', 'This review link has expired or was already used.');
        END IF;
        SELECT * INTO r FROM nda_requests WHERE id = v_id AND status = 'pending' FOR UPDATE;
        IF NOT FOUND THEN
            RETURN jsonb_build_object('ok', false, 'error', 'This request is no longer pending.');
        END IF;
        IF v_action = 'reject' THEN
            UPDATE nda_requests SET status = 'rejected', rejected_at = now() WHERE id = r.id;
            PERFORM _audit('nda_rejected', r.id, v_ip, NULL, v_detail);
            RETURN jsonb_build_object('ok', true, 'action', 'reject', 'email', r.email, 'name', r.name);
        END IF;
        UPDATE nda_requests SET status = 'approved', approved_at = now(), approved_divisions = v_divs,
               investor_access = coalesce((p->>'investor')::boolean, false),
               expires_at = signed_at + interval '3 years',
               password_hash = p->>'password_hash', password_set_at = now()
        WHERE id = r.id RETURNING * INTO r;
        UPDATE nda_review_tokens SET used_at = now() WHERE request_id = r.id AND used_at IS NULL;
        PERFORM _audit('nda_approved', r.id, v_ip, NULL,
                       v_detail || jsonb_build_object('divisions', to_jsonb(v_divs), 'investor', r.investor_access));
        RETURN jsonb_build_object('ok', true, 'action', 'approve', 'email', r.email, 'name', r.name,
                                  'divisions', to_jsonb(r.approved_divisions), 'investor', r.investor_access,
                                  'expires_at', r.expires_at);
    END IF;

    SELECT * INTO r FROM nda_requests WHERE id = (p->>'request_id')::bigint FOR UPDATE;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('ok', false, 'error', 'No such request.');
    END IF;

    IF v_action = 'new_review_link' THEN
        IF r.status <> 'pending' THEN
            RETURN jsonb_build_object('ok', false, 'error', 'Only pending requests get a review link.');
        END IF;
        INSERT INTO nda_review_tokens (token_sha256, request_id, expires_at)
        VALUES (_hex32(p->>'new_review_sha256'), r.id, now() + interval '7 days');
        PERFORM _audit('nda_review_link', r.id, v_ip, NULL, v_detail);
        RETURN jsonb_build_object('ok', true, 'action', v_action, 'request', _public(r));
    END IF;

    IF r.status <> 'approved' THEN
        RETURN jsonb_build_object('ok', false, 'error', 'Only approved requests can be changed this way.');
    END IF;

    IF v_action = 'revoke' THEN
        UPDATE nda_requests SET status = 'revoked', revoked_at = now() WHERE id = r.id;
        DELETE FROM nda_sessions WHERE request_id = r.id;  -- takes effect on the next request (§4.4)
    ELSIF v_action = 'reset' THEN
        UPDATE nda_requests SET password_hash = p->>'password_hash', password_set_at = now() WHERE id = r.id;
        DELETE FROM nda_sessions WHERE request_id = r.id;
    ELSIF v_action IN ('investor_on', 'investor_off') THEN
        UPDATE nda_requests SET investor_access = (v_action = 'investor_on') WHERE id = r.id;
    ELSE
        RETURN jsonb_build_object('ok', false, 'error', 'Unknown action.');
    END IF;
    PERFORM _audit('nda_' || v_action, r.id, v_ip, NULL, v_detail);
    RETURN jsonb_build_object('ok', true, 'action', v_action, 'email', r.email, 'name', r.name);
END $$;

-- ------------------------------------------------------------------ nda-login (§4.5)
-- login_begin p: {email, ip} -> {locked, password_hash|null}. n8n checks the password against the
-- hash (or a dummy hash when null, so unknown emails take as long), then calls login_finish.

CREATE OR REPLACE FUNCTION login_begin(p jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = web, pg_temp AS $$
DECLARE
    v_email text := lower(p->>'email');
    v_ip text := coalesce(host(_ip(p->>'ip')), '?');
BEGIN
    IF _count('loginfail:email:' || v_email, 900) >= 5 OR _count('loginfail:ip:' || v_ip, 900) >= 20 THEN
        PERFORM _audit('login_locked', NULL, _ip(p->>'ip'), NULL, jsonb_build_object('email', v_email));
        RETURN jsonb_build_object('locked', true);
    END IF;
    RETURN jsonb_build_object('locked', false, 'password_hash', (_live(v_email)).password_hash);
END $$;

-- login_finish p: {email, ok, token_sha256, ip, ua} -> {result: ok|failed, ...}

CREATE OR REPLACE FUNCTION login_finish(p jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = web, pg_temp AS $$
DECLARE
    v_email text := lower(p->>'email');
    v_ip inet := _ip(p->>'ip');
    r nda_requests;
    v_expires timestamptz := now() + interval '8 hours';
BEGIN
    r := _live(v_email);  -- re-checked: an approval may have changed since login_begin
    IF coalesce((p->>'ok')::boolean, false) AND r.id IS NOT NULL THEN
        INSERT INTO nda_sessions (token_sha256, request_id, expires_at, ip, ua)
        VALUES (_hex32(p->>'token_sha256'), r.id, v_expires, v_ip, left(p->>'ua', 400));
        PERFORM _audit('login_ok', r.id, v_ip, p->>'ua');
        RETURN jsonb_build_object('result', 'ok', 'email', r.email, 'expires_at', v_expires,
                                  'investor', r.investor_access);
    END IF;
    PERFORM _hit('loginfail:email:' || v_email, 900, 5);
    PERFORM _hit('loginfail:ip:' || coalesce(host(v_ip), '?'), 900, 20);
    PERFORM _audit('login_failed', (SELECT id FROM nda_requests WHERE email = v_email ORDER BY id DESC LIMIT 1),
                   v_ip, p->>'ua', jsonb_build_object('email', v_email));
    RETURN jsonb_build_object('result', 'failed');
END $$;

-- ------------------------------------------------------------------ nda-content (§4.6)
-- content_get p: {token_sha256, division, ip} -> {status: 200|401|403|429, ...}

CREATE OR REPLACE FUNCTION content_get(p jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = web, pg_temp AS $$
DECLARE
    v_token bytea := _hex32(p->>'token_sha256');
    v_div text := p->>'division';
    v_ip inet := _ip(p->>'ip');
    s nda_sessions;
    r nda_requests;
BEGIN
    SELECT * INTO s FROM nda_sessions WHERE token_sha256 = v_token FOR UPDATE;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('status', 401);
    END IF;
    SELECT * INTO r FROM nda_requests WHERE id = s.request_id;
    IF s.expires_at <= now() OR s.last_seen_at < now() - interval '1 hour'
       OR r.status <> 'approved' OR r.revoked_at IS NOT NULL OR r.expires_at <= now() THEN
        DELETE FROM nda_sessions WHERE token_sha256 = v_token;
        PERFORM _audit('session_ended', r.id, v_ip, NULL, jsonb_build_object('division', v_div));
        RETURN jsonb_build_object('status', 401);
    END IF;
    IF NOT _hit('content:' || encode(v_token, 'hex'), 600, 300) THEN
        RETURN jsonb_build_object('status', 429);
    END IF;
    UPDATE nda_sessions SET last_seen_at = now() WHERE token_sha256 = v_token;

    IF v_div = 'investors' THEN
        IF NOT r.investor_access THEN
            PERFORM _audit('content_forbidden', r.id, v_ip, NULL, jsonb_build_object('division', v_div));
            RETURN jsonb_build_object('status', 403);
        END IF;
        PERFORM _audit('content_view', r.id, v_ip, NULL, jsonb_build_object('division', v_div));
        RETURN jsonb_build_object('status', 200, 'division', v_div, 'viewer', r.email, 'sections', coalesce(
            (SELECT body->'sections' FROM nda_content WHERE division = 'investors' AND project_id = '_page'), '[]'));
    END IF;

    IF NOT (v_div = ANY(r.approved_divisions)) THEN
        PERFORM _audit('content_forbidden', r.id, v_ip, NULL, jsonb_build_object('division', v_div));
        RETURN jsonb_build_object('status', 403);
    END IF;
    PERFORM _audit('content_view', r.id, v_ip, NULL, jsonb_build_object('division', v_div));
    RETURN jsonb_build_object('status', 200, 'division', v_div, 'viewer', r.email, 'projects', coalesce(
        (SELECT jsonb_object_agg(project_id, body) FROM nda_content WHERE division = v_div), '{}'));
END $$;

-- logout p: {token_sha256, ip}

CREATE OR REPLACE FUNCTION logout(p jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = web, pg_temp AS $$
DECLARE v_req bigint;
BEGIN
    DELETE FROM nda_sessions WHERE token_sha256 = _hex32(p->>'token_sha256') RETURNING request_id INTO v_req;
    IF v_req IS NOT NULL THEN
        PERFORM _audit('logout', v_req, _ip(p->>'ip'), NULL);
    END IF;
    RETURN jsonb_build_object('ok', true);
END $$;

-- ------------------------------------------------------------------ website-enquiry (§4.7)
-- p: name, email, phone, service, division, message, ip -> {result: created|limited}

CREATE OR REPLACE FUNCTION enquiry_add(p jsonb) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = web, pg_temp AS $$
DECLARE
    v_ip inet := _ip(p->>'ip');
    v_id bigint;
BEGIN
    IF NOT _hit('enquiry:ip:' || coalesce(host(v_ip), '?'), 3600, 5) THEN
        PERFORM _audit('enquiry_rate_limited', NULL, v_ip, NULL);
        RETURN jsonb_build_object('result', 'limited');
    END IF;
    INSERT INTO enquiries (name, email, phone, service, division, message, ip)
    VALUES (p->>'name', lower(p->>'email'), coalesce(p->>'phone', ''), p->>'service',
            coalesce(p->>'division', ''), p->>'message', v_ip)
    RETURNING id INTO v_id;
    PERFORM _audit('enquiry', NULL, v_ip, NULL, jsonb_build_object('enquiry_id', v_id));
    RETURN jsonb_build_object('result', 'created', 'id', v_id);
END $$;

-- ------------------------------------------------------------------ nda-retention (§4.10), daily

CREATE OR REPLACE FUNCTION retention(p jsonb DEFAULT '{}') RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = web, pg_temp AS $$
DECLARE
    n_sessions int; n_tokens int; n_ip int; n_never int; n_ended int; n_audit int; n_rate int; n_enq int;
BEGIN
    DELETE FROM nda_sessions WHERE expires_at <= now() OR last_seen_at < now() - interval '1 hour';
    GET DIAGNOSTICS n_sessions = ROW_COUNT;
    DELETE FROM nda_review_tokens WHERE used_at IS NOT NULL OR expires_at <= now();
    GET DIAGNOSTICS n_tokens = ROW_COUNT;
    UPDATE nda_requests SET signed_ip = NULL, signed_ua = NULL
    WHERE signed_at < now() - interval '12 months' AND (signed_ip IS NOT NULL OR signed_ua IS NOT NULL);
    GET DIAGNOSTICS n_ip = ROW_COUNT;
    -- Requests that never became an NDA (Q32)
    DELETE FROM nda_requests WHERE status IN ('pending', 'rejected') AND created_at < now() - interval '12 months';
    GET DIAGNOSTICS n_never = ROW_COUNT;
    -- NDA records: the 3-year term + 2 years from signing (Q11)
    DELETE FROM nda_requests WHERE status IN ('approved', 'revoked') AND signed_at < now() - interval '5 years';
    GET DIAGNOSTICS n_ended = ROW_COUNT;
    DELETE FROM nda_audit WHERE at < now() - interval '12 months';
    GET DIAGNOSTICS n_audit = ROW_COUNT;
    DELETE FROM nda_rate WHERE window_start < now() - interval '12 months';
    GET DIAGNOSTICS n_rate = ROW_COUNT;
    DELETE FROM enquiries WHERE at < now() - interval '12 months';
    GET DIAGNOSTICS n_enq = ROW_COUNT;
    PERFORM _audit('retention', NULL, NULL, NULL, jsonb_build_object(
        'sessions', n_sessions, 'review_tokens', n_tokens, 'ip_nulled', n_ip, 'never_approved', n_never,
        'nda_ended', n_ended, 'audit', n_audit, 'rate', n_rate, 'enquiries', n_enq));
    RETURN (SELECT detail FROM nda_audit WHERE event = 'retention' ORDER BY id DESC LIMIT 1);
END $$;

-- ------------------------------------------------------------------ grants

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA web FROM PUBLIC;
GRANT EXECUTE ON FUNCTION
    submit_nda(jsonb), review_view(jsonb), review_post(jsonb), login_begin(jsonb), login_finish(jsonb),
    content_get(jsonb), logout(jsonb), enquiry_add(jsonb), retention(jsonb)
TO it7q_web;
RESET ROLE;
