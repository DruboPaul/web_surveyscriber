import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api import upload_router, extract_router, settings_router
from backend.app.api.routes_usage import router as usage_router
from backend.app.db.database import Base, get_engine, init_database

# ===============================
# Create database tables on startup
# ===============================
init_database()

app = FastAPI(
    title="Automated Handwritten Survey Data Extraction System",
    version="1.0.0"
)

# ===============================
# CORS (Frontend ↔ Backend)
# ===============================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===============================
# API Routes
# ===============================
app.include_router(
    upload_router,
    prefix="/upload",
    tags=["Upload"]
)

app.include_router(
    extract_router,
    prefix="/extract",
    tags=["Extract"]
)

app.include_router(
    settings_router,
    prefix="/api",
    tags=["Settings"]
)

app.include_router(
    usage_router,
    prefix="/api/usage",
    tags=["Usage"]
)

# ===============================
# Static files (Excel downloads)
# ===============================
# Create data directory if it doesn't exist (fresh install)
os.makedirs("data", exist_ok=True)

app.mount(
    "/data",
    StaticFiles(directory="data"),
    name="data"
)
