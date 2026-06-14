import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from backend.config.settings import settings
from backend.api.routes import router
from backend.core.tool_checker import check_all_tools


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CTFAgent starting up...")
    tools = await check_all_tools()
    missing = [k for k, v in tools.items() if v is None]
    if missing:
        logger.warning(f"Missing tools: {', '.join(missing)}")
    else:
        logger.info("All required tools available")

    nvim_key = settings.nvidia_nim_api_key
    if not nvim_key or nvim_key == "your_key_here":
        logger.warning("NVIDIA_NIM_API_KEY not set! LLM calls will fail.")

    logger.info(f"Using NIM endpoint: {settings.nvidia_nim_base_url}")
    yield
    logger.info("CTFAgent shutting down.")


app = FastAPI(
    title="CTFAgent",
    description="Autonomous multi-agent CTF-solving framework",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "CTFAgent",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
    )
