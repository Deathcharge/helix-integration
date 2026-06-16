"""
🐙 GitHub App Integration
Native GitHub integration for repository management, webhooks, and automation

Replaces Zapier-based GitHub integration with direct GitHub App
"""

import hashlib
import hmac
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select, text

from apps.backend.core.unified_auth import get_current_user
from apps.backend.database import get_async_session
from apps.backend.security.admin_bypass import is_admin_user
from apps.backend.services.github_push_deploy_service import queue_push_deploy

try:
    from apps.backend.db_models import User
except ImportError:
    User = None  # type: ignore[assignment, misc]

try:
    from apps.backend.services.github_user_service import GitHubUserService
except ImportError:
    GitHubUserService = None  # type: ignore[assignment, misc]

try:
    from apps.backend.services.oauth_service import decrypt_token
except ImportError:
    decrypt_token = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

router = APIRouter()

_SERVER_API_KEY = os.getenv("HELIX_API_KEY", "")


class _GitHubInstallationVisibilityService(Protocol):
    async def list_installations(self) -> list[dict[str, Any]]: ...


def require_github_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Allow GitHub management actions only for Helix admins."""
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


def _github_user_id(current_user: dict) -> str:
    user_id = current_user.get("id") or current_user.get("user_id") or current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authenticated user id missing")
    return str(user_id)


async def _load_current_user_github_token(current_user: dict) -> str:
    token = current_user.get("github_access_token")
    if token:
        return str(token)

    if User is None:
        raise HTTPException(status_code=503, detail="GitHub linking unavailable")

    user_id = _github_user_id(current_user)
    async_session_factory = get_async_session()
    async with async_session_factory() as db:
        result = await db.execute(select(User.github_access_token).where(User.id == user_id))
        raw_token = result.scalar_one_or_none()

    if not raw_token:
        raise HTTPException(status_code=403, detail="GitHub account not linked. Connect GitHub OAuth first.")

    # Decrypt if encryption helpers are available (access tokens stored encrypted since 2026-04-18)
    if decrypt_token is not None:
        raw_token = decrypt_token(raw_token) or raw_token

    return str(raw_token)


async def _get_authenticated_github_service(current_user: dict) -> _GitHubInstallationVisibilityService:
    if GitHubUserService is None:
        raise HTTPException(status_code=503, detail="GitHub integration unavailable")

    token = await _load_current_user_github_token(current_user)
    return GitHubUserService(access_token=token)


async def _list_visible_installations(current_user: dict) -> list[dict]:
    github_service = await _get_authenticated_github_service(current_user)
    try:
        return await github_service.list_installations()
    except httpx.HTTPStatusError as exc:
        logger.warning("Failed to list user-visible GitHub installations: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to verify GitHub installation ownership") from exc


def _find_visible_installation(installations: list[dict], installation_id: int) -> dict | None:
    for installation in installations:
        try:
            if int(installation.get("id", 0)) == installation_id:
                return installation
        except (TypeError, ValueError):
            continue
    return None


async def _verify_server_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> str:
    """Verify the shared HELIX_API_KEY for server-to-server GitHub App calls."""
    if not _SERVER_API_KEY:
        raise HTTPException(status_code=503, detail="Server API key not configured")

    provided_key = x_api_key
    if not provided_key and authorization:
        provided_key = authorization[7:] if authorization.startswith("Bearer ") else authorization

    if not provided_key or not hmac.compare_digest(provided_key, _SERVER_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")

    return provided_key


# ============================================================================
# CONFIGURATION
# ============================================================================

GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_APP_PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY")  # Base64 encoded or file path
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class GitHubWebhookPayload(BaseModel):
    """Generic GitHub webhook payload"""

    action: str | None = None
    repository: dict | None = None
    sender: dict | None = None
    installation: dict | None = None


class GitHubInstallation(BaseModel):
    """GitHub App installation info"""

    installation_id: int
    account_login: str
    account_type: str
    repositories: list[str]
    permissions: dict


# ============================================================================
# GITHUB APP AUTHENTICATION
# ============================================================================


def generate_jwt_token() -> str:
    """
    Generate JWT for GitHub App authentication
    https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app
    """
    if not GITHUB_APP_ID or not GITHUB_APP_PRIVATE_KEY:
        raise ValueError("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY must be set")

    # Load private key
    if GITHUB_APP_PRIVATE_KEY.startswith("-----BEGIN"):
        private_key = GITHUB_APP_PRIVATE_KEY
    else:
        # Try to load from file
        try:
            with open(GITHUB_APP_PRIVATE_KEY, encoding="utf-8") as f:
                private_key = f.read()
        except (ValueError, TypeError, KeyError, IndexError) as e:
            logger.warning("GitHub App private key file loading failed, trying base64: %s", e)
            import base64

            private_key = base64.b64decode(GITHUB_APP_PRIVATE_KEY).decode("utf-8")

    # Create JWT
    now = int(time.time())
    payload = {
        "iat": now - 60,  # Issued at time (60 seconds in the past)
        "exp": now + (10 * 60),  # Expiration time (10 minutes)
        "iss": GITHUB_APP_ID,  # GitHub App ID
    }

    token = jwt.encode(payload, private_key, algorithm="RS256")
    return token


async def get_installation_access_token(installation_id: int) -> str:
    """
    Get an installation access token for making API requests
    https://docs.github.com/en/rest/apps/apps#create-an-installation-access-token-for-an-app
    """
    jwt_token = generate_jwt_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

        if response.status_code != 201:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to get installation token: {response.text}",
            )

        data = response.json()
        return data["token"]


# ============================================================================
# WEBHOOK SIGNATURE VERIFICATION
# ============================================================================


def verify_webhook_signature(payload: bytes, signature: str | None) -> bool:
    """
    Verify GitHub webhook signature
    https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
    """
    if not GITHUB_WEBHOOK_SECRET:
        # SECURITY: In production, webhook secret is mandatory
        env = os.getenv("ENVIRONMENT", "").lower()
        if env == "production":
            logger.error("CRITICAL: GITHUB_WEBHOOK_SECRET not set in production — rejecting webhook")
            return False
        # Dev-only bypass
        logger.warning("⚠️ GITHUB_WEBHOOK_SECRET not set — skipping verification (dev only)")
        return True

    if not signature:
        return False

    # GitHub sends: sha256=<hash>
    expected_signature = hmac.new(GITHUB_WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()

    expected = f"sha256={expected_signature}"
    return hmac.compare_digest(expected, signature)


# ============================================================================
# GITHUB API HELPERS
# ============================================================================


async def github_api_request(method: str, endpoint: str, installation_id: int, data: dict | None = None) -> dict:
    """Make authenticated request to GitHub API"""
    token = await get_installation_access_token(installation_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method,
            f"https://api.github.com{endpoint}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json=data,
        )

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"GitHub API error: {response.text}",
            )

        return response.json()


async def create_issue(
    installation_id: int,
    repo_owner: str,
    repo_name: str,
    title: str,
    body: str,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
) -> dict:
    """Create a GitHub issue"""
    data: dict[str, str | list[str]] = {"title": title, "body": body}
    if labels:
        data["labels"] = labels
    if assignees:
        data["assignees"] = assignees

    return await github_api_request(
        "POST",
        f"/repos/{repo_owner}/{repo_name}/issues",
        installation_id,
        data,
    )


async def create_pr_comment(
    installation_id: int, repo_owner: str, repo_name: str, pr_number: int, comment: str
) -> dict:
    """Comment on a pull request"""
    return await github_api_request(
        "POST",
        f"/repos/{repo_owner}/{repo_name}/issues/{pr_number}/comments",
        installation_id,
        {"body": comment},
    )


async def update_pr_status(
    installation_id: int,
    repo_owner: str,
    repo_name: str,
    commit_sha: str,
    state: str,  # error, failure, pending, success
    context: str,
    description: str,
    target_url: str | None = None,
) -> dict:
    """Update PR commit status"""
    data = {"state": state, "context": context, "description": description}
    if target_url:
        data["target_url"] = target_url

    return await github_api_request(
        "POST",
        f"/repos/{repo_owner}/{repo_name}/statuses/{commit_sha}",
        installation_id,
        data,
    )


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================


@router.post("/webhook")
@router.post("/github/webhook")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(...),
    x_hub_signature_256: str | None = Header(None),
):
    """
    Main GitHub webhook endpoint

    Receives events from GitHub:
    - push
    - pull_request
    - issues
    - installation
    - installation_repositories
    """
    # Get raw body for signature verification
    body = await request.body()

    # Verify signature
    if not verify_webhook_signature(body, x_hub_signature_256 or ""):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse payload
    payload = await request.json()

    # Handle different event types
    if x_github_event == "installation":
        return await handle_installation_event(payload)
    elif x_github_event == "installation_repositories":
        return await handle_installation_repositories_event(payload)
    elif x_github_event == "push":
        return await handle_push_event(payload)
    elif x_github_event == "pull_request":
        return await handle_pull_request_event(payload)
    elif x_github_event == "issues":
        return await handle_issues_event(payload)
    else:
        # Log unhandled event
        logger.info("📝 Unhandled GitHub event: %s", x_github_event)
        return {"status": "ignored", "event": x_github_event}


# ============================================================================
# EVENT HANDLERS
# ============================================================================


async def handle_installation_event(payload: dict) -> dict:
    """Handle app installation/uninstallation"""
    action = payload.get("action")
    installation = payload.get("installation", {})

    if action == "created":
        installation_id = installation.get("id")
        account = installation.get("account", {})
        account_login = account.get("login")

        logger.info("✅ GitHub App installed by %s", account_login)

        async_session_factory = get_async_session()
        async with async_session_factory() as db:
            await db.execute(
                text(
                    """INSERT INTO github_installations
                       (installation_id, account_login, installed_at)
                       VALUES (:installation_id, :account_login, :installed_at)
                       ON CONFLICT (installation_id) DO UPDATE
                       SET account_login = :account_login"""
                ),
                {
                    "installation_id": installation_id,
                    "account_login": account_login,
                    "installed_at": datetime.now(UTC),
                },
            )
            await db.commit()

    elif action == "deleted":
        installation_id = installation.get("id")
        account_login = installation.get("account", {}).get("login")

        logger.info("❌ GitHub App uninstalled by %s", account_login)

        # Remove installation from database

        async_session_factory = get_async_session()
        async with async_session_factory() as db:
            await db.execute(
                text("DELETE FROM github_installations WHERE installation_id = :installation_id"),
                {"installation_id": installation_id},
            )
            await db.commit()

    return {"status": "processed", "action": action}


async def handle_installation_repositories_event(payload: dict) -> dict:
    """Handle repository add/remove from installation"""
    action = payload.get("action")
    repos_added = payload.get("repositories_added", [])
    repos_removed = payload.get("repositories_removed", [])

    if action == "added":
        logger.info("📦 Repositories added: %s", [r["full_name"] for r in repos_added])
    elif action == "removed":
        logger.info("📦 Repositories removed: %s", [r["full_name"] for r in repos_removed])

    return {"status": "processed", "action": action}


async def handle_push_event(payload: dict) -> dict:
    """Handle push events"""
    ref = payload.get("ref")
    repo = payload.get("repository", {}).get("full_name")
    commits = payload.get("commits", [])
    deployment_state = "not_applicable"

    logger.info("📤 Push to %s (%s): %s commit(s)", repo, ref, len(commits))

    if ref == "refs/heads/main":
        deployment_state = queue_push_deploy(
            repo_full_name=repo,
            ref=ref,
            commit_count=len(commits),
        )

    return {
        "status": "processed",
        "commits": len(commits),
        "deployment": deployment_state,
    }


async def handle_pull_request_event(payload: dict) -> dict:
    """Handle pull request events"""
    action = payload.get("action")
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    installation_id = payload.get("installation", {}).get("id")

    pr_number = pr.get("number")
    pr_title = pr.get("title")

    logger.info("🔀 PR #%s %s: %s", pr_number, action, pr_title)

    # Example: Auto-comment on new PRs
    if action == "opened" and installation_id:
        comment = """👋 Thanks for opening this PR!

Our AI agents will review your changes shortly.

**Automated Checks:**
- ✓ Code style
- ✓ Tests
- ✓ Security scan

You can track progress in real-time on your [Helix Dashboard](https://helixspirals.work/dashboard).
"""
        try:
            await create_pr_comment(
                installation_id,
                repo["owner"]["login"],
                repo["name"],
                pr_number,
                comment,
            )
        except Exception as e:
            logger.error("Failed to comment on PR: %s", e)

    return {"status": "processed", "action": action, "pr": pr_number}


async def handle_issues_event(payload: dict) -> dict:
    """Handle issue events"""
    action = payload.get("action")
    issue = payload.get("issue", {})

    issue_number = issue.get("number")
    issue_title = issue.get("title")

    logger.info("🐛 Issue #%s %s: %s", issue_number, action, issue_title)

    # Example: Auto-label issues based on content
    if action == "opened":
        labels_to_add = []
        body = issue.get("body", "").lower()

        if "bug" in body:
            labels_to_add.append("bug")
        if "feature" in body:
            labels_to_add.append("enhancement")
        if "security" in body or "vulnerability" in body:
            labels_to_add.append("security")

        # Add labels using GitHub API
        if labels_to_add:
            try:
                repo_full_name = payload.get("repository", {}).get("full_name")
                if repo_full_name:
                    owner, repo = repo_full_name.split("/")
                    installation_id = payload.get("installation", {}).get("id")

                    if installation_id:
                        await github_api_request(
                            "POST",
                            f"/repos/{owner}/{repo}/issues/{issue_number}/labels",
                            installation_id,
                            {"labels": labels_to_add},
                        )
                        logger.info("🏷️ Added labels %s to issue #%s", labels_to_add, issue_number)
            except Exception as e:
                logger.error("❌ Failed to add labels to issue #%s: %s", issue_number, e)

    return {"status": "processed", "action": action, "issue": issue_number}


# ============================================================================
# API ENDPOINTS
# ============================================================================


@router.get("/installations")
@router.get("/github/installations")
async def list_installations(_admin: dict = Depends(require_github_admin)):
    """List all GitHub App installations"""
    jwt_token = generate_jwt_token()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://api.github.com/app/installations",
            headers={
                "Authorization": f"Bearer {jwt_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to list installations: {response.text}",
            )

        return response.json()


@router.post("/repos/{owner}/{repo}/issues")
@router.post("/github/repos/{owner}/{repo}/issues")
async def create_github_issue(
    owner: str,
    repo: str,
    title: str,
    body: str,
    installation_id: int,
    labels: list[str] | None = Query(None),
    _admin: dict = Depends(require_github_admin),
):
    """Create a GitHub issue via API"""
    return await create_issue(installation_id, owner, repo, title, body, labels)


@router.get("/health")
@router.get("/github/health")
async def github_health(_admin: dict = Depends(require_github_admin)):
    """Check GitHub App configuration"""
    checks: dict[str, object] = {}
    checks["app_id_configured"] = bool(GITHUB_APP_ID)
    checks["private_key_configured"] = bool(GITHUB_APP_PRIVATE_KEY)
    checks["webhook_secret_configured"] = bool(GITHUB_WEBHOOK_SECRET)
    checks["client_id_configured"] = bool(GITHUB_CLIENT_ID)
    checks["client_secret_configured"] = bool(GITHUB_CLIENT_SECRET)

    # Try to generate JWT
    try:
        generate_jwt_token()
        checks["jwt_generation"] = True
    except Exception as e:
        checks["jwt_generation"] = False
        checks["jwt_error"] = str(e)

    all_healthy = all(
        [
            checks["app_id_configured"],
            checks["private_key_configured"],
            checks["jwt_generation"],
        ]
    )

    return {"status": "healthy" if all_healthy else "unhealthy", "checks": checks}


# ============================================================================
# USER ACCOUNT LINKING - Connect GitHub installations to Helix user accounts
# ============================================================================


@router.post("/link-installation")
@router.post("/github/link-installation")
async def link_installation_to_user(
    installation_id: int,
    current_user: dict = Depends(get_current_user),
):
    """
    Link a GitHub App installation to the authenticated Helix user.

    Ownership is verified against the caller's GitHub OAuth identity before the
    installation can be claimed.
    """
    user_id = _github_user_id(current_user)
    visible_installations = await _list_visible_installations(current_user)
    visible_installation = _find_visible_installation(visible_installations, installation_id)
    if visible_installation is None:
        raise HTTPException(status_code=403, detail="Installation is not accessible to the authenticated GitHub user")

    account_login = (visible_installation.get("account") or {}).get("login") or visible_installation.get(
        "account_login"
    )

    async_session_factory = get_async_session()
    async with async_session_factory() as db:
        result = await db.execute(
            text("SELECT installation_id, user_id FROM github_installations WHERE installation_id = :installation_id"),
            {"installation_id": installation_id},
        )
        row = result.fetchone()
        if row and row[1] and str(row[1]) != user_id:
            raise HTTPException(status_code=409, detail="Installation already linked to another user")

        await db.execute(
            text(
                """INSERT INTO github_installations
                   (installation_id, account_login, user_id, installed_at, linked_at)
                   VALUES (:installation_id, :account_login, :user_id, :installed_at, :linked_at)
                   ON CONFLICT (installation_id) DO UPDATE
                   SET account_login = :account_login,
                       user_id = :user_id,
                       linked_at = :linked_at"""
            ),
            {
                "installation_id": installation_id,
                "account_login": account_login,
                "user_id": user_id,
                "installed_at": datetime.now(UTC),
                "linked_at": datetime.now(UTC),
            },
        )
        await db.commit()

    return {
        "status": "linked",
        "installation_id": installation_id,
        "user_id": user_id,
        "account_login": account_login,
    }


@router.get("/user-installations")
@router.get("/github/user-installations")
@router.get("/github/user-installations/{user_id}")
async def get_user_installations(
    current_user: dict = Depends(get_current_user),
    user_id: str | None = None,
):
    """
    Get GitHub App installations linked to the authenticated user.

    Admins may query another user's linked installations via the legacy path.
    """
    current_user_id = _github_user_id(current_user)
    target_user_id = current_user_id
    if user_id and user_id != current_user_id:
        if not is_admin_user(current_user):
            raise HTTPException(status_code=403, detail="Cannot access installations for another user")
        target_user_id = user_id

    async_session_factory = get_async_session()
    async with async_session_factory() as db:
        result = await db.execute(
            text(
                """SELECT installation_id, account_login, installed_at, linked_at
                   FROM github_installations
                   WHERE user_id = :user_id"""
            ),
            {"user_id": target_user_id},
        )
        rows = result.fetchall()

    installations = [
        {
            "installation_id": row[0],
            "account_login": row[1],
            "installed_at": row[2].isoformat() if row[2] else None,
            "linked_at": row[3].isoformat() if row[3] else None,
        }
        for row in rows
    ]

    return {"user_id": target_user_id, "installations": installations}


@router.delete("/unlink-installation/{installation_id}")
@router.delete("/github/unlink-installation/{installation_id}")
async def unlink_installation(
    installation_id: int,
    current_user: dict = Depends(get_current_user),
    user_id: str | None = None,
):
    """
    Unlink a GitHub App installation from the authenticated user account.

    The installation remains active but is no longer associated with the user.
    """
    current_user_id = _github_user_id(current_user)
    target_user_id = current_user_id
    if user_id and user_id != current_user_id:
        if not is_admin_user(current_user):
            raise HTTPException(status_code=403, detail="Cannot unlink installations for another user")
        target_user_id = user_id

    async_session_factory = get_async_session()
    async with async_session_factory() as db:
        result = await db.execute(
            text(
                """UPDATE github_installations
                   SET user_id = NULL, linked_at = NULL
                   WHERE installation_id = :installation_id AND user_id = :user_id"""
            ),
            {"installation_id": installation_id, "user_id": target_user_id},
        )
        await db.commit()

        if result.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Installation not found or not linked to this user",
            )

    return {"status": "unlinked", "installation_id": installation_id}


@router.get("/linked-user-by-installation/{installation_id}")
@router.get("/github/linked-user-by-installation/{installation_id}")
async def get_linked_user_by_installation(
    installation_id: int,
    _api_key: str = Depends(_verify_server_api_key),
):
    """Resolve the Helix account linked to a GitHub App installation."""
    async_session_factory = get_async_session()
    async with async_session_factory() as db:
        result = await db.execute(
            text(
                """SELECT gi.installation_id, gi.account_login, u.id, u.email, u.name, u.subscription_tier, u.github_username
                   FROM github_installations gi
                   JOIN users u ON u.id = gi.user_id
                   WHERE gi.installation_id = :installation_id AND gi.user_id IS NOT NULL"""
            ),
            {"installation_id": installation_id},
        )
        row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No Helix user linked to this installation")

    return {
        "installation_id": row[0],
        "account_login": row[1],
        "user_id": row[2],
        "email": row[3],
        "name": row[4],
        "subscription_tier": row[5],
        "github_username": row[6],
    }


@router.get("/installation-by-account/{account_login}")
@router.get("/github/installation-by-account/{account_login}")
async def get_installation_by_account(
    account_login: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Find a visible GitHub installation by account login for the authenticated user.
    """
    visible_installations = await _list_visible_installations(current_user)
    matched_installation = next(
        (
            installation
            for installation in visible_installations
            if str((installation.get("account") or {}).get("login") or installation.get("account_login") or "").lower()
            == account_login.lower()
        ),
        None,
    )

    if matched_installation is None:
        return {"found": False, "account_login": account_login}

    raw_installation_id = matched_installation.get("id")
    if not isinstance(raw_installation_id, (int, str)):
        return {"found": False, "account_login": account_login}

    installation_id = int(raw_installation_id)
    current_user_id = _github_user_id(current_user)

    async_session_factory = get_async_session()
    async with async_session_factory() as db:
        result = await db.execute(
            text(
                """SELECT installation_id, account_login, user_id, installed_at, linked_at
                   FROM github_installations
                   WHERE installation_id = :installation_id"""
            ),
            {"installation_id": installation_id},
        )
        row = result.fetchone()

    linked_to_current_user = bool(row and row[2] and str(row[2]) == current_user_id)
    is_linked = bool(row and row[2])

    return {
        "found": True,
        "installation_id": installation_id,
        "account_login": (matched_installation.get("account") or {}).get("login") or account_login,
        "installed_at": row[3].isoformat() if row and row[3] else None,
        "linked_at": row[4].isoformat() if row and row[4] and linked_to_current_user else None,
        "is_linked": is_linked,
        "linked_to_current_user": linked_to_current_user,
    }
