import hiro  # type: ignore
import pytest  # type: ignore
from fastapi import APIRouter, FastAPI
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.testclient import TestClient

from slowapi.errors import RateLimitExceeded
from slowapi.extension import Limiter, _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIASGIMiddleware
from slowapi.util import get_ipaddr
from tests import TestSlowapi


class TestDecorators(TestSlowapi):
    def test_single_decorator(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr)

        @app.get("/t1")
        @limiter.limit("5/minute")
        async def t1(request: Request):
            return PlainTextResponse("test")

        client = TestClient(app)
        for i in range(0, 10):
            response = client.get("/t1")
            assert response.status_code == 200 if i < 5 else 429

    def test_single_decorator_with_headers(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr, headers_enabled=True)

        @app.get("/t1")
        @limiter.limit("5/minute")
        async def t1(request: Request):
            return PlainTextResponse("test")

        client = TestClient(app)
        for i in range(0, 10):
            response = client.get("/t1")
            assert response.status_code == 200 if i < 5 else 429
            assert (
                response.headers.get("X-RateLimit-Limit") is not None if i < 5 else True
            )
            assert response.headers.get("Retry-After") is not None if i < 5 else True

    def test_single_decorator_not_response(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr)

        @app.get("/t1")
        @limiter.limit("5/minute")
        async def t1(request: Request, response: Response):
            return {"key": "value"}

        client = TestClient(app)
        for i in range(0, 10):
            response = client.get("/t1")
            assert response.status_code == 200 if i < 5 else 429

    def test_single_decorator_not_response_with_headers(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr, headers_enabled=True)

        @app.get("/t1")
        @limiter.limit("5/minute")
        async def t1(request: Request, response: Response):
            return {"key": "value"}

        client = TestClient(app)
        for i in range(0, 10):
            response = client.get("/t1")
            assert response.status_code == 200 if i < 5 else 429
            assert (
                response.headers.get("X-RateLimit-Limit") is not None if i < 5 else True
            )
            assert response.headers.get("Retry-After") is not None if i < 5 else True

    def test_multiple_decorators(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr)

        @app.get("/t1")
        @limiter.limit(
            "100 per minute", lambda: "test"
        )  # effectively becomes a limit for all users
        @limiter.limit("50/minute")  # per ip as per default key_func
        async def t1(request: Request):
            return PlainTextResponse("test")

        with hiro.Timeline().freeze() as timeline:
            cli = TestClient(app)
            for i in range(0, 100):
                response = cli.get("/t1", headers={"X_FORWARDED_FOR": "127.0.0.2"})
                assert response.status_code == 200 if i < 50 else 429
            for i in range(50):
                assert cli.get("/t1").status_code == 200

            assert cli.get("/t1").status_code == 429
            assert (
                cli.get("/t1", headers={"X_FORWARDED_FOR": "127.0.0.3"}).status_code
                == 429
            )

    def test_multiple_decorators_not_response(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr)

        @app.get("/t1")
        @limiter.limit(
            "100 per minute", lambda: "test"
        )  # effectively becomes a limit for all users
        @limiter.limit("50/minute")  # per ip as per default key_func
        async def t1(request: Request, response: Response):
            return {"key": "value"}

        with hiro.Timeline().freeze() as timeline:
            cli = TestClient(app)
            for i in range(0, 100):
                response = cli.get("/t1", headers={"X_FORWARDED_FOR": "127.0.0.2"})
                assert response.status_code == 200 if i < 50 else 429
            for i in range(50):
                assert cli.get("/t1").status_code == 200

            assert cli.get("/t1").status_code == 429
            assert (
                cli.get("/t1", headers={"X_FORWARDED_FOR": "127.0.0.3"}).status_code
                == 429
            )

    def test_multiple_decorators_not_response_with_headers(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr, headers_enabled=True)

        @app.get("/t1")
        @limiter.limit(
            "100 per minute", lambda: "test"
        )  # effectively becomes a limit for all users
        @limiter.limit("50/minute")  # per ip as per default key_func
        async def t1(request: Request, response: Response):
            return {"key": "value"}

        with hiro.Timeline().freeze() as timeline:
            cli = TestClient(app)
            for i in range(0, 100):
                response = cli.get("/t1", headers={"X_FORWARDED_FOR": "127.0.0.2"})
                assert response.status_code == 200 if i < 50 else 429
            for i in range(50):
                assert cli.get("/t1").status_code == 200

            assert cli.get("/t1").status_code == 429
            assert (
                cli.get("/t1", headers={"X_FORWARDED_FOR": "127.0.0.3"}).status_code
                == 429
            )

    def test_endpoint_missing_request_param(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr)

        with pytest.raises(Exception) as exc_info:

            @app.get("/t3")
            @limiter.limit("5/minute")
            async def t3():
                return PlainTextResponse("test")

        assert exc_info.match(
            r"""^No "request" or "websocket" argument on function .*"""
        )

    def test_endpoint_missing_request_param_sync(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr)

        with pytest.raises(Exception) as exc_info:

            @app.get("/t3_sync")
            @limiter.limit("5/minute")
            def t3():
                return PlainTextResponse("test")

        assert exc_info.match(
            r"""^No "request" or "websocket" argument on function .*"""
        )

    def test_endpoint_request_param_invalid(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr)

        @app.get("/t4")
        @limiter.limit("5/minute")
        async def t4(request: str = None):
            return PlainTextResponse("test")

        with pytest.raises(Exception) as exc_info:
            client = TestClient(app)
            client.get("/t4")
        assert exc_info.match(
            r"""parameter `request` must be an instance of starlette.requests.Request"""
        )

    def test_endpoint_response_param_invalid(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr, headers_enabled=True)

        @app.get("/t4")
        @limiter.limit("5/minute")
        async def t4(request: Request, response: str = None):
            return {"key": "value"}

        with pytest.raises(Exception) as exc_info:
            client = TestClient(app)
            client.get("/t4")
        assert exc_info.match(
            r"""parameter `response` must be an instance of starlette.responses.Response"""
        )

    def test_endpoint_request_param_invalid_sync(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr)

        @app.get("/t5")
        @limiter.limit("5/minute")
        def t5(request: str = None):
            return PlainTextResponse("test")

        with pytest.raises(Exception) as exc_info:
            client = TestClient(app)
            client.get("/t5")
        assert exc_info.match(
            r"""parameter `request` must be an instance of starlette.requests.Request"""
        )

    def test_endpoint_response_param_invalid_sync(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr, headers_enabled=True)

        @app.get("/t5")
        @limiter.limit("5/minute")
        def t5(request: Request, response: str = None):
            return {"key": "value"}

        with pytest.raises(Exception) as exc_info:
            client = TestClient(app)
            client.get("/t5")
        assert exc_info.match(
            r"""parameter `response` must be an instance of starlette.responses.Response"""
        )

    def test_dynamic_limit_provider_depending_on_key(self, build_fastapi_app):
        def custom_key_func(request: Request):
            if request.headers.get("TOKEN") == "secret":
                return "admin"
            return "user"

        def dynamic_limit_provider(key: str):
            if key == "admin":
                return "10/minute"
            return "5/minute"

        app, limiter = build_fastapi_app(key_func=custom_key_func)

        @app.get("/t1")
        @limiter.limit(dynamic_limit_provider)
        async def t1(request: Request, response: Response):
            return {"key": "value"}

        client = TestClient(app)
        for i in range(0, 10):
            response = client.get("/t1")
            assert response.status_code == 200 if i < 5 else 429

        for i in range(0, 20):
            response = client.get("/t1", headers={"TOKEN": "secret"})
            assert response.status_code == 200 if i < 10 else 429

    def test_disabled_limiter(self, build_fastapi_app):
        """
        Check that the limiter does nothing if disabled (both sync and async)
        """
        app, limiter = build_fastapi_app(key_func=get_ipaddr, enabled=False)

        @app.get("/t1")
        @limiter.limit("5/minute")
        async def t1(request: Request):
            return PlainTextResponse("test")

        @app.get("/t2")
        @limiter.limit("5/minute")
        def t2(request: Request):
            return PlainTextResponse("test")

        @app.get("/t3")
        def t3(request: Request):
            return PlainTextResponse("also a test")

        client = TestClient(app)
        for i in range(0, 10):
            response = client.get("/t1")
            assert response.status_code == 200

        for i in range(0, 10):
            response = client.get("/t2")
            assert response.status_code == 200

        for i in range(0, 10):
            response = client.get("/t3")
            assert response.status_code == 200

    def test_cost(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr)

        @app.get("/t1")
        @limiter.limit("50/minute", cost=10)
        async def t1(request: Request):
            return PlainTextResponse("test")

        @app.get("/t2")
        @limiter.limit("50/minute", cost=15)
        async def t2(request: Request):
            return PlainTextResponse("test")

        client = TestClient(app)
        for i in range(0, 10):
            response = client.get("/t1")
            assert response.status_code == 200 if i < 5 else 429

            response = client.get("/t2")
            assert response.status_code == 200 if i < 3 else 429

    def test_callable_cost(self, build_fastapi_app):
        app, limiter = build_fastapi_app(key_func=get_ipaddr)

        @app.get("/t1")
        @limiter.limit("50/minute", cost=lambda request: int(request.headers["foo"]))
        async def t1(request: Request):
            return PlainTextResponse("test")

        @app.get("/t2")
        @limiter.limit(
            "50/minute", cost=lambda request: int(request.headers["foo"]) * 1.5
        )
        async def t2(request: Request):
            return PlainTextResponse("test")

        client = TestClient(app)
        for i in range(0, 10):
            response = client.get("/t1", headers={"foo": "10"})
            assert response.status_code == 200 if i < 5 else 429

            response = client.get("/t2", headers={"foo": "5"})
            assert response.status_code == 200 if i < 6 else 429

    @pytest.mark.parametrize(
        "key_style",
        ["url", "endpoint"],
    )
    def test_key_style(self, build_fastapi_app, key_style):
        app, limiter = build_fastapi_app(key_func=lambda: "mock", key_style=key_style)

        @app.get("/t1/{my_param}")
        @limiter.limit("1/minute")
        async def t1_func(my_param: str, request: Request):
            return PlainTextResponse("test")

        client = TestClient(app)
        client.get("/t1/param_one")
        second_call = client.get("/t1/param_two")
        # with the "url" key_style, since the `my_param` value changed, the storage key is different
        # meaning it should not raise any RateLimitExceeded error.
        if key_style == "url":
            assert second_call.status_code == 200
            assert limiter._storage.get("LIMITER/mock//t1/param_one/1/1/minute") == 1
            assert limiter._storage.get("LIMITER/mock//t1/param_two/1/1/minute") == 1
        # However, with the `endpoint` key_style, it will use the function name (e.g: "t1_func")
        # meaning it will raise a RateLimitExceeded error, because no matter the parameter value
        # it will share the limitations.
        elif key_style == "endpoint":
            assert second_call.status_code == 429
            # check that we counted 2 requests, even though we had a different value for "my_param"
            assert (
                limiter._storage.get(
                    "LIMITER/mock/tests.test_fastapi_extension.t1_func/1/1/minute"
                )
                == 2
            )


class TestIncludedRouters:
    """
    Routes added through `include_router` must still be found by the middleware.

    Since FastAPI 0.138, `app.routes` holds an opaque `_IncludedRouter` node per
    `include_router` call instead of the flattened sub routes. A middleware that
    only looks at the top level finds no handler, and slowapi then treats every
    request as exempt.

    These tests only cover `SlowAPIASGIMiddleware`: `SlowAPIMiddleware` does not
    await `_check_limits` and is broken for unrelated reasons.
    """

    def build_app(self, **limiter_args):
        limiter_args.setdefault("key_func", lambda: "mock")
        limiter_args.setdefault("storage_uri", "async+memory://")
        limiter = Limiter(**limiter_args)
        app = FastAPI()
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIASGIMiddleware)
        return app, limiter

    def test_default_limits_apply_to_included_router(self):
        app, limiter = self.build_app(default_limits=["2/minute"])
        router = APIRouter()

        @router.get("/t1")
        async def t1(request: Request):
            return PlainTextResponse("test")

        app.include_router(router, prefix="/v0")

        client = TestClient(app)
        assert [client.get("/v0/t1").status_code for _ in range(3)] == [200, 200, 429]

    def test_default_limits_apply_to_nested_included_router(self):
        app, limiter = self.build_app(default_limits=["2/minute"])
        inner = APIRouter()

        @inner.get("/t1/{my_param}")
        async def t1(my_param: str, request: Request):
            return PlainTextResponse("test")

        outer = APIRouter()
        outer.include_router(inner, prefix="/inner")
        app.include_router(outer, prefix="/v0")

        client = TestClient(app)
        assert [client.get("/v0/inner/t1/p").status_code for _ in range(3)] == [
            200,
            200,
            429,
        ]

    def test_default_limits_apply_to_route_added_directly(self):
        app, limiter = self.build_app(default_limits=["2/minute"])

        @app.get("/t1")
        async def t1(request: Request):
            return PlainTextResponse("test")

        client = TestClient(app)
        assert [client.get("/t1").status_code for _ in range(3)] == [200, 200, 429]

    def test_plain_starlette_route_in_included_router(self):
        app, limiter = self.build_app(default_limits=["2/minute"])
        router = APIRouter()

        async def t1(request: Request):
            return PlainTextResponse("test")

        router.add_route("/t1", t1, methods=["GET"])
        app.include_router(router, prefix="/v0")

        client = TestClient(app)
        assert [client.get("/v0/t1").status_code for _ in range(3)] == [200, 200, 429]

    def test_exempt_route_in_included_router(self):
        app, limiter = self.build_app(default_limits=["2/minute"])
        router = APIRouter()

        @router.get("/t1")
        @limiter.exempt
        async def t1(request: Request):
            return PlainTextResponse("test")

        app.include_router(router, prefix="/v0")

        client = TestClient(app)
        assert [client.get("/v0/t1").status_code for _ in range(3)] == [200, 200, 200]

    def test_unknown_route_is_not_limited(self):
        app, limiter = self.build_app(default_limits=["2/minute"])
        router = APIRouter()

        @router.get("/t1")
        async def t1(request: Request):
            return PlainTextResponse("test")

        app.include_router(router, prefix="/v0")

        client = TestClient(app)
        assert [client.get("/nope").status_code for _ in range(3)] == [404, 404, 404]


class TestHeaderInjection(TestSlowapi):
    """
    Header injection reads window stats from the storage, which is async in this
    fork. A missing `await` there turns every breached request into a 500, and
    silently marks the storage dead on the way out.
    """

    def test_middleware_429_goes_through_the_default_handler(self, build_fastapi_app):
        app, limiter = build_fastapi_app(
            key_func=lambda: "mock",
            default_limits=["2/minute"],
            headers_enabled=True,
            in_memory_fallback_enabled=True,
        )

        @app.get("/t1")
        async def t1(request: Request):
            return PlainTextResponse("test")

        client = TestClient(app)
        responses = [client.get("/t1") for _ in range(3)]

        assert [r.status_code for r in responses] == [200, 200, 429]
        assert responses[0].headers["X-RateLimit-Limit"] == "2"
        assert not limiter._storage_dead
