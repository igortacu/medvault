import asyncio
import importlib
import os
import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from app.main import create_app
from app.security import rate_limit
from tests.test_auth_sms import PHONE, AuthFlowCase, FakeRedis, run

institutions_router = importlib.import_module("app.institutions.router")
documents_router = importlib.import_module("app.documents.router")

IP = "1.2.3.4"
LIMIT = rate_limit.Limit(name="test", limit=3, window=600, cooldown=900)


class EnforceTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self._saved = rate_limit.redis_client
        rate_limit.redis_client = self.redis

    def tearDown(self):
        rate_limit.redis_client = self._saved

    def hit(self, limit=LIMIT, account=PHONE, ip=IP):
        run(rate_limit.enforce(limit, account=account, ip=ip))

    def test_over_the_limit_starts_a_cooldown_with_retry_after(self):
        for _ in range(LIMIT.limit):
            self.hit()
        with self.assertRaises(HTTPException) as ctx:
            self.hit()
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(ctx.exception.headers["Retry-After"], "900")
        self.assertEqual(ctx.exception.detail, rate_limit.TOO_MANY)

    def test_requests_during_the_cooldown_are_not_counted(self):
        for _ in range(LIMIT.limit + 1):
            try:
                self.hit()
            except HTTPException:
                pass
        counter = next(k for k in self.redis.store if ":count:" in k)
        before = self.redis.store[counter]
        for _ in range(5):
            with self.assertRaises(HTTPException):
                self.hit()
        self.assertEqual(self.redis.store[counter], before)

    def test_cooldown_ends_and_the_budget_returns(self):
        for _ in range(LIMIT.limit + 1):
            try:
                self.hit()
            except HTTPException:
                pass
        # Both keys expire (the window is shorter than the cooldown).
        self.redis.store.clear()
        self.redis.ttls.clear()
        self.hit()

    def test_account_and_ip_are_counted_together(self):
        for _ in range(LIMIT.limit):
            self.hit()
        self.hit(ip="5.6.7.8")
        self.hit(account="+37369111111")
        with self.assertRaises(HTTPException):
            self.hit()

    def test_no_cooldown_waits_for_the_window(self):
        limit = rate_limit.Limit(name="w", limit=1, window=3600, cooldown=0)
        self.hit(limit)
        with self.assertRaises(HTTPException) as ctx:
            self.hit(limit)
        self.assertEqual(ctx.exception.headers["Retry-After"], "3600")
        self.assertFalse([k for k in self.redis.store if ":cooldown:" in k])

    def test_concurrent_burst_is_capped(self):
        async def burst():
            return await asyncio.gather(
                *(rate_limit.enforce(LIMIT, account=PHONE, ip=IP) for _ in range(40)),
                return_exceptions=True,
            )

        results = run(burst())
        self.assertEqual(results.count(None), LIMIT.limit)

    def test_keys_and_logs_never_hold_the_account_or_ip(self):
        with self.assertLogs("medvault.rate_limit", "WARNING") as logs:
            for _ in range(LIMIT.limit + 3):
                try:
                    self.hit()
                except HTTPException:
                    pass
        self.assertEqual(len(logs.records), 1)  # logged once per cooldown, not per hit
        record = logs.records[0]
        self.assertEqual(record.limit, "test")
        text = " ".join([*self.redis.store, logs.output[0], str(vars(record))])
        self.assertNotIn(PHONE, text)
        self.assertNotIn(IP, text)

    def test_counter_that_lost_its_ttl_heals(self):
        self.hit()
        counter = next(iter(self.redis.store))
        self.redis.ttls.pop(counter)
        for _ in range(LIMIT.limit):
            try:
                self.hit()
            except HTTPException:
                pass
        self.assertEqual(self.redis.ttls[counter], LIMIT.window)


class ConfigurationTests(unittest.TestCase):
    def test_defaults(self):
        self.assertEqual(
            (rate_limit.LOGIN.limit, rate_limit.LOGIN.window, rate_limit.LOGIN.cooldown),
            (5, 900, 900),
        )
        self.assertEqual(rate_limit.PASSWORD_RESET, rate_limit.Limit("password_reset", 5, 900, 900))
        self.assertEqual(rate_limit.SMS_CODE, rate_limit.Limit("sms_code", 5, 900, 900))
        self.assertEqual((rate_limit.INSTITUTION_CONNECT.limit, rate_limit.INSTITUTION_CONNECT.window), (10, 3600))
        self.assertEqual((rate_limit.DOCUMENT_UPLOAD.limit, rate_limit.DOCUMENT_UPLOAD.window), (30, 3600))
        self.assertEqual((rate_limit.EXPORT.limit, rate_limit.EXPORT.window), (5, 3600))

    def test_env_overrides_and_ignores_junk(self):
        env = {
            "RATE_LIMIT_DEMO_LIMIT": "7",
            "RATE_LIMIT_DEMO_WINDOW_SECONDS": "60",
            "RATE_LIMIT_DEMO_COOLDOWN_SECONDS": "not-a-number",
        }
        saved = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            limit = rate_limit.configured("demo", 1, 10, 20)
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        self.assertEqual(limit, rate_limit.Limit("demo", 7, 60, 20))


class RouteWiringTests(unittest.TestCase):
    def dependencies_of(self, path, method="POST"):
        app = create_app()
        route = next(
            r for r in app.routes
            if getattr(r, "path", None) == path and method in r.methods
        )
        return [d.call for d in route.dependant.dependencies]

    def test_connect_routes_share_the_connect_limit(self):
        for path in (
            "/api/v1/institutions/connect",
            "/api/v1/institutions/{institution_id}/connect",
        ):
            self.assertIn(institutions_router.limit_connect, self.dependencies_of(path))

    def test_upload_is_limited(self):
        self.assertIn(documents_router.limit_upload, self.dependencies_of("/documents/upload"))

    def test_dependency_keys_on_the_signed_in_account(self):
        redis = FakeRedis()
        saved, rate_limit.redis_client = rate_limit.redis_client, redis
        try:
            dependency = rate_limit.limited(rate_limit.Limit("dep", 1, 60, 0))
            request = SimpleNamespace(client=SimpleNamespace(host=IP))
            run(dependency(request, SimpleNamespace(user_id="u1")))
            run(dependency(request, SimpleNamespace(user_id="u2")))
            with self.assertRaises(HTTPException):
                run(dependency(request, SimpleNamespace(user_id="u1")))
        finally:
            rate_limit.redis_client = saved


class AuthLimitTests(AuthFlowCase):
    REQ = SimpleNamespace(client=SimpleNamespace(host=IP))

    def test_login_is_limited_even_when_every_attempt_succeeds(self):
        async def logins():
            outcomes = []
            for _ in range(rate_limit.LOGIN.limit + 1):
                try:
                    await self.login_once()
                    outcomes.append(200)
                except HTTPException as e:
                    outcomes.append((e.status_code, e.headers.get("Retry-After")))
            return outcomes

        outcomes = run(logins())
        self.assertEqual(outcomes[:-1], [200] * rate_limit.LOGIN.limit)
        self.assertEqual(outcomes[-1], (429, str(rate_limit.LOGIN.cooldown)))

    async def login_once(self):
        from app.auth import router as auth_router

        resp = await auth_router.login(
            auth_router.LoginRequest(phone=PHONE, password="Str0ng!Passw"), self.REQ
        )
        # Successful sign-ins clear the failure counter, so only the new limit applies.
        await auth_router.throttle.clear_failures(PHONE)
        return resp

    def test_code_entry_is_limited_per_phone(self):
        from app.auth import router as auth_router

        async def guesses():
            resp = await self.login_once()
            statuses = []
            for _ in range(rate_limit.SMS_CODE.limit + 1):
                try:
                    await auth_router.sms_resend(
                        auth_router.ChallengeRequest(challenge_id=resp.challenge_id), self.REQ
                    )
                except HTTPException as e:
                    statuses.append((e.status_code, e.headers and e.headers.get("Retry-After")))
            return statuses

        statuses = run(guesses())
        self.assertEqual(statuses[-1], (429, str(rate_limit.SMS_CODE.cooldown)))

    def test_password_reset_is_limited(self):
        from app.auth import router as auth_router

        async def requests():
            outcomes = []
            for _ in range(rate_limit.PASSWORD_RESET.limit + 1):
                try:
                    await auth_router.password_reset_request(
                        auth_router.PasswordResetRequest(phone=PHONE), self.REQ
                    )
                    outcomes.append(200)
                except HTTPException as e:
                    outcomes.append(e.status_code)
            return outcomes

        self.assertEqual(run(requests())[-1], 429)


if __name__ == "__main__":
    unittest.main()
