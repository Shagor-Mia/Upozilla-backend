from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import CurrentUser, get_client_ip, get_current_user, get_optional_user
from app.core.rate_limit import rate_limit_by_ip
from app.db.models.otp import OtpPurpose
from app.modules.auth import otp_service, service
from app.modules.auth.schemas import (
    FacebookLoginRequest,
    GoogleLoginRequest,
    LoginRequest,
    LogoutRequest,
    OtpRequestBody,
    OtpRequestResponse,
    OtpVerifyBody,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    WsTicketResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(db: Session, user) -> TokenResponse:
    access_token, refresh_token = service.issue_token_pair(db, user)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(rate_limit_by_ip("register", limit=30, window_seconds=600))],
)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return _tokens(db, service.register_user(db, payload))


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_by_ip("login", limit=30, window_seconds=600))],
)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return _tokens(db, service.authenticate_user(db, payload))


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    access_token, refresh_token = service.rotate_refresh_token(db, payload.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=204)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> None:
    if payload.refresh_token:
        service.revoke_refresh_token(db, payload.refresh_token)


@router.post("/logout-all", status_code=204)
def logout_all(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    service.revoke_all_refresh_tokens(db, current_user.uuid)


@router.get("/me", response_model=UserResponse)
def me(current_user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> UserResponse:
    return service.to_user_response(db, service.get_user_by_id(db, current_user.user_id))


# --- Phone OTP (Section 10) ------------------------------------------------------


@router.post("/otp/request", response_model=OtpRequestResponse)
def request_otp(
    payload: OtpRequestBody,
    request: Request,
    db: Session = Depends(get_db),
    current_user: CurrentUser | None = Depends(get_optional_user),
) -> OtpRequestResponse:
    if payload.purpose is OtpPurpose.VERIFY_PHONE and current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="sign in before verifying a phone number")

    expires_in, dev_code = otp_service.request_otp(
        db,
        phone=payload.phone,
        purpose=payload.purpose,
        client_ip=get_client_ip(request),
        turnstile_token=payload.turnstile_token,
        requesting_user_id=current_user.uuid if current_user else None,
    )
    return OtpRequestResponse(sent=True, expires_in_seconds=expires_in, dev_code=dev_code)


@router.post("/otp/verify", response_model=TokenResponse)
def verify_otp(
    payload: OtpVerifyBody,
    db: Session = Depends(get_db),
    current_user: CurrentUser | None = Depends(get_optional_user),
) -> TokenResponse:
    """Verifies the code, then issues our own JWT pair (Section 10). For
    `verify_phone` the caller must already be signed in; the fresh token pair
    carries the updated `phone_verified` claim."""
    if payload.purpose is OtpPurpose.REGISTER and not payload.full_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="full_name is required to register")
    if payload.purpose is OtpPurpose.VERIFY_PHONE and current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="sign in before verifying a phone number")

    otp_service.verify_otp(db, payload.phone, payload.code, payload.purpose)

    if payload.purpose is OtpPurpose.LOGIN:
        user = service.login_with_verified_phone(db, payload.phone)
    elif payload.purpose is OtpPurpose.REGISTER:
        user = service.register_with_verified_phone(db, payload.phone, payload.full_name or "")
    else:
        assert current_user is not None
        user = service.attach_verified_phone(db, current_user.uuid, payload.phone)
    return _tokens(db, user)


# --- Facebook Login (Section 16.2) ----------------------------------------------


@router.post(
    "/facebook",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_by_ip("facebook-login", limit=30, window_seconds=600))],
)
def facebook_login(payload: FacebookLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return _tokens(db, service.login_with_facebook(db, payload.access_token))


# --- Google Login ----------------------------------------------------------------


@router.post(
    "/google",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit_by_ip("google-login", limit=30, window_seconds=600))],
)
def google_login(payload: GoogleLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    return _tokens(db, service.login_with_google(db, payload.id_token))


# --- WebSocket auth ticket -------------------------------------------------------


@router.post("/ws-ticket", response_model=WsTicketResponse)
def ws_ticket(current_user: CurrentUser = Depends(get_current_user)) -> WsTicketResponse:
    ticket, ttl = service.create_ws_ticket(current_user)
    return WsTicketResponse(ticket=ticket, expires_in_seconds=ttl)
