from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional
from app.services.aiAssistant import SimpleAssistant
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/api/properties")
async def get_properties(
    operation_type: Optional[str] = None,
    property_type: Optional[str] = None,
    location: Optional[str] = None
):
    try:
        assistant = SimpleAssistant()
        search_params = {k: v for k, v in {
            "operation_type": operation_type,
            "property_type": property_type,
            "location": location
        }.items() if v is not None}
        
        properties = await assistant.tokko_client.search_properties(search_params)
        return JSONResponse(
            content={
                "status": "success",
                "data": properties
            }
        )
    except Exception as e:
        logger.error(f"Properties error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )