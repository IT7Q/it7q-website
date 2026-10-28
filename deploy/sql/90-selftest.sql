-- IT7Q website database: self-test (DEPLOY.md step 2). Run as the superuser in it7q_web.
-- Everything happens inside one transaction that is ROLLED BACK at the end: nothing is kept.
-- Prints "NOTICE: self-test passed" twice, or stops at the first failed ASSERT.

\set ON_ERROR_STOP on
BEGIN;

-- Part 1, as n8n's role: proves the grants as well as the logic.
SET LOCAL ROLE it7q_web;
DO $$
DECLARE
    r jsonb;
    v_id bigint;
    rev text := repeat('b', 64);
    s1 text := repeat('c', 64);
    s2 text := repeat('d', 64);
    pw text := 'scrypt$16384$8$1$c2VsZnRlc3Q=$c2VsZnRlc3Q=';
    nda jsonb := jsonb_build_object('name', 'Self Test', 'email', 'SelfTest@example.invalid', 'org', '',
        'reason', 'self-test', 'wants_investor', true, 'nda_version', '1.0', 'nda_sha256', repeat('0', 64),
        'signature', 'Self Test', 'ip', '192.0.2.1', 'ua', 'selftest', 'review_sha256', rev);
    me jsonb := jsonb_build_object('email', 'selftest@example.invalid', 'ip', '192.0.2.1', 'ua', 'selftest');
BEGIN
    -- No direct table access for n8n
    BEGIN
        PERFORM count(*) FROM web.nda_requests;
        RAISE EXCEPTION 'it7q_web can read nda_requests directly';
    EXCEPTION WHEN insufficient_privilege THEN NULL;
    END;

    r := web.submit_nda(nda);
    ASSERT r->>'result' = 'created', 'submit: ' || r::text;
    v_id := (r->>'request_id')::bigint;
    r := web.submit_nda(nda || jsonb_build_object('review_sha256', repeat('e', 64)));
    ASSERT r->>'result' = 'duplicate', 'duplicate: ' || r::text;

    r := web.review_view(jsonb_build_object('review_sha256', rev));
    ASSERT r->>'mode' = 'request' AND r->'request'->>'email' = 'selftest@example.invalid', 'view: ' || r::text;
    r := web.review_view('{}');
    ASSERT r->>'mode' = 'list', 'list: ' || r::text;
    ASSERT NOT (r::text LIKE '%scrypt%'), 'list leaks a password hash';

    r := web.login_begin(me);
    ASSERT r->>'password_hash' IS NULL, 'pending request has a password: ' || r::text;

    r := web.review_post(jsonb_build_object('action', 'approve', 'review_sha256', rev, 'divisions', '[]'::jsonb,
                                            'password_hash', pw, 'actor', 'selftest'));
    ASSERT NOT (r->>'ok')::boolean, 'approved with no divisions';
    r := web.review_post(jsonb_build_object('action', 'approve', 'review_sha256', rev,
                                            'divisions', jsonb_build_array('msp', 'opus', 'nope'),
                                            'investor', false, 'password_hash', pw, 'actor', 'selftest'));
    ASSERT (r->>'ok')::boolean AND r->'divisions' = '["msp", "opus"]'::jsonb, 'approve: ' || r::text;
    ASSERT (r->>'expires_at')::timestamptz > now() + interval '1094 days', 'NDA term is not 3 years';
    r := web.review_post(jsonb_build_object('action', 'approve', 'review_sha256', rev,
                                            'divisions', jsonb_build_array('msp'), 'password_hash', pw));
    ASSERT NOT (r->>'ok')::boolean, 'review link worked twice';

    r := web.login_begin(me);
    ASSERT NOT (r->>'locked')::boolean AND r->>'password_hash' = pw, 'login_begin: ' || r::text;
    r := web.login_finish(me || jsonb_build_object('ok', true, 'token_sha256', s1));
    ASSERT r->>'result' = 'ok' AND NOT (r->>'investor')::boolean, 'login: ' || r::text;

    r := web.content_get(jsonb_build_object('token_sha256', s1, 'division', 'msp'));
    ASSERT (r->>'status')::int = 200 AND r->>'viewer' = 'selftest@example.invalid', 'msp: ' || r::text;
    r := web.content_get(jsonb_build_object('token_sha256', s1, 'division', 'fabricus'));
    ASSERT (r->>'status')::int = 403, 'fabricus should be out of scope: ' || r::text;
    r := web.content_get(jsonb_build_object('token_sha256', s1, 'division', 'investors'));
    ASSERT (r->>'status')::int = 403, 'investors without access: ' || r::text;
    r := web.review_post(jsonb_build_object('action', 'investor_on', 'request_id', v_id, 'actor', 'selftest'));
    ASSERT (r->>'ok')::boolean, 'investor_on: ' || r::text;
    r := web.content_get(jsonb_build_object('token_sha256', s1, 'division', 'investors'));
    ASSERT (r->>'status')::int = 200 AND jsonb_typeof(r->'sections') = 'array', 'investors: ' || r::text;

    r := web.logout(jsonb_build_object('token_sha256', s1));
    r := web.content_get(jsonb_build_object('token_sha256', s1, 'division', 'msp'));
    ASSERT (r->>'status')::int = 401, 'token alive after logout: ' || r::text;

    r := web.login_finish(me || jsonb_build_object('ok', true, 'token_sha256', s2));
    r := web.review_post(jsonb_build_object('action', 'revoke', 'request_id', v_id, 'actor', 'selftest'));
    ASSERT (r->>'ok')::boolean, 'revoke: ' || r::text;
    r := web.content_get(jsonb_build_object('token_sha256', s2, 'division', 'msp'));
    ASSERT (r->>'status')::int = 401, 'session alive after revoke: ' || r::text;
    r := web.login_begin(me);
    ASSERT r->>'password_hash' IS NULL, 'revoked NDA can still log in';

    FOR i IN 1..5 LOOP
        r := web.login_finish(jsonb_build_object('email', 'nobody@example.invalid', 'ok', false,
                                                 'token_sha256', repeat('f', 64), 'ip', '192.0.2.9'));
        ASSERT r->>'result' = 'failed', 'bad login accepted';
    END LOOP;
    r := web.login_begin(jsonb_build_object('email', 'nobody@example.invalid', 'ip', '192.0.2.9'));
    ASSERT (r->>'locked')::boolean, 'no lockout after 5 failures: ' || r::text;

    r := web.enquiry_add(jsonb_build_object('name', 'Self Test', 'email', 'selftest@example.invalid',
        'service', 'other', 'division', '', 'message', 'self-test', 'ip', '192.0.2.1'));
    ASSERT r->>'result' = 'created', 'enquiry: ' || r::text;
    RAISE NOTICE 'self-test passed (functions, as it7q_web)';
END $$;

-- Part 2, as the owner: retention needs back-dated rows, which only the owner can insert.
SET LOCAL ROLE it7q_web_owner;
DO $$
DECLARE r jsonb;
BEGIN
    INSERT INTO web.nda_requests (email, name, reason, nda_version, nda_sha256, signature_text, signed_ip, signed_ua,
                                  status, signed_at, created_at)
    VALUES ('old-approved@example.invalid', 'Old', 'x', '1.0', repeat('0', 64), 'Old', '192.0.2.2', 'ua',
            'approved', now() - interval '5 years 1 day', now() - interval '5 years 1 day'),
           ('old-pending@example.invalid', 'Old', 'x', '1.0', repeat('0', 64), 'Old', '192.0.2.3', 'ua',
            'pending', now() - interval '13 months', now() - interval '13 months'),
           ('mid-approved@example.invalid', 'Mid', 'x', '1.0', repeat('0', 64), 'Mid', '192.0.2.4', 'ua',
            'approved', now() - interval '13 months', now() - interval '13 months'),
           ('new-pending@example.invalid', 'New', 'x', '1.0', repeat('0', 64), 'New', '192.0.2.5', 'ua',
            'pending', now() - interval '11 months', now() - interval '11 months');
    INSERT INTO web.nda_audit (at, event) VALUES (now() - interval '13 months', 'old');
    INSERT INTO web.enquiries (at, name, email, service, message) VALUES (now() - interval '13 months', 'Old', 'o@x.invalid', 'other', 'x');

    r := web.retention('{}');
    ASSERT NOT EXISTS (SELECT 1 FROM web.nda_requests WHERE email = 'old-approved@example.invalid'), 'NDA past term + 2 years kept';
    ASSERT NOT EXISTS (SELECT 1 FROM web.nda_requests WHERE email = 'old-pending@example.invalid'), 'old pending request kept';
    ASSERT EXISTS (SELECT 1 FROM web.nda_requests WHERE email = 'mid-approved@example.invalid'
                   AND signed_ip IS NULL AND signed_ua IS NULL), 'IP/UA not nulled at 12 months, or record deleted';
    ASSERT EXISTS (SELECT 1 FROM web.nda_requests WHERE email = 'new-pending@example.invalid'
                   AND signed_ip IS NOT NULL), 'recent request touched';
    ASSERT NOT EXISTS (SELECT 1 FROM web.nda_audit WHERE event = 'old'), 'old audit row kept';
    ASSERT NOT EXISTS (SELECT 1 FROM web.enquiries WHERE email = 'o@x.invalid'), 'old enquiry kept';
    RAISE NOTICE 'self-test passed (retention: %)', r;
END $$;

ROLLBACK;
