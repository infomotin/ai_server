"""
RBAC Service - Role-Based Access Control
Manages roles, permissions, menus, and user assignments.
"""
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.models.database import RBACRole, RBACPermission, RBACMenu, RBACModule, RBACUserRole, User


DEFAULT_MODULES = [
    {"name": "AI Management", "slug": "ai-management", "icon": "fas fa-robot", "sort": 1},
    {"name": "Model Builder", "slug": "model-builder", "icon": "fas fa-hammer", "sort": 2},
    {"name": "Data Sources", "slug": "data-sources", "icon": "fas fa-database", "sort": 3},
    {"name": "Skills", "slug": "skills", "icon": "fas fa-wand-magic-sparkles", "sort": 4},
    {"name": "Assistants", "slug": "assistants", "icon": "fas fa-robot", "sort": 5},
    {"name": "Agent", "slug": "agent", "icon": "fas fa-terminal", "sort": 6},
    {"name": "Firewall", "slug": "firewall", "icon": "fas fa-shield-halved", "sort": 7},
    {"name": "Cameras", "slug": "cameras", "icon": "fas fa-video", "sort": 8},
    {"name": "Training", "slug": "training", "icon": "fas fa-brain", "sort": 9},
    {"name": "Integrations", "slug": "integrations", "icon": "fas fa-plug", "sort": 10},
    {"name": "Settings", "slug": "settings", "icon": "fas fa-cog", "sort": 11},
    {"name": "User Management", "slug": "user-management", "icon": "fas fa-users", "sort": 12},
]

DEFAULT_MENUS = [
    # AI Management
    {"module": "ai-management", "title": "Dashboard", "slug": "dashboard", "url": "/dashboard", "icon": "fas fa-th-large"},
    {"module": "ai-management", "title": "Chat", "slug": "chat", "url": "/chat", "icon": "fas fa-comments"},
    {"module": "ai-management", "title": "Models", "slug": "models", "url": "/models", "icon": "fas fa-cube"},
    {"module": "ai-management", "title": "API Keys", "slug": "api-keys", "url": "/keys", "icon": "fas fa-key"},
    # Model Builder
    {"module": "model-builder", "title": "Templates", "slug": "templates", "url": "/model-builder", "icon": "fas fa-layer-group"},
    {"module": "model-builder", "title": "Custom Models", "slug": "custom-models", "url": "/model-builder", "icon": "fas fa-building"},
    # Data Sources
    {"module": "data-sources", "title": "Upload Files", "slug": "upload", "url": "/data", "icon": "fas fa-upload"},
    {"module": "data-sources", "title": "Database Connect", "slug": "database", "url": "/data", "icon": "fas fa-plug"},
    {"module": "data-sources", "title": "Train AI", "slug": "train", "url": "/data", "icon": "fas fa-brain"},
    {"module": "data-sources", "title": "Knowledge Bases", "slug": "knowledge-bases", "url": "/data", "icon": "fas fa-brain"},
    # Skills
    {"module": "skills", "title": "All Skills", "slug": "all-skills", "url": "/skills", "icon": "fas fa-wand-magic-sparkles"},
    # Assistants
    {"module": "assistants", "title": "My Assistants", "slug": "my-assistants", "url": "/assistants", "icon": "fas fa-robot"},
    # Agent
    {"module": "agent", "title": "Coding Agent", "slug": "coding-agent", "url": "/agent", "icon": "fas fa-terminal"},
    # Firewall
    {"module": "firewall", "title": "Profiles", "slug": "profiles", "url": "/firewall", "icon": "fas fa-shield-halved"},
    {"module": "firewall", "title": "Rules", "slug": "rules", "url": "/firewall", "icon": "fas fa-list"},
    # Cameras
    {"module": "cameras", "title": "Live View", "slug": "live-view", "url": "/cameras", "icon": "fas fa-broadcast-tower"},
    {"module": "cameras", "title": "My Cameras", "slug": "my-cameras", "url": "/cameras", "icon": "fas fa-video"},
    {"module": "cameras", "title": "Recordings", "slug": "recordings", "url": "/cameras", "icon": "fas fa-film"},
    # Training
    {"module": "training", "title": "Training Jobs", "slug": "training-jobs", "url": "/data", "icon": "fas fa-tasks"},
    # Integrations
    {"module": "integrations", "title": "All Integrations", "slug": "all-integrations", "url": "/integrations", "icon": "fas fa-plug"},
    # Settings
    {"module": "settings", "title": "Profile", "slug": "profile", "url": "/settings", "icon": "fas fa-user"},
    # User Management (Admin only)
    {"module": "user-management", "title": "Users", "slug": "users", "url": "/admin/users", "icon": "fas fa-users", "admin_only": True},
    {"module": "user-management", "title": "Roles", "slug": "roles", "url": "/admin/roles", "icon": "fas fa-user-shield", "admin_only": True},
    {"module": "user-management", "title": "Permissions", "slug": "permissions", "url": "/admin/permissions", "icon": "fas fa-key", "admin_only": True},
    {"module": "user-management", "title": "Menus", "slug": "menus", "url": "/admin/menus", "icon": "fas fa-bars", "admin_only": True},
]

DEFAULT_ROLES = [
    {"name": "Super Admin", "slug": "super-admin", "description": "Full system access", "is_system": True, "is_active": True},
    {"name": "Admin", "slug": "admin", "description": "Administrative access", "is_system": True, "is_active": True},
    {"name": "Manager", "slug": "manager", "description": "Management level access", "is_system": False, "is_active": True},
    {"name": "Operator", "slug": "operator", "description": "Operational access", "is_system": False, "is_active": True},
    {"name": "Viewer", "slug": "viewer", "description": "Read-only access", "is_system": False, "is_active": True},
]

ACTIONS = ["view", "create", "edit", "delete", "*"]


class RBACService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def init_default_data(self, db: Session) -> Dict[str, Any]:
        """Initialize default modules, menus, roles, and permissions."""
        result = {"modules": 0, "menus": 0, "roles": 0, "permissions": 0}

        # Create modules
        for mod_data in DEFAULT_MODULES:
            existing = db.query(RBACModule).filter(RBACModule.slug == mod_data["slug"]).first()
            if not existing:
                module = RBACModule(
                    id=str(uuid.uuid4()),
                    name=mod_data["name"],
                    slug=mod_data["slug"],
                    icon=mod_data.get("icon"),
                    sort_order=mod_data.get("sort", 0),
                    is_active=True
                )
                db.add(module)
                result["modules"] += 1

        db.commit()

        # Create menus
        for menu_data in DEFAULT_MENUS:
            module = db.query(RBACModule).filter(RBACModule.slug == menu_data["module"]).first()
            if not module:
                continue
            existing = db.query(RBACMenu).filter(
                RBACMenu.slug == menu_data["slug"],
                RBACMenu.module_id == module.id
            ).first()
            if not existing:
                menu = RBACMenu(
                    id=str(uuid.uuid4()),
                    module_id=module.id,
                    title=menu_data["title"],
                    slug=menu_data["slug"],
                    url=menu_data.get("url"),
                    icon=menu_data.get("icon"),
                    is_active=True
                )
                db.add(menu)
                result["menus"] += 1

        db.commit()

        # Create roles
        for role_data in DEFAULT_ROLES:
            existing = db.query(RBACRole).filter(RBACRole.slug == role_data["slug"]).first()
            if not existing:
                role = RBACRole(
                    id=str(uuid.uuid4()),
                    name=role_data["name"],
                    slug=role_data["slug"],
                    description=role_data.get("description"),
                    is_system=role_data.get("is_system", False),
                    is_active=role_data.get("is_active", True)
                )
                db.add(role)
                result["roles"] += 1

        db.commit()

        # Create permissions for each menu
        menus = db.query(RBACMenu).all()
        for menu in menus:
            for action in ACTIONS:
                permission_name = f"{menu.slug}.{action}"
                existing = db.query(RBACPermission).filter(
                    RBACPermission.menu_id == menu.id,
                    RBACPermission.action == action
                ).first()
                if not existing:
                    perm = RBACPermission(
                        id=str(uuid.uuid4()),
                        menu_id=menu.id,
                        name=permission_name,
                        action=action,
                        is_active=True
                    )
                    db.add(perm)
                    result["permissions"] += 1

        db.commit()
        return result

    # ============== Module CRUD ==============
    def get_modules(self, db: Session, include_menus: bool = False) -> List[Dict]:
        query = db.query(RBACModule).filter(RBACModule.is_active == True).order_by(RBACModule.sort_order)
        modules = query.all()
        result = []
        for m in modules:
            data = {
                "id": m.id,
                "name": m.name,
                "slug": m.slug,
                "icon": m.icon,
                "description": m.description,
                "sort_order": m.sort_order,
                "is_active": m.is_active
            }
            if include_menus:
                menus = db.query(RBACMenu).filter(
                    RBACMenu.module_id == m.id,
                    RBACMenu.is_active == True,
                    RBACMenu.parent_id == None
                ).order_by(RBACMenu.sort_order).all()
                data["menus"] = [self._serialize_menu(db, menu) for menu in menus]
            result.append(data)
        return result

    def _serialize_menu(self, db: Session, menu: RBACMenu) -> Dict:
        children = db.query(RBACMenu).filter(
            RBACMenu.parent_id == menu.id,
            RBACMenu.is_active == True
        ).all()
        return {
            "id": menu.id,
            "title": menu.title,
            "slug": menu.slug,
            "url": menu.url,
            "icon": menu.icon,
            "sort_order": menu.sort_order,
            "children": [self._serialize_menu(db, c) for c in children]
        }

    # ============== Menu CRUD ==============
    def get_menus(self, db: Session, module_id: Optional[str] = None) -> List[Dict]:
        query = db.query(RBACMenu)
        if module_id:
            query = query.filter(RBACMenu.module_id == module_id)
        menus = query.filter(RBACMenu.is_active == True).order_by(RBACMenu.sort_order).all()
        return [self._serialize_menu(db, m) for m in menus if not m.parent_id]

    def create_menu(self, db: Session, data: Dict) -> RBACMenu:
        menu = RBACMenu(
            id=str(uuid.uuid4()),
            module_id=data["module_id"],
            parent_id=data.get("parent_id"),
            title=data["title"],
            slug=data["slug"],
            url=data.get("url"),
            icon=data.get("icon"),
            sort_order=data.get("sort_order", 0),
            is_active=True
        )
        db.add(menu)
        db.commit()
        db.refresh(menu)
        return menu

    def update_menu(self, db: Session, menu_id: str, data: Dict) -> Optional[RBACMenu]:
        menu = db.query(RBACMenu).filter(RBACMenu.id == menu_id).first()
        if not menu:
            return None
        for key in ["title", "slug", "url", "icon", "sort_order", "parent_id"]:
            if key in data:
                setattr(menu, key, data[key])
        db.commit()
        db.refresh(menu)
        return menu

    def delete_menu(self, db: Session, menu_id: str) -> bool:
        menu = db.query(RBACMenu).filter(RBACMenu.id == menu_id).first()
        if not menu:
            return False
        db.delete(menu)
        db.commit()
        return True

    # ============== Role CRUD ==============
    def get_roles(self, db: Session, include_permissions: bool = False) -> List[Dict]:
        roles = db.query(RBACRole).order_by(RBACRole.is_system.desc(), RBACRole.name).all()
        result = []
        for r in roles:
            data = {
                "id": r.id,
                "name": r.name,
                "slug": r.slug,
                "description": r.description,
                "is_active": r.is_active,
                "is_system": r.is_system,
                "created_at": str(r.created_at)
            }
            if include_permissions:
                perms = db.query(RBACPermission).filter(
                    RBACPermission.role_id == r.id
                ).all()
                data["permissions"] = [p.name for p in perms]
            result.append(data)
        return result

    def create_role(self, db: Session, data: Dict) -> RBACRole:
        role = RBACRole(
            id=str(uuid.uuid4()),
            name=data["name"],
            slug=data["slug"],
            description=data.get("description"),
            is_active=True,
            is_system=False
        )
        db.add(role)
        db.commit()
        db.refresh(role)

        # Assign permissions
        if "permissions" in data and data["permissions"]:
            self.assign_permissions_to_role(db, role.id, data["permissions"])

        return role

    def update_role(self, db: Session, role_id: str, data: Dict) -> Optional[RBACRole]:
        role = db.query(RBACRole).filter(RBACRole.id == role_id).first()
        if not role:
            return None
        if role.is_system:
            # Can't modify system roles
            return None

        for key in ["name", "slug", "description"]:
            if key in data:
                setattr(role, key, data[key])

        db.commit()
        db.refresh(role)

        # Update permissions if provided
        if "permissions" in data:
            self.assign_permissions_to_role(db, role_id, data["permissions"])

        return role

    def delete_role(self, db: Session, role_id: str) -> bool:
        role = db.query(RBACRole).filter(RBACRole.id == role_id).first()
        if not role or role.is_system:
            return False

        # Remove all permission assignments
        db.query(RBACPermission).filter(RBACPermission.role_id == role_id).delete()

        # Remove user assignments
        db.query(RBACUserRole).filter(RBACUserRole.role_id == role_id).delete()

        db.delete(role)
        db.commit()
        return True

    def toggle_role(self, db: Session, role_id: str) -> bool:
        role = db.query(RBACRole).filter(RBACRole.id == role_id).first()
        if not role or role.is_system:
            return False
        role.is_active = not role.is_active
        db.commit()
        return True

    # ============== Permission Assignment ==============
    def assign_permissions_to_role(self, db: Session, role_id: str, permissions: List[str]) -> None:
        # Remove existing
        db.query(RBACPermission).filter(RBACPermission.role_id == role_id).delete()
        db.commit()

        # Add new
        for perm_name in permissions:
            # Find permission by name
            menu_slug, action = perm_name.rsplit(".", 1) if "." in perm_name else (perm_name, "*")
            menu = db.query(RBACMenu).filter(RBACMenu.slug == menu_slug).first()
            if menu:
                perm = RBACPermission(
                    id=str(uuid.uuid4()),
                    menu_id=menu.id,
                    role_id=role_id,
                    name=perm_name,
                    action=action,
                    is_active=True
                )
                db.add(perm)

        db.commit()

    def get_all_permissions(self, db: Session) -> List[Dict]:
        """Get all permissions grouped by module and menu."""
        modules = self.get_modules(db, include_menus=True)
        result = []
        for module in modules:
            for menu in module.get("menus", []):
                menu_perms = db.query(RBACPermission).filter(
                    RBACPermission.menu_id == menu["id"]
                ).all()
                result.append({
                    "module": module["name"],
                    "module_slug": module["slug"],
                    "menu": menu["title"],
                    "menu_slug": menu["slug"],
                    "menu_id": menu["id"],
                    "permissions": [{"id": p.id, "name": p.name, "action": p.action} for p in menu_perms]
                })
        return result

    # ============== User-Role Assignment ==============
    def assign_role_to_user(self, db: Session, user_id: str, role_id: str, granted_by: Optional[str] = None) -> RBACUserRole:
        # Remove existing role assignment
        db.query(RBACUserRole).filter(RBACUserRole.user_id == user_id).delete()

        # Add new assignment
        assignment = RBACUserRole(
            id=str(uuid.uuid4()),
            user_id=user_id,
            role_id=role_id,
            granted_by=granted_by
        )
        db.add(assignment)
        db.commit()
        db.refresh(assignment)
        return assignment

    def remove_role_from_user(self, db: Session, user_id: str) -> bool:
        db.query(RBACUserRole).filter(RBACUserRole.user_id == user_id).delete()
        db.commit()
        return True

    def get_user_roles(self, db: Session, user_id: str) -> List[Dict]:
        assignments = db.query(RBACUserRole).filter(RBACUserRole.user_id == user_id).all()
        result = []
        for a in assignments:
            role = db.query(RBACRole).filter(RBACRole.id == a.role_id).first()
            if role:
                result.append({
                    "role_id": role.id,
                    "role_name": role.name,
                    "role_slug": role.slug,
                    "granted_at": str(a.granted_at)
                })
        return result

    def get_role_permissions(self, db: Session, role_id: str) -> List[str]:
        perms = db.query(RBACPermission).filter(RBACPermission.role_id == role_id).all()
        return [p.name for p in perms]

    def user_has_permission(self, db: Session, user_id: str, permission: str) -> bool:
        """Check if user has a specific permission."""
        # Get user's roles
        assignments = db.query(RBACUserRole).filter(RBACUserRole.user_id == user_id).all()
        for a in assignments:
            perms = db.query(RBACPermission).filter(
                RBACPermission.role_id == a.role_id,
                RBACPermission.name == permission
            ).first()
            if perms:
                return True
            # Check for wildcard
            perm_parts = permission.split(".")
            if len(perm_parts) == 2:
                wildcard = f"{perm_parts[0]}.*"
                wc_perm = db.query(RBACPermission).filter(
                    RBACPermission.role_id == a.role_id,
                    RBACPermission.name == wildcard
                ).first()
                if wc_perm:
                    return True
        return False

    def get_users_with_roles(self, db: Session) -> List[Dict]:
        """Get all users with their assigned roles."""
        users = db.query(User).all()
        result = []
        for u in users:
            roles = self.get_user_roles(db, u.id)
            result.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_active": u.is_active,
                "is_admin": u.is_admin,
                "created_at": str(u.created_at) if u.created_at else "",
                "roles": roles
            })
        return result


rbac_service = RBACService()
