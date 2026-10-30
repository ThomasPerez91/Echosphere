"""Same-origin account security endpoints; no automatic authentication after changes."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from starlette.concurrency import run_in_threadpool

from portal_app.account_security.service import AccountSecurity
from portal_app.api.accounts import check_origin, peer_address
from portal_app.api.sessions import response
from portal_app.sessions.service import SESSION_COOKIE

router = APIRouter(prefix="/security")


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class StepUp(Strict):
    action: Literal[
        "password_change",
        "email_change",
        "logout_all",
        "mfa_enroll",
        "mfa_remove",
        "mfa_disable",
        "mfa_backup_codes",
    ]
    factor: dict | None = None
    parameters: dict | None = None
    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr | None = Field(default=None, min_length=15, max_length=128)
    new_email: str | None = Field(default=None, min_length=3, max_length=320)

    @model_validator(mode="after")
    def consistent(self):
        if (self.action == "password_change") != (self.new_password is not None) or (
            self.action == "email_change"
        ) != (self.new_email is not None):
            raise ValueError("Action parameters do not match")
        return self


class Proof(Strict):
    proof: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class PasswordChange(Proof):
    new_password: SecretStr = Field(min_length=15, max_length=128)


class EmailChange(Proof):
    new_email: str = Field(min_length=3, max_length=320)


class ResetRequest(Strict):
    email: str = Field(min_length=3, max_length=320)


class Token(Strict):
    token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class ResetConfirm(Token):
    new_password: SecretStr = Field(min_length=15, max_length=128)


def context(request):
    check_origin(request)
    return (
        AccountSecurity(request.app.state.accounts),
        request.cookies.get(SESSION_COOKIE),
        request.headers.get("x-csrf-token"),
    )


def changed(payload):
    # Keep cookies until the next normal login: a delayed response must not erase a newer cookie.
    return response(payload)


@router.post("/step-up")
async def step_up(data: StepUp, request: Request):
    service, raw, csrf = context(request)
    parameters = data.new_password.get_secret_value() if data.new_password else data.new_email
    if data.action.startswith("mfa_"):
        parameters = data.parameters
    return response(
        await run_in_threadpool(
            service.step_up,
            raw,
            csrf,
            data.current_password.get_secret_value(),
            data.action,
            parameters,
            peer_address(request),
            data.factor,
        )
    )


@router.post("/password/change")
async def password_change(data: PasswordChange, request: Request):
    service, raw, csrf = context(request)
    return changed(
        await run_in_threadpool(
            service.password_change,
            raw,
            csrf,
            data.proof,
            data.new_password.get_secret_value(),
            peer_address(request),
        )
    )


@router.post("/logout-all")
async def logout_all(data: Proof, request: Request):
    service, raw, csrf = context(request)
    return changed(await run_in_threadpool(service.logout_all, raw, csrf, data.proof))


@router.post("/password/reset/request", status_code=202)
async def reset_request(data: ResetRequest, request: Request):
    service, _, _ = context(request)
    await run_in_threadpool(service.reset_request, data.email, peer_address(request))
    result = response({"status": "request_received"})
    result.status_code = 202
    return result


@router.post("/password/reset/confirm")
async def reset_confirm(data: ResetConfirm, request: Request):
    service, _, _ = context(request)
    return changed(
        await run_in_threadpool(
            service.reset_confirm,
            data.token,
            data.new_password.get_secret_value(),
            peer_address(request),
        )
    )


@router.post("/email/request")
async def email_request(data: EmailChange, request: Request):
    service, raw, csrf = context(request)
    return response(
        await run_in_threadpool(
            service.email_request, raw, csrf, data.proof, data.new_email, peer_address(request)
        )
    )


@router.post("/email/confirm")
async def email_confirm(data: Token, request: Request):
    service, _, _ = context(request)
    return changed(
        await run_in_threadpool(service.email_confirm, data.token, peer_address(request))
    )
