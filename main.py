from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.core.database import create_db_and_tables
from backend.routers import auth_router, user_router, upload_router, batch_process_router, image_extraction_router, match_router, client_router, init_router, export_router, download_router
from backend.models import rebuild_models

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Rebuild models to resolve forward references
    rebuild_models()
    create_db_and_tables()
    yield

app = FastAPI(
    title="Ticket Management System",
    description="Phase 6: Client Management & Rate System",
    version="6.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(user_router.router)
app.include_router(upload_router.router)
app.include_router(batch_process_router.router)
app.include_router(image_extraction_router.router)
app.include_router(match_router.router)
app.include_router(client_router.router)
app.include_router(init_router.router)
app.include_router(export_router.router)
app.include_router(download_router.router)

@app.get("/")
async def root():
    return {
        "message": "Ticket Management System API",
        "version": "6.0.0",
        "phase": "Phase 6: Client Management & Rate System"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)