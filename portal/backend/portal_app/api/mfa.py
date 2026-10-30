"""MFA account APIs: normal and limited recovery cookies have disjoint authority."""

from fastapi import APIRouter, Request
from pydantic import Field, SecretStr
from starlette.concurrency import run_in_threadpool

from portal_app.api.account_security import Proof, Strict
from portal_app.api.accounts import check_origin, peer_address
from portal_app.api.sessions import bootstrap, cookie, response
from portal_app.mfa.service import Mfa
from portal_app.sessions.service import CHALLENGE_COOKIE, SESSION_COOKIE, csrf

RECOVERY_COOKIE = "__Host-portal-recovery"
router = APIRouter(prefix="/mfa")


def mfa_response(payload):
    result = response(payload)
    if payload.get("global_logout"):
        from portal_app.sessions.receipts import COOKIE

        result.delete_cookie(COOKIE, secure=True, httponly=True, samesite="strict", path="/")
    return result


class AssertionOptions(Strict):
    current_password: SecretStr = Field(min_length=1, max_length=128)
    action: str = Field(min_length=1, max_length=32)
    parameters: SecretStr | dict | None = None
    email: str | None = Field(default=None, max_length=320)


class Enrollment(Strict):
    proof: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")
    kind: str = Field(pattern=r"^(totp|webauthn)$")
    name: str = Field(min_length=1, max_length=80)
    replace_id: str | None = Field(default=None, max_length=36)


class Finish(Strict):
    challenge_id: str = Field(min_length=36, max_length=36)
    totp: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    credential: dict | None = None


class Management(Proof):
    action: str = Field(pattern=r"^(mfa_disable|mfa_remove|mfa_backup_codes)$")
    parameters: dict | None = None


class Recovery(Strict):
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=128)
    backup_code: SecretStr = Field(min_length=32, max_length=64)


def context(request, recovery=False):
    check_origin(request)
    return (
        Mfa(request.app.state.accounts),
        request.cookies.get(RECOVERY_COOKIE if recovery else SESSION_COOKIE),
        request.headers.get("x-csrf-token"),
    )


@router.get("/status")
async def status(request: Request):
    bootstrap(request)
    return mfa_response(
        await run_in_threadpool(
            Mfa(request.app.state.accounts).status, request.cookies.get(SESSION_COOKIE)
        )
    )


@router.post("/assertion/options")
async def assertion_options(data: AssertionOptions, request: Request):
    service, raw, proof = context(request)
    if data.action == "login":
        raw = request.cookies.get(CHALLENGE_COOKIE)
    return mfa_response(
        await run_in_threadpool(
            service.assertion_options,
            raw,
            proof,
            data.current_password.get_secret_value(),
            data.action,
            data.parameters.get_secret_value()
            if isinstance(data.parameters, SecretStr)
            else data.parameters,
            data.email,
            peer_address(request),
        )
    )


@router.post("/enroll/begin")
async def begin(data: Enrollment, request: Request):
    service, raw, proof = context(request)
    return mfa_response(
        await run_in_threadpool(
            service.begin, raw, proof, data.proof, data.kind, data.name, data.replace_id
        )
    )


@router.post("/enroll/finish")
async def finish(data: Finish, request: Request):
    service, raw, proof = context(request)
    return mfa_response(
        await run_in_threadpool(
            service.finish,
            raw,
            proof,
            data.challenge_id,
            data.model_dump(exclude={"challenge_id"}, exclude_none=True),
            peer_address(request),
        )
    )


@router.post("/manage")
async def manage(data: Management, request: Request):
    service, raw, proof = context(request)
    return mfa_response(
        await run_in_threadpool(
            service.manage, raw, proof, data.proof, data.action, data.parameters
        )
    )


@router.post("/recovery/start")
async def recovery(data: Recovery, request: Request):
    check_origin(request)
    raw = await run_in_threadpool(
        Mfa(request.app.state.accounts).recover,
        data.email,
        data.password.get_secret_value(),
        data.backup_code.get_secret_value(),
        request.cookies.get(CHALLENGE_COOKIE),
        request.headers.get("x-csrf-token"),
        peer_address(request),
    )
    result = mfa_response({"status": "mfa_recovery", "csrf_token": csrf(raw), "expires_in": 900})
    cookie(result, RECOVERY_COOKIE, raw, 900)
    return result


@router.post("/recovery/enroll/begin")
async def recovery_begin(data: Enrollment, request: Request):
    service, raw, proof = context(request, True)
    return mfa_response(
        await run_in_threadpool(service.begin, raw, proof, None, data.kind, data.name, None, True)
    )


@router.post("/recovery/enroll/finish")
async def recovery_finish(data: Finish, request: Request):
    service, raw, proof = context(request, True)
    return mfa_response(
        await run_in_threadpool(
            service.finish,
            raw,
            proof,
            data.challenge_id,
            data.model_dump(exclude={"challenge_id"}, exclude_none=True),
            peer_address(request),
            True,
        )
    )
