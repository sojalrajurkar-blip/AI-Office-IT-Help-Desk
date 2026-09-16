from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.security import verify_password, get_password_hash, create_access_token
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, Token, UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication & RBAC"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user account."""
    # Check if user with this email already exists
    stmt = select(User).where(User.email == user_in.email)
    existing_user = (await db.execute(stmt)).scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    # Create new user
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role or UserRole.REQUESTER,
        department=user_in.department,
        office_location=user_in.office_location,
        phone_number=user_in.phone_number,
        team_id=user_in.team_id,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    user_in: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user with email & password, returns JWT bearer token."""
    stmt = select(User).where(User.email == user_in.email)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account.",
        )

    access_token = create_access_token(subject=user.id)
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Retrieve the currently authenticated user profile."""
    return current_user


# RBAC Role Test Endpoints (Verifies backend RBAC security boundaries)
@router.get("/test/requester")
async def test_requester_access(
    current_user: User = Depends(require_roles([UserRole.REQUESTER])),
):
    return {"message": "Authorized for Requester", "user": current_user.email, "role": current_user.role}


@router.get("/test/operator")
async def test_operator_access(
    current_user: User = Depends(require_roles([UserRole.OPERATOR, UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN])),
):
    return {"message": "Authorized for IT Staff", "user": current_user.email, "role": current_user.role}


@router.get("/test/team-lead")
async def test_team_lead_access(
    current_user: User = Depends(require_roles([UserRole.TEAM_LEAD, UserRole.MANAGER, UserRole.ADMIN])),
):
    return {"message": "Authorized for Team Lead & above", "user": current_user.email, "role": current_user.role}


@router.get("/test/manager")
async def test_manager_access(
    current_user: User = Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN])),
):
    return {"message": "Authorized for Manager & Admin", "user": current_user.email, "role": current_user.role}


@router.get("/test/admin")
async def test_admin_access(
    current_user: User = Depends(require_roles([UserRole.ADMIN])),
):
    return {"message": "Authorized for Admin Only", "user": current_user.email, "role": current_user.role}
