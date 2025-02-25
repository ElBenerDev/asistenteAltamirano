import aiohttp
import logging
from typing import Any, Dict, List, Optional
from app.config.settings import settings
from .cache import PropertyCache

logger = logging.getLogger(__name__)

class TokkoClient:
    def __init__(self):
        self.api_key = settings.tokko_api_key
        # Set default base URL if not configured
        self.base_url = getattr(settings, 'tokko_base_url', 'https://www.tokkobroker.com/api/v1')
        self._cache = {}
        logger.info(f"Tokko client initialized with base_url: {self.base_url}")

    async def search_properties(self, location: str, rooms: Optional[int] = None, max_price: Optional[float] = None) -> List[Dict]:
        try:
            params = {
                "key": self.api_key,
                "location": location,
                "operation_type": "1",  # For rent
                "status": "ACTIVE"
            }
            
            if rooms:
                params["rooms"] = rooms
            if max_price:
                params["price_max"] = max_price

            logger.info(f"Searching properties with params: {params}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/property/search", params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Tokko API error: {error_text}")
                        return []
                    
                    data = await response.json()
                    logger.info(f"Found {len(data.get('objects', []))} properties")
                    return data.get("objects", [])

        except Exception as e:
            logger.error(f"Error searching properties: {str(e)}", exc_info=True)
            return []

    async def get_property_detail(self, property_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific property"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/property/{property_id}/",
                    headers=self.headers
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"Error getting property details: {error_text}")
                        return None
        except Exception as e:
            logger.error(f"Failed to get property details: {str(e)}")
            return None

    async def filter_properties(self, **kwargs) -> Dict[str, Any]:
        """Filter properties with specific criteria"""
        params = {k: v for k, v in kwargs.items() if v is not None}
        return await self.search_properties(params)

    def _format_property_details(self, prop: Dict) -> Dict:
        """Extract and format property details from Tokko data"""
        # Get operation details
        operation = next((op for op in prop.get('operations', []) if op.get('prices')), {})
        price_data = next(iter(operation.get('prices', [])), {})
        
        # Extract features from property data
        features = []
        if prop.get('parking_amount'):
            features.append('Cochera')
        if prop.get('balcony_amount'):
            features.append('Balcón')
        if prop.get('has_pool'):
            features.append('Pileta')
        if prop.get('has_grill'):
            features.append('Parrilla')
        if prop.get('has_garden'):
            features.append('Jardín')
        
        return {
            'title': prop.get('publication_title', ''),
            'address': prop.get('location', {}).get('address', ''),
            'price': price_data.get('price', 'Consultar'),
            'price_formatted': f"ARS {price_data.get('price', 0):,}",
            'operation_type': operation.get('operation_type', 'Alquiler'),
            'area': f"{prop.get('total_surface', 'N/A')} m²",
            'room_amount': prop.get('room_amount', 'N/A'),
            'bathroom_amount': prop.get('bathroom_amount', 'N/A'),
            'expenses': prop.get('expenses', 0),
            'expenses_formatted': f"ARS {prop.get('expenses', 0):,}",
            'description': prop.get('description', ''),
            'features': features,
            'image_url': next((p['image'].get('url', '') if isinstance(p.get('image'), dict) else p.get('image', '')
                            for p in prop.get('photos', []) if p.get('image')), ''),
            'url': prop.get('public_url', '#')
        }

    def format_property_response(self, properties: list) -> str:
        """Format properties into markdown for the chat response"""
        formatted = []
        for idx, prop in enumerate(properties, 1):
            details = self._format_property_details(prop)
            
            # Build property description with features
            features_text = ' • '.join(details['features']) if details['features'] else 'Sin amenities'
            
            property_text = (
                f"{idx}. **{details['title']}**\n"
                f"   - Dirección: {details['address']}\n"
                f"   - Precio: {details['price_formatted']}\n"
                f"   - {details['operation_type']}\n"
                f"   - Superficie: {details['area']}\n"
                f"   - Ambientes: {details['room_amount']}\n"
                f"   - Baños: {details['bathroom_amount']}\n"
                f"   - Gastos comunes: {details['expenses_formatted']}\n"
                f"   - Amenities: {features_text}\n"
                f"   - Descripción: {details['description']}\n"
                f"   - ![Imagen]({details['image_url']})\n"
                f"   - [Más información]({details['url']})\n"
            )
            formatted.append(property_text)
        
        return "\n\n".join(formatted)