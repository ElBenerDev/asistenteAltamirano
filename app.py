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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.initialize_openai()
    yield
    # Shutdown
    if settings.openai_client:
        await settings.openai_client.close()

# Initialize FastAPI
app = FastAPI(
    title=settings.app_name,
    docs_url=None if os.getenv("PRODUCTION") else "/docs",
    redoc_url=None if os.getenv("PRODUCTION") else "/redoc",
    openapi_url=None if os.getenv("PRODUCTION") else "/openapi.json",
    lifespan=lifespan
)

app.add_middleware(ServerErrorMiddleware)
# Remove HTTPSRedirectMiddleware as Cloud Run handles HTTPS
# app.add_middleware(HTTPSRedirectMiddleware)  # Comment this line

# Update CORS middleware with specific origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# Verify static directory exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        return templates.TemplateResponse(
            "index.html",
            {"request": request}
        )
    except Exception as e:
        logger.error(f"Error rendering index: {str(e)}")
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
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "port": os.getenv("PORT", "8080")
    }

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
    sys.exit(0)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port, 
        log_level="info",
        reload=False,
        workers=1
    )

