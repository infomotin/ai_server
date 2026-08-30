"""
RBAC Router - Role-Based Access Control API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.models.engine import get_db_session
from src.models.database import User
from src.services.rbac_service import rbac_service
from src.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/rbac", tags=["RBAC"])


class InitRequest(BaseModel):
    pass


class ModuleCreate(BaseModel):
    name: str
    slug: str
    icon: Optional[str] = None
    description: Optional[str] = None
    sort_order: int = 0


class MenuCreate(BaseModel):
    module_id: str
    parent_id: Optional[str] = None
    title: str
    slug: str
    url: Optional[str] = None
    icon: Optional[str] = None
    sort_order: int = 0


class MenuUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    url: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None
    parent_id: Optional[str] = None


class RoleCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    permissions: List[str] = []


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None


class UserRoleAssign(BaseModel):
    user_id: str
    role_id: str


def check_admin(current_user: User = Depends(get_current_user)) -> User:
    """Ensure user is admin."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.post("/init")
async def init_rbac(
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Initialize default RBAC data."""
    result = rbac_service.init_default_data(db)
    return {"success": True, "message": "RBAC initialized", "data": result}


@router.get("/modules")
async def get_modules(
    include_menus: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get all modules with optional menus."""
    return rbac_service.get_modules(db, include_menus=include_menus)


@router.post("/modules")
async def create_module(
    data: ModuleCreate,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Create a new module."""
    from src.models.database import RBACModule
    import uuid
    module = RBACModule(
        id=str(uuid.uuid4()),
        name=data.name,
        slug=data.slug,
        icon=data.icon,
        description=data.description,
        sort_order=data.sort_order,
        is_active=True
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    return {"success": True, "module": {"id": module.id, "name": module.name, "slug": module.slug}}


@router.get("/menus")
async def get_menus(
    module_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get menus, optionally filtered by module."""
    return rbac_service.get_menus(db, module_id=module_id)


@router.post("/menus")
async def create_menu(
    data: MenuCreate,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Create a new menu."""
    menu = rbac_service.create_menu(db, data.model_dump())
    return {"success": True, "menu": {"id": menu.id, "title": menu.title, "slug": menu.slug}}


@router.put("/menus/{menu_id}")
async def update_menu(
    menu_id: str,
    data: MenuUpdate,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Update a menu."""
    menu = rbac_service.update_menu(db, menu_id, data.model_dump(exclude_unset=True))
    if not menu:
        raise HTTPException(status_code=404, detail="Menu not found")
    return {"success": True, "menu": {"id": menu.id, "title": menu.title, "slug": menu.slug}}


@router.delete("/menus/{menu_id}")
async def delete_menu(
    menu_id: str,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Delete a menu."""
    if not rbac_service.delete_menu(db, menu_id):
        raise HTTPException(status_code=404, detail="Menu not found")
    return {"success": True}


@router.get("/roles")
async def get_roles(
    include_permissions: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get all roles with optional permissions."""
    return rbac_service.get_roles(db, include_permissions=include_permissions)


@router.post("/roles")
async def create_role(
    data: RoleCreate,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Create a new role."""
    role = rbac_service.create_role(db, data.model_dump())
    return {"success": True, "role": {"id": role.id, "name": role.name, "slug": role.slug}}


@router.put("/roles/{role_id}")
async def update_role(
    role_id: str,
    data: RoleUpdate,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Update a role."""
    role = rbac_service.update_role(db, role_id, data.model_dump(exclude_unset=True))
    if not role:
        raise HTTPException(status_code=404, detail="Role not found or system role")
    return {"success": True, "role": {"id": role.id, "name": role.name, "slug": role.slug}}


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: str,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Delete a role."""
    if not rbac_service.delete_role(db, role_id):
        raise HTTPException(status_code=400, detail="Cannot delete system role")
    return {"success": True}


@router.post("/roles/{role_id}/toggle")
async def toggle_role(
    role_id: str,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Toggle role active status."""
    if not rbac_service.toggle_role(db, role_id):
        raise HTTPException(status_code=400, detail="Cannot toggle system role")
    return {"success": True}


@router.get("/permissions")
async def get_all_permissions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session)
):
    """Get all permissions grouped by module and menu."""
    return rbac_service.get_all_permissions(db)


@router.post("/roles/{role_id}/permissions")
async def assign_permissions(
    role_id: str,
    permissions: List[str],
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Assign permissions to a role."""
    rbac_service.assign_permissions_to_role(db, role_id, permissions)
    return {"success": True, "permissions": permissions}


@router.get("/users/roles")
async def get_users_with_roles(
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Get all users with their assigned roles."""
    return rbac_service.get_users_with_roles(db)


@router.post("/users/{user_id}/role")
async def assign_role(
    user_id: str,
    data: UserRoleAssign,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Assign a role to a user."""
    rbac_service.assign_role_to_user(db, user_id, data.role_id, granted_by=current_user.id)
    return {"success": True}


@router.delete("/users/{user_id}/role")
async def remove_role(
    user_id: str,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Remove role from a user."""
    rbac_service.remove_role_from_user(db, user_id)
    return {"success": True}


@router.get("/users/{user_id}/roles")
async def get_user_roles(
    user_id: str,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Get roles assigned to a user."""
    return rbac_service.get_user_roles(db, user_id)


@router.get("/users/{user_id}/has-permission/{permission}")
async def check_user_permission(
    user_id: str,
    permission: str,
    current_user: User = Depends(check_admin),
    db: Session = Depends(get_db_session)
):
    """Check if user has a specific permission."""
    has_perm = rbac_service.user_has_permission(db, user_id, permission)
    return {"user_id": user_id, "permission": permission, "has_permission": has_perm}
