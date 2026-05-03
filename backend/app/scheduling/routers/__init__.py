from app.scheduling.routers.curriculum import router as scheduling_router
from app.scheduling.routers.scheduling import router as scheduling_v2_router
from app.scheduling.routers.rooms import router as rooms_router
from app.scheduling.routers.slots import router as slots_router
from app.scheduling.routers.designations import router as scheduling_designations_router

__all__ = [
    "scheduling_router",
    "scheduling_v2_router",
    "rooms_router",
    "slots_router",
    "scheduling_designations_router",
]
