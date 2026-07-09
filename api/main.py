from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from starlette.responses import JSONResponse, Response

from api.interactions import handle_interaction
from api.tasks import ActionsCommandRequest, AskCommandRequest, CompleteActionRequest
from minutes_agent.config import Settings, get_settings
from minutes_agent.models import GenerateMinutesRequest
from minutes_agent.workflow import MinutesWorkflow

app = FastAPI(title="Minutes Agent API", version="0.1.0")


@app.middleware("http")
async def enforce_route_profile(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if not _route_allowed(get_settings(), request.url.path):
        return JSONResponse(
            status_code=404,
            content={"detail": "route is not enabled on this service"},
        )
    return await call_next(request)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/tasks/generate-minutes")
def generate_minutes_task(
    payload: GenerateMinutesRequest,
    request: Request,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    settings = get_settings()
    _verify_internal_request(settings, x_agent_token, authorization, request)
    result = MinutesWorkflow(settings).generate_minutes(payload)
    return result.model_dump(mode="json")


@app.post("/tasks/check-actions")
def check_actions_task(
    request: Request,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    settings = get_settings()
    _verify_internal_request(settings, x_agent_token, authorization, request)
    actions = MinutesWorkflow(settings).check_actions()
    return {"notified": [action.model_dump(mode="json") for action in actions]}


@app.post("/commands/ask")
def ask_command(
    payload: AskCommandRequest,
    request: Request,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, str]:
    settings = get_settings()
    _verify_internal_request(settings, x_agent_token, authorization, request)
    answer = MinutesWorkflow(settings).answer_question(payload.question, limit=payload.limit)
    return {"answer": answer}


@app.post("/commands/actions")
def actions_command(
    payload: ActionsCommandRequest,
    request: Request,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    settings = get_settings()
    _verify_internal_request(settings, x_agent_token, authorization, request)
    actions = MinutesWorkflow(settings).list_actions(status=payload.status)
    return {"actions": [action.model_dump(mode="json") for action in actions[: payload.limit]]}


@app.post("/commands/action-done")
def action_done_command(
    payload: CompleteActionRequest,
    request: Request,
    x_agent_token: str | None = Header(default=None, alias="X-Agent-Token"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, object]:
    settings = get_settings()
    _verify_internal_request(settings, x_agent_token, authorization, request)
    item = MinutesWorkflow(settings).complete_action(payload.action_id)
    if item is None:
        raise HTTPException(status_code=404, detail="action item was not found")
    return {"action": item.model_dump(mode="json")}


@app.post("/interactions")
async def discord_interactions(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, object]:
    settings = get_settings()
    return await handle_interaction(request, background_tasks, settings)


def _verify_agent_token(expected: str | None, actual: str | None) -> None:
    if not expected:
        raise HTTPException(status_code=503, detail="agent token is not configured")
    if actual != expected:
        raise HTTPException(status_code=401, detail="invalid agent token")


def _verify_internal_request(
    settings: Settings,
    actual_token: str | None,
    authorization: str | None,
    request: Request,
) -> None:
    if not settings.agent_api_token and not settings.cloud_tasks_service_account_email:
        raise HTTPException(status_code=503, detail="internal authentication is not configured")
    if settings.agent_api_token and actual_token == settings.agent_api_token:
        return
    if _verify_oidc_service_account(settings, authorization, request):
        return
    if actual_token or authorization:
        raise HTTPException(status_code=401, detail="invalid internal authentication")
    raise HTTPException(status_code=401, detail="missing internal authentication")


def _verify_oidc_service_account(
    settings: Settings,
    authorization: str | None,
    request: Request | None = None,
) -> bool:
    if not settings.cloud_tasks_service_account_email:
        return False
    if not authorization or not authorization.startswith("Bearer "):
        return False
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return False
    try:
        audience = _oidc_audience_for_request(settings, request)
        from google.auth.transport import requests
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(token, requests.Request(), audience=audience)
    except HTTPException:
        raise
    except Exception:
        return False
    email = str(claims.get("email") or claims.get("sub") or "")
    return email == settings.cloud_tasks_service_account_email


def _oidc_audience_for_request(settings: Settings, request: Request | None) -> str:
    if settings.cloud_run_base_url:
        base_url = settings.cloud_run_base_url.rstrip("/")
    elif request is not None:
        base_url = f"{request.url.scheme}://{request.url.netloc}".rstrip("/")
    else:
        raise HTTPException(status_code=503, detail="cloud run base url is not configured")
    path = request.url.path if request is not None else ""
    return f"{base_url}{path}"


def _route_allowed(settings: Settings, path: str) -> bool:
    profile = settings.route_profile.lower()
    if profile == "public":
        return path in {"/health", "/interactions"}
    if profile == "internal":
        return path == "/health" or path.startswith("/tasks/") or path.startswith("/commands/")
    return True
