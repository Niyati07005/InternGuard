import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import Scan, User
from .schemas import LoginRequest, RegisterRequest

router = APIRouter(prefix="/api/auth", tags=["authentication"])
password_hasher = PasswordHasher()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if isinstance(user_id, int):
        user = db.get(User, user_id)
        if user is not None:
            return user
        request.session.clear()

    guest = User(
        email=f"guest-{secrets.token_urlsafe(24)}@local.invalid",
        password_hash=password_hasher.hash(secrets.token_urlsafe(32)),
        is_guest=True,
    )
    db.add(guest)
    db.commit()
    db.refresh(guest)
    request.session["user_id"] = guest.id
    return guest


def user_payload(user: User) -> dict:
    return {"id": user.id, "email": None if user.is_guest else user.email, "is_guest": user.is_guest}


def _move_guest_scans(request: Request, user: User, db: Session) -> None:
    previous_id = request.session.get("user_id")
    if not isinstance(previous_id, int) or previous_id == user.id:
        return
    guest = db.get(User, previous_id)
    if guest is None or not guest.is_guest:
        return
    db.query(Scan).filter(Scan.owner_user_id == guest.id).update(
        {Scan.owner_user_id: user.id}, synchronize_session=False
    )
    db.delete(guest)
    db.commit()


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    user = User(email=payload.email, password_hash=password_hasher.hash(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.") from exc
    db.refresh(user)
    _move_guest_scans(request, user, db)
    request.session.clear()
    request.session["user_id"] = user.id
    return {"user": user_payload(user)}


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    try:
        valid = user is not None and password_hasher.verify(user.password_hash, payload.password)
    except (VerifyMismatchError, InvalidHashError):
        valid = False
    if not valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or password is incorrect.")
    _move_guest_scans(request, user, db)
    request.session.clear()
    request.session["user_id"] = user.id
    return {"user": user_payload(user)}


@router.get("/me")
def current_user(user: User = Depends(get_current_user)):
    return user_payload(user)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"logged_out": True}
