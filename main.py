from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os

from core.database import create_db_and_tables
from services.tasks import start_scheduler
from core.logger import get_logger
from routers import feedback, admin, admin_portal, auth, users, whatsapp, branches

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_db_and_tables()
    start_scheduler()
    logger.info("Application started")
    yield
    # Shutdown
    logger.info("Application shutting down")

app = FastAPI(lifespan=lifespan)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error"},
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(feedback.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(admin_portal.router)
app.include_router(users.router)
app.include_router(whatsapp.router)
app.include_router(branches.router)

# Serve frontend files
frontend_dist = "frontend-survey/dist"
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    logger.warning(f"Frontend directory '{frontend_dist}' not found. Serving as API only.")