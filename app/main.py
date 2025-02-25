from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse, HTMLResponse, Response, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.config.settings import settings  # Updated import
from app.services.aiAssistant import SimpleAssistant  # Updated import
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import logging.handlers
import logging
import os
import sys
from contextlib import asynccontextmanager
import uvicorn
import signal
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Enhanced lifespan manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application"""
    try:
        logger.info("Starting application initialization...")
        await settings.initialize_openai()
        await settings.initialize_tokko()
        logger.info("Application initialization complete")
        yield
    except Exception as e:
        logger.error(f"Application initialization failed: {e}")
        raise
    finally:
        logger.info("Application shutdown initiated")

# Initialize FastAPI with explicit configuration
app = FastAPI(
    title=settings.app_name,
    description="Asistente Inmobiliario Altamirano API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    default_response_class=HTMLResponse
)

# Import routes after app initialization to avoid circular imports
from app.routes import chat_router, properties_router, chat

# Include routers
app.include_router(chat_router)
app.include_router(properties_router)
app.include_router(chat.router)

# Middleware configuration
app.add_middleware(ServerErrorMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware for request ID and logging
class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(datetime.utcnow().timestamp()))
        logger.debug(f"Processing request {request_id}: {request.method} {request.url}")
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            logger.debug(f"Request {request_id} completed with status {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"Request {request_id} failed: {str(e)}")
            raise

app.add_middleware(RequestContextMiddleware)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Content-Security-Policy"] = "upgrade-insecure-requests"
    return response

# Directory configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

# Ensure directories exist
os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

# Mount static files with custom configuration
app.mount("/static", StaticFiles(
    directory=static_dir,
    check_dir=True,
    html=True
), name="static")

templates = Jinja2Templates(directory=templates_dir)

# Enhanced home endpoint
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        logger.info(f"Processing home request from {request.client.host}")
        logger.debug(f"Template directory: {templates_dir}")
        templates_list = os.listdir(templates_dir)
        logger.debug(f"Available templates: {templates_list}")
        
        try:
            response = templates.TemplateResponse(
                "index.html",
                {
                    "request": request,
                    "title": "Asistente Inmobiliario Altamirano"
                }
            )
            logger.info("Template rendered successfully")
            return response
        except Exception as e:
            logger.warning(f"Template render error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error rendering template"
            )
    except Exception as e:
        logger.error(f"Home endpoint error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Enhanced health check endpoint
@app.get("/healthz")
async def healthz():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/health")
async def health_check():
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": os.getenv("K_REVISION", "local"),
            "services": {
                "openai": "initialized" if hasattr(settings, 'openai_client') else "not initialized",
                "tokko": "initialized" if hasattr(settings, 'tokko_client') else "not initialized"
            },
            "system": {
                "python_version": sys.version,
                "templates_dir": os.path.exists(templates_dir),
                "static_dir": os.path.exists(static_dir)
            }
        }
        
        if not all(service == "initialized" for service in health_status["services"].values()):
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health_status
            )
            
        return JSONResponse(content=health_status)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "unhealthy", "error": str(e)}
        )

# Debug endpoint
@app.get("/debug")
async def debug():
    try:
        debug_info = {
            "env": {
                k: v for k, v in os.environ.items() 
                if not any(secret in k.lower() for secret in ['key', 'password', 'secret'])
            },
            "directories": {
                "base": BASE_DIR,
                "templates": os.listdir(templates_dir),
                "static": os.listdir(static_dir)
            },
            "clients": {
                "openai": hasattr(settings, 'openai_client'),
                "tokko": hasattr(settings, 'tokko_client')
            }
        }
        return JSONResponse(content=debug_info)
    except Exception as e:
        logger.error(f"Debug endpoint error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Error handlers
@app.exception_handler(500)
async def internal_error(request: Request, exc: Exception):
    logger.error(f"Internal Server Error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "Internal Server Error",
            "detail": str(exc) if app.debug else None
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error handler: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "Internal server error"}
    )

# Favicon endpoint
@app.get("/favicon.ico")
async def favicon():
    """Handle favicon requests"""
    return JSONResponse(
        content={},  # Empty content for 204
        status_code=status.HTTP_204_NO_CONTENT
    )

# Signal handler
def handle_exit(signum, frame):
    logger.info(f"Received signal {signum}")
    try:
        if hasattr(settings, 'openai_client'):
            settings.openai_client.close()
        logger.info("Cleanup complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    finally:
        sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)

@app.on_event("startup")
async def startup_event():
    required_vars = ["OPENAI_API_KEY", "TOKKO_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing environment variables: {missing_vars}")
        raise HTTPException(status_code=500, detail="Missing required environment variables")
    
    logger.info("All required environment variables are set")

# Main execution
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="debug",
        reload=True,
        workers=1,
        loop="auto",
        http="h11",
        ws="none",
        timeout_keep_alive=65,
        access_log=True
    )

@app.get("/")
async def root():
    return {"status": "API is running"}