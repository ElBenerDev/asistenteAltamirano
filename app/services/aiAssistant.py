import os
import json
import requests
import asyncio
from datetime import datetime
from openai import AsyncOpenAI
from dotenv import load_dotenv
from typing import Dict, Optional, Any  # Added Any to imports
import logging
from app.config import settings  # Add settings import

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Add file handler for debugging
file_handler = logging.FileHandler('assistant_debug.log')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Load environment variables
load_dotenv()

TOKKO_API_KEY = os.getenv("TOKKO_API_KEY")
TOKKO_BASE_URL = os.getenv("TOKKO_BASE_URL")

def format_property_info(prop: Dict) -> str:
    """Format property information for display"""
    return (
        f"- Type: {prop.get('type', {}).get('name', 'Unknown')}\n"
        f"  Operation: {prop.get('operation_type', {}).get('name', 'Unknown')}\n"
        f"  Price: {prop.get('currency', 'USD')} {prop.get('price', 'N/A')}\n"
        f"  Location: {prop.get('location', {}).get('address', 'No address')}\n"
        f"  Area: {prop.get('total_surface')} m²\n"
        f"  Rooms: {prop.get('room_amount', 'N/A')}\n"
        f"  Description: {prop.get('description', 'No description')[:100]}...\n"
    )

class PropertyCache:
    def __init__(self):
        self.properties = []
        self.last_updated = None
        self.rental_properties = []
        self.sale_properties = []

    def needs_update(self) -> bool:
        # Implement logic to determine if the cache needs to be updated
        return True

    def update_cache(self, properties: list):
        self.properties = properties
        self.last_updated = datetime.now()
        
        # Separate properties by operation type
        self.rental_properties = []
        self.sale_properties = []
        
        for prop in properties:
            for operation in prop.get('operations', []):
                if operation.get('operation_type', '').lower() == 'rent':
                    self.rental_properties.append(prop)
                    break
                elif operation.get('operation_type', '').lower() == 'sale':
                    self.sale_properties.append(prop)
                    break

    def filter_properties(self, search_params: Dict) -> list:
        """Filter properties based on search parameters"""
        # First, select the correct property pool based on operation type
        if search_params.get('operation_type') == 'Rent':
            property_pool = self.rental_properties
        elif search_params.get('operation_type') == 'Sale':
            property_pool = self.sale_properties
        else:
            property_pool = self.properties

        filtered = []
        for prop in property_pool:
            matches = True
            
            # Filter by property type
            if search_params.get('property_type'):
                prop_type = search_params['property_type'].lower()
                if prop.get('type', {}).get('name', '').lower() != prop_type:
                    matches = False
            
            # Filter by location
            if matches and search_params.get('location'):
                location = search_params['location'].lower()
                prop_location = prop.get('location', {}).get('name', '').lower()
                if location not in prop_location:
                    matches = False
            
            # Update room filtering to use minimum rooms
            if matches and search_params.get('min_rooms'):
                min_rooms = search_params['min_rooms']
                prop_rooms = prop.get('room_amount', 0)
                if prop_rooms < min_rooms:  # Changed from exact match to minimum
                    matches = False
            
            # Filter by price
            if matches and search_params.get('max_price'):
                max_price = search_params.get('max_price')
                currency = search_params.get('currency', 'USD')
                
                # Get property price
                for operation in prop.get('operations', []):
                    if operation.get('operation_type') == search_params.get('operation_type'):
                        prices = operation.get('prices', [])
                        if prices:
                            price = prices[0]
                            if (price.get('currency') == currency and 
                                price.get('price', float('inf')) > max_price):
                                matches = False
                            break
            
            if matches:
                filtered.append(prop)
        
        return filtered

class TokkoClient:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or TOKKO_API_KEY
        self.base_url = TOKKO_BASE_URL
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        self.cache = PropertyCache()
        logger.info("Tokko Client initialized with cache")

    def get_api_metadata(self) -> Dict:
        """Get all available metadata from the API"""
        try:
            logger.info("\n=== Fetching API Metadata ===")
            
            # Get property types
            url = f"{self.base_url}/property/property_types/"
            params = {"key": self.api_key, "format": "json", "lang": "es"}
            response = requests.get(url, params=params, headers=self.headers)
            self.property_types = response.json()
            logger.info(f"Property Types: {json.dumps(self.property_types, indent=2)}")

            # Get operation types
            url = f"{self.base_url}/property/operation_types/"
            response = requests.get(url, params=params, headers=self.headers)
            self.operation_types = response.json()
            logger.info(f"Operation Types: {json.dumps(self.operation_types, indent=2)}")

            # Get available tags
            url = f"{self.base_url}/property/tags/"
            response = requests.get(url, params=params, headers=self.headers)
            self.tags = response.json()
            logger.info(f"Available Tags: {json.dumps(self.tags, indent=2)}")

            return {
                "property_types": self.property_types,
                "operation_types": self.operation_types,
                "tags": self.tags
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch API metadata: {str(e)}")
            return {"error": str(e)}

    def search_properties(self, search_params: Dict = None) -> Dict:
        try:
            logger.info("\n=== Tokko Search ===")
            logger.info(f"Search parameters: {search_params}")
            
            # Initial API call to get all properties
            if self.cache.needs_update():
                url = f"{self.base_url}/property/"
                params = {
                    "key": self.api_key,
                    "format": "json",
                    "lang": "es",
                    "limit": 100,
                    "active": True  # Only get active listings
                }
                
                logger.info("Fetching properties from Tokko API...")
                response = requests.get(url, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                if data.get('objects'):
                    self.cache.update_cache(data['objects'])
                    logger.info(f"Cache updated with {len(data['objects'])} properties")
            
            # Filter properties based on search parameters
            if search_params:
                filtered = self.cache.filter_properties(search_params)
                logger.info(f"Found {len(filtered)} matching properties")
                logger.info(f"Operation type: {search_params.get('operation_type')}")
                logger.info(f"Property type: {search_params.get('property_type')}")
                
                return {
                    "count": len(filtered),
                    "properties": filtered,
                    "total": len(filtered)
                }
            
            return {
                "count": len(self.cache.properties),
                "properties": self.cache.properties,
                "total": len(self.cache.properties)
            }

        except Exception as e:
            logger.error(f"Search failed: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def _get_simple_listing(self) -> Dict:
        """Get simple property listing"""
        try:
            url = f"{self.base_url}/property/"
            params = {"key": self.api_key, "limit": 20}
            response = requests.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Simple listing failed: {str(e)}")
            return {"error": str(e)}

    def _format_property_with_photos(self, prop: Dict) -> str:
        try:
            # Get operation and price info
            price_info = ""
            operation_type = ""
            for op in prop.get('operations', []):
                prices = op.get('prices', [])
                if prices:
                    price = prices[0]
                    price_info = f"{price.get('currency', 'ARS')} {price.get('price', 'N/A'):,}"
                    operation_type = op.get('operation_type', 'N/A')
                    break

            # Format property details in HTML/CSS friendly way
            property_html = f"""
            <div class="property-card">
                <h3 class="property-title">
                    {prop.get('publication_title', 'Propiedad Destacada')}
                </h3>
                
                <div class="property-location">
                    <i class="fas fa-map-marker-alt"></i>
                    {prop.get('address', 'Consultar dirección')}
                </div>
                
                <div class="property-details">
                    <div class="detail-item">
                        <i class="fas fa-dollar-sign"></i>
                        <span>{price_info}</span>
                    </div>
                    <div class="detail-item">
                        <i class="fas fa-home"></i>
                        <span>{operation_type}</span>
                    </div>
                    <div class="detail-item">
                        <i class="fas fa-bed"></i>
                        <span>{prop.get('room_amount', 'N/A')} Ambientes</span>
                    </div>
                    <div class="detail-item">
                        <i class="fas fa-bath"></i>
                        <span>{prop.get('bathroom_amount', 'N/A')} Baños</span>
                    </div>
                    <div class="detail-item">
                        <i class="fas fa-ruler-combined"></i>
                        <span>{prop.get('total_surface', 'N/A')} m²</span>
                    </div>
                </div>
            """

            # Add amenities if available
            amenities = []
            if prop.get('parking_amount'):
                amenities.append('<i class="fas fa-car"></i> Cochera')
            if prop.get('balcony_amount'):
                amenities.append('<i class="fas fa-sun"></i> Balcón')
            if prop.get('has_pool'):
                amenities.append('<i class="fas fa-swimming-pool"></i> Pileta')
            if prop.get('accepts_pets'):
                amenities.append('<i class="fas fa-paw"></i> Acepta mascotas')

            if amenities:
                property_html += f"""
                <div class="property-details">
                    {''.join(f'<div class="detail-item">{amenity}</div>' for amenity in amenities)}
                </div>
                """

            # Add photos
            photo_urls = []
            for photo in prop.get('photos', [])[:3]:
                if photo.get('image'):
                    photo_urls.append(photo['image']['url'] if isinstance(photo['image'], dict) else photo['image'])

            if photo_urls:
                property_html += f"""
                <div class="property-photos">
                    {''.join(f'<img src="{url}" alt="Foto de propiedad" loading="lazy">' for url in photo_urls)}
                </div>
                """

            # Add description
            description = prop.get('description', '').strip()
            if description:
                preview = description[:200] + "..." if len(description) > 200 else description
                property_html += f"""
                <div class="property-description">
                    {preview}
                </div>
                """

            # Add link to full property
            public_url = prop.get('public_url')
            if public_url:
                property_html += f"""
                <a href="{public_url}" class="property-link" target="_blank">
                    <i class="fas fa-external-link-alt"></i>
                    Ver Propiedad Completa
                </a>
                """

            property_html += """
                <hr class="property-separator">
            </div>
            """

            return property_html

        except Exception as e:
            logger.error(f"Error formatting property: {str(e)}")
            return '<div class="error-message">❌ Error al formatear la propiedad</div>'

class OpenAIError(Exception):
    """Custom exception for OpenAI specific errors"""
    pass

class SimpleAssistant:
    _instance = None
    _assistant_id = None
    _threads_cache = {}  # Add thread caching
    
    def __init__(self):
        self.client = settings.openai_client
        self.tokko_client = TokkoClient()  # Add TokkoClient initialization
        self.polling_interval = 2.0  # Increased base interval
        self.max_attempts = 120  # Allow more attempts
        self.max_threads = 10

    @classmethod
    async def get_instance(cls) -> 'SimpleAssistant':
        if not cls._instance:
            cls._instance = cls()
            await cls._instance.initialize()
        return cls._instance

    async def initialize(self) -> None:
        """Initialize the assistant (only if needed)"""
        if not self._assistant_id:
            self._assistant_id = await self._create_assistant()
            logger.info("Assistant initialized with ID: %s", self._assistant_id)

    async def _create_assistant(self) -> str:
        try:
            assistant = await self.client.beta.assistants.create(
                name="Real Estate Assistant",
                instructions="""Sos un asistente inmobiliario profesional para Altamirano Properties en Argentina.

            COMPORTAMIENTO:
            - Usar español argentino siempre (vos, che, etc.)
            - Ser cordial pero profesional
            - Mantener un tono amigable sin perder formalidad
            - Mantener CONTEXTO de la conversación
            - NUNCA inventar propiedades
            - NUNCA repetir preguntas ya respondidas
            - NUNCA volver a preguntar información ya proporcionada
            - NUNCA usar "tú" o expresiones españolas

            MANEJO DE CONTEXTO:
            - Si el usuario menciona "alquilar/alquiler" → operation_type = "Rent"
            - Si menciona "comprar/compra/venta" → operation_type = "Sale"
            - Si dice "depto/departamento" → property_type = "Apartment"
            - Si dice "casa" → property_type = "House"
            - Si dice "local" → property_type = "Local"
            - Si dice "oficina" → property_type = "Office"
            - Números mencionados pueden ser ambientes o precios según contexto
            
            PROCESO DE BÚSQUEDA:
            1. Recolectar información faltante en orden natural
            2. Una vez tengas location + operation_type + property_type → hacer búsqueda
            3. Si menciona ambientes, usar como filtro adicional
            4. Si menciona precio, usar como máximo

            EJEMPLOS DE DIÁLOGO NATURAL:
            Usuario: "busco alquilar un depto en ballester"
            → Entender: operation_type="Rent", property_type="Apartment", location="Villa Ballester"
            → Preguntar: "¿Cuántos ambientes necesitás?"

            Usuario: "depto 2 ambientes en ballester"
            → Entender: property_type="Apartment", rooms=2, location="Villa Ballester"
            → Preguntar: "¿Estás buscando para alquilar o comprar?"

            ZONAS CONOCIDAS:
            - "ballester" = "Villa Ballester"
            - "malaver" = "Villa Malaver"
            - "chilavert" = "Chilavert"
            - "suarez" = "José León Suárez"
            - "san martin" = "San Martín"

            TÉRMINOS ARGENTINOS:
            - "depto/departamento" = Apartment
            - "ambientes" = rooms
            - "expensas" = gastos comunes
            - "cochera" = parking
            - "PH" = tipo especial de departamento""",
                model="gpt-3.5-turbo",
                tools=[{
                    "type": "function",
                    "function": {
                        "name": "search_properties",
                        "description": "Search for properties based on criteria",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "location": {"type": "string"},
                                "operation_type": {"type": "string", "enum": ["Rent", "Sale"]},
                                "property_type": {"type": "string", "enum": ["Apartment", "House", "Office", "Local"]},
                                "rooms": {"type": "integer", "minimum": 1},
                                "max_price": {"type": "number"}
                            },
                            "required": ["location", "operation_type", "property_type"]
                        }
                    }
                }]
            )
            return assistant.id
        except Exception as e:
            logger.error("Failed to create assistant: %s", str(e))
            raise

    async def _get_or_create_thread(self) -> str:
        """Create a new thread or clean up old ones"""
        try:
            # Cleanup old threads if needed
            if len(self._threads_cache) >= self.max_threads:
                oldest_thread = min(self._threads_cache.items(), key=lambda x: x[1])[0]
                self._threads_cache.pop(oldest_thread)
            
            # Create new thread
            thread = await self.client.beta.threads.create()
            self._threads_cache[thread.id] = datetime.now()
            return thread.id
            
        except Exception as e:
            logger.error("Thread creation failed: %s", str(e))
            raise OpenAIError(f"Failed to create thread: {str(e)}")

    async def chat(self, message: str, thread_id: str = None) -> dict:
        try:
            current_thread = thread_id or await self._get_or_create_thread()
            
            logger.info("=== Chat Session ===")
            logger.info(f"Thread ID: {current_thread}")
            logger.info(f"User Message: {message}")

            # Add message to thread
            await self.client.beta.threads.messages.create(
                thread_id=current_thread,
                role="user",
                content=message
            )

            # Create run
            run = await self.client.beta.threads.runs.create(
                thread_id=current_thread,
                assistant_id=self._assistant_id
            )
            
            logger.info(f"Run ID: {run.id}")

            attempts = 0
            while attempts < self.max_attempts:
                try:
                    status = await self.client.beta.threads.runs.retrieve(
                        thread_id=current_thread,
                        run_id=run.id
                    )
                    
                    if status.status == "completed":
                        messages = await self.client.beta.threads.messages.list(
                            thread_id=current_thread,
                            limit=10
                        )
                        
                        response = {
                            "content": messages.data[0].content[0].text.value,
                            "thread_id": current_thread,
                            "status": status.status
                        }
                        
                        return response

                    if status.status in ["failed", "cancelled", "expired"]:
                        error_msg = f"OpenAI run {status.status}"
                        if hasattr(status, 'last_error'):
                            error_msg += f": {status.last_error}"
                        logger.error(error_msg)
                        raise OpenAIError(error_msg)

                    if status.status == "requires_action":
                        logger.info("Run requires action - checking tool calls")
                        tool_outputs = await self._handle_tool_calls(status, current_thread, run.id)
                        logger.info(f"Tool outputs: {json.dumps(tool_outputs, indent=2)}")
                        
                        # Include function output in response
                        if tool_outputs:
                            response = {
                                "content": "",  # Will be updated with final message
                                "thread_id": current_thread,
                                "status": status.status,
                                "function_output": tool_outputs[0]["output"]
                            }
                            return response

                    await asyncio.sleep(self.polling_interval)
                    attempts += 1

                except Exception as e:
                    if "429" in str(e):
                        logger.warning("Rate limit hit, waiting...")
                        await asyncio.sleep(5)
                        continue
                    raise

            raise OpenAIError("OpenAI request timed out")

        except Exception as e:
            logger.error(f"Chat error: {str(e)}")
            raise

    async def _handle_tool_calls(self, run_status, thread_id: str, run_id: str) -> list:
        """Handle tool calls from the assistant"""
        tool_outputs = []
        
        for tool_call in run_status.required_action.submit_tool_outputs.tool_calls:
            try:
                logger.info(f"Processing tool call: {tool_call.function.name}")
                
                if tool_call.function.name == "search_properties":
                    # Parse the arguments
                    args = json.loads(tool_call.function.arguments)
                    logger.info(f"Search parameters: {args}")
                    
                    # Map the parameters correctly for Tokko API
                    search_params = {
                        'location': args.get('location'),
                        'operation_type': args.get('operation_type'),
                        'property_type': args.get('property_type'),
                        'min_rooms': args.get('rooms'),
                        'max_price': args.get('max_price')
                    }
                    
                    logger.info(f"Searching with params: {search_params}")
                    
                    # Execute the search
                    search_results = self.tokko_client.search_properties(search_params)
                    
                    if "error" in search_results:
                        logger.error(f"Search error: {search_results['error']}")
                        output = {
                            "type": "error",
                            "message": search_results["error"]
                        }
                    else:
                        properties = search_results.get("properties", [])
                        formatted_properties = []
                        
                        for prop in properties:
                            # Get operation details
                            operation = next((op for op in prop.get('operations', []) 
                                            if op.get('prices')), {})
                            
                            # Format price
                            price_info = "Consultar"
                            if operation and operation.get('prices'):
                                price = operation['prices'][0]
                                price_info = f"{price.get('currency', 'ARS')} {price.get('price', 'Consultar'):,}"
                            
                            # Format property
                            formatted_prop = {
                                "title": prop.get('publication_title', 'Propiedad'),
                                "address": prop.get('fake_address', 'Consultar dirección'),
                                "operation_type": operation.get('operation_type', 'N/D'),
                                "property_type": prop.get('type', {}).get('name', 'N/D'),
                                "price": price_info,
                                "rooms": prop.get('room_amount', 'N/D'),
                                "surface": f"{prop.get('total_surface', 'N/D')} m²",
                                "expenses": f"ARS {prop.get('expenses', 0):,}",
                                "description": prop.get('description', '').strip(),
                                "image_url": next((p['image'] for p in prop.get('photos', []) 
                                                 if p.get('image')), None),
                                "url": prop.get('public_url', '')
                            }
                            formatted_properties.append(formatted_prop)
                        
                        logger.info(f"Found {len(formatted_properties)} properties")
                        output = {
                            "type": "properties",
                            "data": formatted_properties,
                            "count": len(formatted_properties)
                        }
                    
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(output, ensure_ascii=False)
                    })
                    
                else:
                    logger.warning(f"Unknown function call: {tool_call.function.name}")
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps({"error": "Función no implementada"})
                    })
            
            except Exception as e:
                logger.error(f"Error processing tool call: {str(e)}")
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": json.dumps({"error": str(e)})
                })
        
        # Submit all tool outputs
        if tool_outputs:
            await self.client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run_id,
                tool_outputs=tool_outputs
            )
        
        return tool_outputs

    def format_property_response(self, properties: list) -> str:
        """Format properties into a structured markdown response."""
        formatted = []
        for idx, prop in enumerate(properties, 1):
            # Get operation details
            operation = next((op for op in prop.get('operations', []) 
                            if op.get('prices')), {})
            
            # Get the first price if available
            price_data = next(iter(operation.get('prices', [])), {})
            price = f"{price_data.get('price', 'Consultar'):,}" if price_data else 'Consultar'
            
            # Format property text with full details
            property_text = (
                f"{idx}. **{prop.get('publication_title', 'Departamento')}**\n"
                f"   - Operación: {operation.get('operation_type', 'N/D')}\n"
                f"   - Tipo: {prop.get('type', {}).get('name', 'Departamento')}\n"
                f"   - Precio: ${price}\n"
                f"   - Ambientes: {prop.get('room_amount', 'N/D')}\n"
                f"   - Superficie: {prop.get('total_surface', 'N/D')} m2\n"
                f"   - Expensas: ${prop.get('expenses', 0):,}\n"
                f"   - Descripción: {prop.get('description', 'Sin descripción')}\n"
            )

            # Add photos if available
            if prop.get('photos'):
                first_photo = prop['photos'][0]
                image_url = first_photo.get('image', {}).get('url', '') if isinstance(first_photo.get('image'), dict) else first_photo.get('image', '')
                if image_url:
                    property_text += f"   - imagen:{image_url}\n"

            # Add link to property
            if prop.get('public_url'):
                property_text += f"   - [Ver más detalles]({prop['public_url']})\n"

            formatted.append(property_text)
        
        # Join all properties with double newlines for better readability
        return "\n\n".join(formatted)

    def search_properties(self, args):
        search_params = {
            'location': args.get('location'),
            'operation_type': args.get('operation_type'),
            'property_type': args.get('property_type'),
            # Change exact room match to minimum rooms
            'min_rooms': args.get('rooms'),  # Instead of 'rooms'
            'max_price': args.get('max_price')
        }

# Add to top of file if not already present
__all__ = ['SimpleAssistant', 'OpenAIError']

# Example usage
if __name__ == "__main__":
    async def test_assistant():
        assistant = SimpleAssistant()
        
        # Test different property queries
        queries = [
            "Busco departamento en venta en Villa Ballester hasta 100000 USD",
            "Hay casas en alquiler en Chilavert?",
            "Necesito un local comercial en Villa Ballester",
            "¿Cuánto cuesta un departamento de 2 ambientes en Malaver?"
        ]
        
        for query in queries:
            print(f"\nQuery: {query}")
            response = await assistant.chat(query)
            print(f"Response: {response['content']}")

    asyncio.run(test_assistant())
