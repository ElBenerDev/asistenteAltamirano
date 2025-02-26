import aiohttp
import json
import logging
from typing import Any, Dict, List, Optional
from app.config.settings import settings
from .cache import PropertyCache

logger = logging.getLogger(__name__)

class TokkoClient:
    # Complete property type mapping from API analysis
    PROPERTY_TYPE_MAP = {
        "Apartment": "2",   # AP
        "House": "3",       # HO
        "Land": "1",        # LA
        "Garage": "10",     # GA
        "Industrial Ship": "12",  # IS
        "Bussiness Premises": "7",  # LO
        "Condo": "13",      # PH
        # Add Spanish variations
        "Departamento": "2",
        "Casa": "3",
        "Terreno": "1",
        "Cochera": "10",
        "Nave Industrial": "12",
        "Local": "7",
        "PH": "13"
    }

    # Complete operation type mapping from API analysis
    OPERATION_TYPE_MAP = {
        "Rent": "1",
        "Sale": "2",
        # Spanish variations
        "Alquiler": "1",
        "Venta": "2",
        # Additional variations
        "rent": "1",
        "sale": "2",
        "alquiler": "1",
        "venta": "2"
    }

    def __init__(self):
        self.api_key = settings.tokko_api_key
        # Set default base URL if not configured
        self.base_url = getattr(settings, 'tokko_base_url', 'https://www.tokkobroker.com/api/v1')
        self._cache = {}
        logger.info(f"Tokko client initialized with base_url: {self.base_url}")

    async def search_properties(self, location: str, operation_type: str = None, property_type: str = None, rooms: Optional[int] = None, max_price: Optional[float] = None) -> List[Dict]:
        try:
            # Base parameters
            params = {
                "key": self.api_key.get_secret_value(),
                "limit": "0",
                "format": "json"
            }

            # Build filters dictionary
            filters = {}  # Remove "status": ["ACTIVE"] as it might be interfering

            # Add location if provided
            if location:
                filters["locations"] = [location.strip()]  # Changed to array of locations

            # Handle operation type
            if operation_type:
                op_id = self.OPERATION_TYPE_MAP.get(operation_type.lower())
                if op_id:
                    # Changed to use operation_id instead of operation_types
                    filters["operation_id"] = op_id
                    logger.info(f"Added operation filter: {operation_type} (ID: {op_id})")

            # Handle property type
            if property_type:
                type_id = self.PROPERTY_TYPE_MAP.get(property_type)
                if type_id:
                    # Changed to use type_id instead of property_types
                    filters["type_id"] = type_id
                    logger.info(f"Added property type filter: {property_type} (ID: {type_id})")

            # Add room filter
            if rooms:
                filters["room_amount"] = str(rooms)

            # Add price filter
            if max_price:
                filters["price_max"] = str(max_price)

            # Add filters to params
            params["filters"] = json.dumps(filters)
            logger.info(f"Final search params: {params}")
            logger.info(f"Final filters: {filters}")

            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/property/"  # Changed back to base property endpoint
                logger.info(f"Making request to: {url}")

                async with session.get(url, params=params) as response:
                    logger.info(f"Full request URL: {response.url}")
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Tokko API error: {error_text}")
                        return []

                    data = await response.json()
                    logger.debug(f"Raw API response: {json.dumps(data)[:500]}...")

                    properties = data.get('objects', [])
                    logger.info(f"Found {len(properties)} properties")

                    return properties

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