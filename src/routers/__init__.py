from src.routers.auth_router import router as auth_router
from src.routers.users_router import router as users_router
from src.routers.keys_router import router as keys_router
from src.routers.completions_router import router as completions_router
from src.routers.models_router import router as models_router
from src.routers.skills_router import router as skills_router
from src.routers.data_router import router as data_router
from src.routers.settings_router import router as settings_router
from src.routers.skill_chat_router import router as skill_chat_router
from src.routers.management_router import router as management_router
from src.routers.model_builder_router import router as model_builder_router
from src.routers.firewall_router import router as firewall_router
from src.routers.database_router import router as database_router
from src.routers.ai_assistant_router import router as ai_assistant_router
from src.routers.integrations_router import router as integrations_router
from src.routers.agent_router import router as agent_router
from src.routers.mcp_router import router as mcp_router

__all__ = [
    "auth_router",
    "users_router",
    "keys_router",
    "completions_router",
    "models_router",
    "skills_router",
    "data_router",
    "settings_router",
    "skill_chat_router",
    "management_router",
    "model_builder_router",
    "firewall_router",
    "database_router",
    "ai_assistant_router",
    "integrations_router",
    "agent_router",
    "mcp_router"
]
