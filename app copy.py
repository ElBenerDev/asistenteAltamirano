from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from config.settings import settings
from aiAssistant import SimpleAssistant  # Fixed import
import logging
import logging.handlers
import os
from openai import OpenAI
from datetime import datetime
from typing import Dict, Optional
from starlette.middleware.errors import ServerErrorMiddleware
from pydantic import BaseModel
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import signal
import sys
from contextlib import asynccontextmanager
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Update the lifespan manager to be more robust
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Starting application...")
        await settings.initialize_openai()
        await settings.initialize_tokko()  # Now properly defined
        yield
    finally:
        logger.info("Application shutdown")

# Initialize FastAPI
app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    root_path="",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

app.add_middleware(ServerErrorMiddleware)
# Remove HTTPSRedirectMiddleware as Cloud Run handles HTTPS
# app.add_middleware(HTTPSRedirectMiddleware)  # Comment this line

# Update CORS middleware with specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Temporarily allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    try:
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "upgrade-insecure-requests"
        return response
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request error: {e}")
        raise

# Get the absolute path to the static and templates directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

# Ensure directories exist
os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        logger.info(f"Processing home request from {request.client.host}")
        logger.info(f"Template directory: {templates_dir}")
        templates_list = os.listdir(templates_dir)
        logger.info(f"Available templates: {templates_list}")
        
        # Try loading index.html first
        try:
            response = templates.TemplateResponse(
                "index.html",
                {"request": request}
            )
            logger.info("index.html template rendered successfully")
            return response
        except Exception as e:
            logger.warning(f"Failed to render index.html: {e}, falling back to base.html")
            # Fall back to base template
            return templates.TemplateResponse(
                "base.html",
                {
                    "request": request,
                    "title": "Asistente Altamirano - Servicio Activo"
                }
            )
    except Exception as e:
        logger.error(f"Error in home endpoint: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

class ChatMessage(BaseModel):
    message: str
    thread_id: Optional[str] = None

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
        message = data.get("message")
        thread_id = data.get("thread_id")

        if not message:
            return JSONResponse(
                status_code=400,
                content={"error": "Message is required", "status": "error"}
            )

        assistant = SimpleAssistant()
        response = await assistant.chat(message=message, thread_id=thread_id)
        
        return {
            "response": response["content"],
            "thread_id": response["thread_id"],
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "status": "error"}
        )

@app.get("/health")
async def health_check():
    """Health check endpoint for Cloud Run"""
    try:
        # Verify critical services are initialized
        if not hasattr(settings, 'openai_client'):
            raise Exception("OpenAI client not initialized")
        if not hasattr(settings, 'tokko_client'):
            raise Exception("Tokko client not initialized")
            
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": os.getenv("K_REVISION", "local"),
            "services": {
                "openai": "initialized" if settings.openai_client else "not initialized",
                "tokko": "initialized" if settings.tokko_client else "not initialized"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/properties")
async def get_properties(
    operation_type: Optional[str] = None,
    property_type: Optional[str] = None,
    location: Optional[str] = None
):
    """Get properties from Tokko API"""
    try:
        assistant = SimpleAssistant()
        search_params = {k: v for k, v in {
            "operation_type": operation_type,
            "property_type": property_type,
            "location": location
        }.items() if v is not None}
        
        properties = await assistant.tokko_client.search_properties(search_params)
        return {
            "status": "success",
            "data": properties
        }
    except Exception as e:
        logger.error(f"Error fetching properties: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/debug")
async def debug():
    """Debug endpoint to check application state"""
    try:
        return {
            "env": {k: v for k, v in os.environ.items() if not k.lower().contains('key')},
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
    except Exception as e:
        logger.error(f"Debug endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.exception_handler(500)
async def internal_error(request: Request, exc: Exception):
    logger.error(f"Internal Server Error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": "Internal Server Error",
            "detail": str(exc) if app.debug else None
        }
    )

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global error handler: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"message": "Internal server error"}
    )

@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(status_code=204)

def handle_exit(signum, frame):
    logger.info(f"Received signal {signum}")
    # Graceful shutdown
    try:
        if hasattr(settings, 'openai_client'):
            settings.openai_client.aclose()
        logger.info("Cleanup complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    finally:
        sys.exit(0)

# Update main execution block
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8080"))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )