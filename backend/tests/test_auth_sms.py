import asyncio
import json
import os
import re
import time
import unittest
from contextlib import asynccontextmanager
from datetime import date, timedelta
from types import SimpleNamespace

from fastapi import HTTPException, Response
from pydantic import ValidationError

from app.auth import challenges, dependencies, sessions, sms, throttle, validation
from app.auth import router as auth_router

PHONE = "+37369000000"
USER_ID = "11111111-1111-1111-1111-111111111111"
REQ = SimpleNamespace(client=SimpleNamespace(host="1.2.3.4"))


class FakeRedis:
    """In-memory Redis with the real command semantics the code relies on, and an
    `await asyncio.sleep(0)` in every command so concurrent coroutines interleave the
    way they do against a network server (a read-modify-write is NOT atomic here)."""

    def __init__(self):
        self.store: dict = {}
        self.ttls: dict = {}

    async def _yield(self):
        await asyncio.sleep(0)

    async def set(self, key, value, ex=None, nx=False, xx=False, keepttl=False):
        await self._yield()
        exists = key in self.store
        if (nx and exists) or (xx and not exists):
            return None
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex
        elif not keepttl:
            self.ttls.pop(key, None)
        return True

    async def get(self, key):
        await self._yield()
        return self.store.get(key)

    async def getdel(self, key):
        await self._yield()
        self.ttls.pop(key, None)
        return self.store.pop(key, None)

    async def delete(self, *keys):
        await self._yield()
        for k in keys:
            self.store.pop(k, None)
            self.ttls.pop(k, None)

    async def incr(self, key):
        await self._yield()
        self.store[key] = str(int(self.store.get(key, 0)) + 1)
        return int(self.store[key])

    async def expire(self, key, seconds):
        await self._yield()
        if key in self.store:  # real Redis: no-op on a missing key
            self.ttls[key] = seconds

    async def ttl(self, key):
        await self._yield()
        if key not in self.store:
            return -2
        return self.ttls.get(key, -1)

    async def sadd(self, key, *vals):
        await self._yield()
        self.store.setdefault(key, set()).update(vals)

    async def srem(self, key, *vals):
        await self._yield()
        self.store.get(key, set()).difference_update(vals)

    async def smembers(self, key):
        await self._yield()
        return set(self.store.get(key, set()))

    async def lpush(self, key, val):
        await self._yield()
        self.store.setdefault(key, []).insert(0, val)

    async def ltrim(self, key, a, b):
        await self._yield()
        self.store[key] = self.store.get(key, [])[a : b + 1]

    async def lrange(self, key, a, b):
        await self._yield()
        return self.store.get(key, [])[a : b + 1]


def run(coro):
    return asyncio.run(coro)


class RedisCase(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self._saved_env = {
            k: os.environ.get(k) for k in ("APP_ENV", "SMS_PROVIDER", "ENABLE_DEV_SMS_OUTBOX")
        }
        os.environ["APP_ENV"] = "development"
        os.environ.pop("SMS_PROVIDER", None)
        os.environ.pop("ENABLE_DEV_SMS_OUTBOX", None)
        self._saved = []
        for mod in (challenges, sessions, throttle, sms, auth_router, dependencies):
            self._saved.append((mod, mod.redis_client))
            mod.redis_client = self.redis

    def tearDown(self):
        for mod, old in self._saved:
            mod.redis_client = old
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def last_code(self, phone=PHONE):
        msg = self.redis.store[f"sms:outbox:{phone}"][0]
        return re.search(r"\b(\d{6})\b", msg).group(1)

    def wrong_code(self, good):
        return "000000" if good != "000000" else "111111"


class ValidationTests(unittest.TestCase):
    def test_name_accepts_diacritics_and_rejects_digits(self):
        self.assertEqual(validation.validate_name("  Ștefan "), "Ștefan")
        self.assertEqual(validation.validate_name("Anne-Marie"), "Anne-Marie")
        self.assertEqual(validation.validate_name("O’Brien"), "O’Brien")
        for bad in ("A", "R2D2", "Jo$", "x" * 51):
            with self.assertRaises(ValueError):
                validation.validate_name(bad)

    def test_name_is_nfc_normalised(self):
        decomposed = "Ștefan"  # S + combining comma below
        self.assertEqual(validation.validate_name(decomposed), "Ștefan")

    def test_phone_normalisation(self):
        for raw in ("+373 69 000 000", "37369000000", "069000000", "00373-69000000"):
            self.assertEqual(validation.normalize_phone(raw), PHONE)
        with self.assertRaises(ValueError):
            validation.normalize_phone("+40712345678")

    def test_dob_bounds(self):
        validation.validate_dob(date(1990, 1, 1))
        with self.assertRaises(ValueError):
            validation.validate_dob(date.today() + timedelta(days=1))
        with self.assertRaises(ValueError):
            validation.validate_dob(date.today().replace(year=date.today().year - 121, day=1))

    def test_password_rules(self):
        validation.validate_password("Str0ng!Passw")
        for bad in (
            "short1!A", "alllowercase1!", "ALLUPPERCASE1!", "NoDigitsHere!",
            "NoSpecial1234", "Password1234", "A1!" + "a" * 130,
        ):
            with self.assertRaises(ValueError):
                validation.validate_password(bad)

    def test_request_models_cap_input_size(self):
        with self.assertRaises(ValidationError):
            auth_router.LoginRequest(phone=PHONE, password="x" * 10_000)
        with self.assertRaises(ValidationError):
            auth_router.LoginRequest(phone="9" * 500, password="x")
        with self.assertRaises(ValidationError):
            auth_router.CodeRequest(challenge_id="a" * 500, code="1")


class ChallengeTests(RedisCase):
    def test_correct_code_consumes_challenge(self):
        cid = run(challenges.start("login", PHONE, "u1"))
        data = run(challenges.verify(cid, "login", self.last_code()))
        self.assertEqual(data["user_id"], "u1")
        with self.assertRaises(HTTPException):
            run(challenges.verify(cid, "login", self.last_code()))
        # Nothing is left behind (challenge, counters).
        self.assertEqual([k for k in self.redis.store if k.startswith("sms:c") or "attempts" in k], [])

    def test_wrong_purpose_and_wrong_code_rejected(self):
        cid = run(challenges.start("login", PHONE, "u1"))
        with self.assertRaises(HTTPException):
            run(challenges.verify(cid, "reset", self.last_code()))
        with self.assertRaises(HTTPException) as ctx:
            run(challenges.verify(cid, "login", self.wrong_code(self.last_code())))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_attempt_cap_burns_challenge(self):
        cid = run(challenges.start("login", PHONE, "u1"))
        good = self.last_code()
        for _ in range(challenges.MAX_ATTEMPTS):
            with self.assertRaises(HTTPException):
                run(challenges.verify(cid, "login", self.wrong_code(good)))
        with self.assertRaises(HTTPException) as ctx:
            run(challenges.verify(cid, "login", good))
        self.assertEqual(ctx.exception.status_code, 429)
        with self.assertRaises(HTTPException):
            run(challenges.verify(cid, "login", good))

    def test_resend_does_not_refill_attempts(self):
        cid = run(challenges.start("login", PHONE, "u1"))
        for _ in range(challenges.MAX_ATTEMPTS):
            with self.assertRaises(HTTPException):
                run(challenges.verify(cid, "login", "000000" if self.last_code() != "000000" else "111111"))
        self.redis.store.pop(f"sms:cooldown:{cid}", None)
        run(challenges.resend(cid))
        with self.assertRaises(HTTPException) as ctx:
            run(challenges.verify(cid, "login", self.last_code()))
        self.assertEqual(ctx.exception.status_code, 429)

    def test_decoy_never_verifies_and_sends_nothing(self):
        cid = run(challenges.start("reset", PHONE, None))
        self.assertNotIn(f"sms:outbox:{PHONE}", self.redis.store)
        with self.assertRaises(HTTPException):
            run(challenges.verify(cid, "reset", "123456"))

    def test_resend_cooldown_and_cap(self):
        cid = run(challenges.start("signup", PHONE, "u1"))
        with self.assertRaises(HTTPException):  # cooldown
            run(challenges.resend(cid))
        for _ in range(challenges.MAX_RESENDS):
            self.redis.store.pop(f"sms:cooldown:{cid}", None)
            run(challenges.resend(cid))
        self.redis.store.pop(f"sms:cooldown:{cid}", None)
        with self.assertRaises(HTTPException) as ctx:
            run(challenges.resend(cid))
        self.assertEqual(ctx.exception.status_code, 429)

    def test_malformed_input_is_a_clean_400(self):
        cid = run(challenges.start("login", PHONE, "u1"))
        for bad_id in ("", "short", "x" * 200, "\ud800" * 30, "../../etc/passwd" + "a" * 10):
            with self.assertRaises(HTTPException) as ctx:
                run(challenges.verify(bad_id, "login", "123456"))
            self.assertEqual(ctx.exception.status_code, 400)
        for bad_code in ("\ud800", "12345", "1234567", "abcdef", " ", "１２３４５６"):
            with self.assertRaises(HTTPException) as ctx:
                run(challenges.verify(cid, "login", bad_code))
            self.assertIn(ctx.exception.status_code, (400, 429))

    # --- concurrency: these fail against a read-modify-write implementation ---
    def test_concurrent_wrong_guesses_are_capped(self):
        async def main():
            cid = await challenges.start("reset", PHONE, "u1")
            good = self.last_code()
            wrong = self.wrong_code(good)
            results = await asyncio.gather(
                *(challenges.verify(cid, "reset", wrong) for _ in range(200)),
                return_exceptions=True,
            )
            codes = [r.status_code for r in results]
            # At most MAX_ATTEMPTS guesses are ever evaluated; the rest are refused.
            self.assertEqual(codes.count(400), challenges.MAX_ATTEMPTS)
            self.assertEqual(codes.count(429), 200 - challenges.MAX_ATTEMPTS)
            # And the correct code no longer works afterwards.
            with self.assertRaises(HTTPException):
                await challenges.verify(cid, "reset", good)

        run(main())

    def test_concurrent_correct_submissions_only_one_wins(self):
        async def main():
            cid = await challenges.start("login", PHONE, "u1")
            good = self.last_code()
            results = await asyncio.gather(
                *(challenges.verify(cid, "login", good) for _ in range(10)),
                return_exceptions=True,
            )
            winners = [r for r in results if isinstance(r, dict)]
            self.assertEqual(len(winners), 1)

        run(main())

    def test_concurrent_resends_send_once(self):
        async def main():
            cid = await challenges.start("signup", PHONE, "u1")
            before = len(self.redis.store[f"sms:outbox:{PHONE}"])
            self.redis.store.pop(f"sms:cooldown:{cid}", None)
            results = await asyncio.gather(
                *(challenges.resend(cid) for _ in range(20)), return_exceptions=True
            )
            ok = [r for r in results if r is None]
            self.assertEqual(len(ok), 1)
            self.assertEqual(len(self.redis.store[f"sms:outbox:{PHONE}"]), before + 1)

        run(main())

    def test_failed_guess_cannot_resurrect_a_consumed_challenge(self):
        async def main():
            cid = await challenges.start("login", PHONE, "u1")
            good = self.last_code()
            wrong = self.wrong_code(good)
            await asyncio.gather(
                challenges.verify(cid, "login", good),
                challenges.verify(cid, "login", wrong),
                challenges.verify(cid, "login", wrong),
                return_exceptions=True,
            )
            self.assertNotIn(f"sms:challenge:{cid}", self.redis.store)
            with self.assertRaises(HTTPException):
                await challenges.verify(cid, "login", good)

        run(main())

    def test_resend_cannot_resurrect_a_consumed_challenge(self):
        async def main():
            cid = await challenges.start("login", PHONE, "u1")
            good = self.last_code()
            self.redis.store.pop(f"sms:cooldown:{cid}", None)
            await asyncio.gather(
                challenges.verify(cid, "login", good),
                challenges.resend(cid),
                return_exceptions=True,
            )
            self.assertNotIn(f"sms:challenge:{cid}", self.redis.store)

        run(main())


class SessionTests(RedisCase):
    def test_create_touch_destroy_all(self):
        s1 = run(sessions.create("u1"))
        s2 = run(sessions.create("u1"))
        self.assertEqual(self.redis.ttls[f"session:{s1}"], sessions.SESSION_IDLE_TTL_SECONDS)
        self.redis.ttls[f"session:{s1}"] = 5
        run(sessions.touch(s1, "u1"))
        self.assertEqual(self.redis.ttls[f"session:{s1}"], 15 * 60)
        self.assertEqual(self.redis.ttls["user_sessions:u1"], 24 * 60 * 60)
        run(sessions.destroy_all("u1"))
        self.assertNotIn(f"session:{s1}", self.redis.store)
        self.assertNotIn(f"session:{s2}", self.redis.store)

    def test_touch_repairs_a_missing_index_entry(self):
        sid = "legacy-sid"
        self.redis.store[f"session:{sid}"] = "{}"
        run(sessions.touch(sid, "u1"))
        self.assertIn(sid, self.redis.store["user_sessions:u1"])

    def context(self, payload):
        self.redis.store["session:sid"] = payload
        gen = dependencies.get_request_context(session_id="sid")
        return run(gen.__anext__())

    def test_session_older_than_cap_is_rejected_despite_activity(self):
        old = int(time.time()) - sessions.SESSION_MAX_AGE_SECONDS - 5
        with self.assertRaises(HTTPException) as ctx:
            self.context(json.dumps({"user_id": USER_ID, "created_at": old}))
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertNotIn("session:sid", self.redis.store)

    def test_legacy_session_without_created_at_is_rejected(self):
        for payload in (json.dumps({"user_id": USER_ID}), USER_ID):
            with self.assertRaises(HTTPException) as ctx:
                self.context(payload)
            self.assertEqual(ctx.exception.status_code, 401)
            self.redis.store.pop("session:sid", None)


class SmsFailClosedTests(RedisCase):
    def test_dev_outbox_requires_explicit_opt_in(self):
        self.assertFalse(sms.mock_enabled())  # development alone is not enough
        os.environ["ENABLE_DEV_SMS_OUTBOX"] = "true"
        self.assertTrue(sms.mock_enabled())

    def test_unset_app_env_is_production(self):
        os.environ.pop("APP_ENV")
        os.environ["ENABLE_DEV_SMS_OUTBOX"] = "true"
        self.assertFalse(sms.mock_enabled())
        with self.assertRaises(RuntimeError):
            sms.get_sms_provider()

    def test_mock_never_logs_the_code(self):
        with self.assertLogs("medvault.sms", level="INFO") as logs:
            run(sms.MockSmsProvider().send(PHONE, "MedVault code: 123456."))
        self.assertNotIn("123456", "".join(logs.output))
        self.assertNotIn(PHONE, "".join(logs.output))


class ThrottleTests(RedisCase):
    def test_lockout_after_failures(self):
        for _ in range(throttle.LOGIN_MAX_FAILURES):
            run(throttle.count_login_attempt("p"))
        run(throttle.ensure_not_locked("p"))  # at the limit, not over it
        with self.assertRaises(HTTPException) as ctx:
            run(throttle.count_login_attempt("p"))
        self.assertEqual(ctx.exception.status_code, 429)
        with self.assertRaises(HTTPException):
            run(throttle.ensure_not_locked("p"))
        run(throttle.clear_failures("p"))
        run(throttle.ensure_not_locked("p"))

    def test_concurrent_attempts_are_capped(self):
        async def main():
            results = await asyncio.gather(
                *(throttle.count_login_attempt("p") for _ in range(50)),
                return_exceptions=True,
            )
            allowed = [r for r in results if r is None]
            self.assertEqual(len(allowed), throttle.LOGIN_MAX_FAILURES)

        run(main())

    def test_counter_that_lost_its_ttl_heals(self):
        self.redis.store["k"] = str(10)  # no TTL: as if a crash skipped EXPIRE
        with self.assertRaises(HTTPException):
            run(throttle.hit("k", 3, 60))
        self.assertEqual(self.redis.ttls["k"], 60)

    def test_hit_limit(self):
        for _ in range(3):
            run(throttle.hit("k", 3, 60))
        with self.assertRaises(HTTPException):
            run(throttle.hit("k", 3, 60))


class FakeDb:
    """Async-context-manager session used for the sign-up / reset SQL calls."""

    def __init__(self, scalar=None, fail=False):
        self.scalar = scalar
        self.fail = fail
        self.statements = []
        self.commits = 0

    async def execute(self, statement, params=None):
        self.statements.append((str(statement), params))
        if self.fail:
            raise RuntimeError("db down")
        scalar = self.scalar
        return SimpleNamespace(scalar_one=lambda: scalar)

    async def commit(self):
        self.commits += 1


class AuthFlowCase(RedisCase):
    def setUp(self):
        super().setUp()
        self.hasher = auth_router._hasher
        self.row = SimpleNamespace(
            id=USER_ID,
            password_hash=self.hasher.hash("Str0ng!Passw"),
            status="active",
        )
        self.audits = []
        self.db = FakeDb(scalar=USER_ID)
        self._orig = (
            auth_router._lookup,
            auth_router._audit,
            auth_router._current_user,
            auth_router.get_session_factory,
        )

        async def lookup(phone):
            return self.row if phone == PHONE else None

        async def audit(action, outcome, user_id=None, metadata=None):
            self.audits.append((action, outcome))

        async def current_user(user_id):
            return auth_router.CurrentUser(
                id=user_id, phone=PHONE, status="active", created_at="2026-01-01T00:00:00Z"
            )

        @asynccontextmanager
        async def session():
            yield self.db

        auth_router._lookup, auth_router._audit, auth_router._current_user = (
            lookup, audit, current_user,
        )
        auth_router.get_session_factory = lambda: session

    def tearDown(self):
        (
            auth_router._lookup,
            auth_router._audit,
            auth_router._current_user,
            auth_router.get_session_factory,
        ) = self._orig
        super().tearDown()

    async def flush_background(self):
        await asyncio.gather(*list(auth_router._background))


class LoginFlowTests(AuthFlowCase):
    def login(self, phone=PHONE, password="Str0ng!Passw"):
        return auth_router.login(auth_router.LoginRequest(phone=phone, password=password), REQ)

    def test_password_alone_issues_no_session(self):
        resp = run(self.login("069000000"))
        self.assertTrue(resp.challenge_id)
        self.assertFalse([k for k in self.redis.store if k.startswith("session:")])

    def test_full_flow_issues_session_after_code(self):
        resp = run(self.login())
        response = Response()
        run(auth_router.login_verify(
            auth_router.CodeRequest(challenge_id=resp.challenge_id, code=self.last_code()), response
        ))
        self.assertIn("session_id=", response.headers["set-cookie"])
        self.assertTrue([k for k in self.redis.store if k.startswith("session:")])
        self.assertIn(("auth.login", "success"), self.audits)
        self.assertNotIn(f"auth:fail:{PHONE}", self.redis.store)

    def test_bad_password_is_generic_and_locks_out(self):
        for _ in range(throttle.LOGIN_MAX_FAILURES):
            with self.assertRaises(HTTPException) as ctx:
                run(self.login(password="wrong"))
            self.assertEqual(ctx.exception.detail, auth_router.INVALID_CREDENTIALS)
        with self.assertRaises(HTTPException) as ctx:
            run(self.login(password="wrong"))
        self.assertEqual(ctx.exception.status_code, 429)

    def test_concurrent_password_guesses_are_capped(self):
        async def main():
            results = await asyncio.gather(
                *(self.login(password="wrong") for _ in range(30)), return_exceptions=True
            )
            statuses = [r.status_code for r in results]
            self.assertEqual(statuses.count(401), throttle.LOGIN_MAX_FAILURES)
            self.assertEqual(statuses.count(429), 30 - throttle.LOGIN_MAX_FAILURES)

        run(main())

    def test_unknown_phone_same_error(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self.login(phone="+37369111111", password="x"))
        self.assertEqual(ctx.exception.detail, auth_router.INVALID_CREDENTIALS)

    def test_unnormalisable_phone_is_generic_401_and_touches_no_keys(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self.login(phone="not a phone ☃", password="x"))
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(ctx.exception.detail, auth_router.INVALID_CREDENTIALS)
        self.assertFalse([k for k in self.redis.store if "phone" in k or "☃" in k])

    def test_pending_user_cannot_log_in(self):
        self.row.status = "pending_verification"
        with self.assertRaises(HTTPException) as ctx:
            run(self.login())
        self.assertEqual(ctx.exception.detail, auth_router.INVALID_CREDENTIALS)

    def test_wrong_codes_count_toward_lockout_even_when_challenge_burns(self):
        resp = run(self.login())
        good = self.last_code()
        for _ in range(challenges.MAX_ATTEMPTS + 1):
            with self.assertRaises(HTTPException):
                run(auth_router.login_verify(
                    auth_router.CodeRequest(challenge_id=resp.challenge_id, code=self.wrong_code(good)),
                    Response(),
                ))
        # 1 password attempt + 6 wrong codes (including the one that burned the challenge).
        self.assertGreaterEqual(int(self.redis.store[f"auth:fail:{PHONE}"]), throttle.LOGIN_MAX_FAILURES)

    def test_locked_out_phone_cannot_finish_an_open_challenge(self):
        resp = run(self.login())
        self.redis.store[f"auth:fail:{PHONE}"] = str(throttle.LOGIN_MAX_FAILURES + 1)
        self.redis.ttls[f"auth:fail:{PHONE}"] = 600
        with self.assertRaises(HTTPException) as ctx:
            run(auth_router.login_verify(
                auth_router.CodeRequest(challenge_id=resp.challenge_id, code=self.last_code()),
                Response(),
            ))
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertFalse([k for k in self.redis.store if k.startswith("session:")])

    def test_logout_destroys_session(self):
        sid = run(sessions.create(USER_ID))
        run(auth_router.logout(Response(), session_id=sid))
        self.assertNotIn(f"session:{sid}", self.redis.store)
        self.assertEqual(self.redis.store[f"user_sessions:{USER_ID}"], set())


class SignupFlowTests(AuthFlowCase):
    BODY = dict(
        first_name="Maria", last_name="Rusu", phone="069000000",
        date_of_birth=date(1990, 5, 17), password="Str0ng!Passw",
    )

    def signup(self, **over):
        return auth_router.signup(auth_router.SignupRequest(**{**self.BODY, **over}), REQ)

    def test_free_phone_gets_a_real_challenge_and_an_sms(self):
        async def main():
            resp = await self.signup()
            await self.flush_background()
            return resp

        resp = run(main())
        self.assertTrue(resp.challenge_id)
        self.assertEqual(len(self.redis.store[f"sms:outbox:{PHONE}"]), 1)
        self.assertEqual(self.db.commits, 1)
        # The SQL receives the normalised phone and a hash, never the plaintext password.
        _, params = self.db.statements[0]
        self.assertEqual(params["phone"], PHONE)
        self.assertNotIn("Str0ng!Passw", json.dumps(params, default=str))
        self.assertTrue(params["hash"].startswith("$argon2id$"))

    def test_taken_phone_is_indistinguishable_from_a_free_one(self):
        async def main():
            free = await self.signup()
            await self.flush_background()
            self.db.scalar = None  # auth_register_user -> NULL: active account owns it
            taken = await self.signup()
            await self.flush_background()
            return free, taken

        free, taken = run(main())
        self.assertEqual(type(free), type(taken))
        self.assertEqual(free.expires_in, taken.expires_in)
        self.assertNotEqual(free.challenge_id, taken.challenge_id)
        # Only the real sign-up sent an SMS, and the decoy can never be verified.
        self.assertEqual(len(self.redis.store[f"sms:outbox:{PHONE}"]), 1)
        with self.assertRaises(HTTPException):
            run(auth_router.signup_verify(
                auth_router.CodeRequest(challenge_id=taken.challenge_id, code=self.last_code()),
                Response(),
            ))

    def test_field_errors_are_collected_and_nothing_is_created(self):
        with self.assertRaises(HTTPException) as ctx:
            run(self.signup(first_name="R2", phone="12", password="weak"))
        self.assertEqual(ctx.exception.status_code, 422)
        errors = ctx.exception.detail["errors"]
        self.assertEqual(set(errors), {"first_name", "phone", "password"})
        self.assertEqual(self.db.statements, [])

    def test_signup_is_rate_limited_per_ip(self):
        async def many():
            outcomes = []
            for _ in range(12):
                try:
                    await self.signup(first_name="R2")
                except HTTPException as e:
                    outcomes.append(e.status_code)
            return outcomes

        outcomes = run(many())
        self.assertEqual(outcomes.count(422), 10)
        self.assertEqual(outcomes.count(429), 2)

    def test_verify_activates_and_opens_a_session(self):
        async def main():
            resp = await self.signup()
            await self.flush_background()
            response = Response()
            user = await auth_router.signup_verify(
                auth_router.CodeRequest(challenge_id=resp.challenge_id, code=self.last_code()),
                response,
            )
            return user, response

        user, response = run(main())
        self.assertEqual(user.status, "active")
        self.assertIn("session_id=", response.headers["set-cookie"])
        self.assertTrue(any("auth_activate_user" in s for s, _ in self.db.statements))
        self.assertIn(("auth.phone_verified", "success"), self.audits)


class PasswordResetTests(AuthFlowCase):
    def reset_request(self, phone=PHONE):
        return auth_router.password_reset_request(
            auth_router.PasswordResetRequest(phone=phone), REQ
        )

    def test_request_has_the_same_shape_for_unknown_and_junk_phones(self):
        async def main():
            known = await self.reset_request()
            await self.flush_background()
            unknown = await self.reset_request("+37369111111")
            junk = await self.reset_request("☃☃☃")
            return known, unknown, junk

        known, unknown, junk = run(main())
        self.assertEqual(known.expires_in, unknown.expires_in)
        self.assertEqual(known.expires_in, junk.expires_in)
        self.assertNotIn("sms:outbox:+37369111111", self.redis.store)
        self.assertFalse([k for k in self.redis.store if "☃" in k])

    def test_full_reset_signs_out_everywhere_and_token_is_single_use(self):
        async def main():
            sid = await sessions.create(USER_ID)
            resp = await self.reset_request()
            await self.flush_background()
            token = (
                await auth_router.password_reset_verify(
                    auth_router.CodeRequest(challenge_id=resp.challenge_id, code=self.last_code())
                )
            ).reset_token
            body = auth_router.PasswordResetConfirm(reset_token=token, new_password="N3w!Password")
            await auth_router.password_reset_confirm(body)
            with self.assertRaises(HTTPException) as ctx:
                await auth_router.password_reset_confirm(body)
            return sid, ctx.exception.status_code

        sid, replay_status = run(main())
        self.assertEqual(replay_status, 400)
        self.assertNotIn(f"session:{sid}", self.redis.store)
        self.assertTrue(any("auth_set_password" in s for s, _ in self.db.statements))
        self.assertIn(("auth.password_reset", "success"), self.audits)

    def test_weak_new_password_keeps_the_token(self):
        self.redis.store["auth:reset_token:tok"] = USER_ID
        with self.assertRaises(HTTPException) as ctx:
            run(auth_router.password_reset_confirm(
                auth_router.PasswordResetConfirm(reset_token="tok", new_password="weak")
            ))
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("auth:reset_token:tok", self.redis.store)

    def test_db_failure_gives_the_token_back(self):
        self.redis.store["auth:reset_token:tok"] = USER_ID
        self.db.fail = True
        with self.assertRaises(RuntimeError):
            run(auth_router.password_reset_confirm(
                auth_router.PasswordResetConfirm(reset_token="tok", new_password="N3w!Password")
            ))
        self.assertEqual(self.redis.store["auth:reset_token:tok"], USER_ID)


if __name__ == "__main__":
    unittest.main()
