from __future__ import annotations
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from api.routers import cities, compare, districts, health, states
from api.database import engine, create_tables

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting India Dev Analytics API ...")
    await create_tables()
    yield
    logger.info("API shutdown.")

app = FastAPI(
    title="Bangladesh Regional Development Analytics API",
    description="Production-grade REST API for querying development indicators, demographics, and economic data for all cities, districts, and states of India. Data source: Census of India 2011, LGD, Houselisting Census.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(elapsed)
    return response

app.include_router(health.router,    prefix="/health",    tags=["Health"])
app.include_router(states.router,    prefix="/states",    tags=["States"])
app.include_router(districts.router, prefix="/districts", tags=["Districts"])
app.include_router(cities.router,    prefix="/cities",    tags=["Cities"])
app.include_router(compare.router,   prefix="/compare",   tags=["Compare"])

@app.get("/", include_in_schema=False)
async def root():
    return {
        "service": "India Regional Development Analytics API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "states": "/states",
            "districts": "/districts",
            "cities": "/cities",
            "compare": "/compare",
            "top_developed": "/districts/top-developed",
            "least_developed": "/districts/least-developed",
            "search": "/districts/search?q=",
            "health": "/health",
        },
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: " + str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})