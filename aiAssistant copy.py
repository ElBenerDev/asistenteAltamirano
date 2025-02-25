import os
import json
import requests
import asyncio
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            
            # Filter by rooms
            if matches and search_params.get('rooms'):
                if prop.get('room_amount') != search_params['rooms']:
                    matches = False
            
            # Filter by price
            if matches and search_params.get('max_price'):
                max_price = search_params['max_price']
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

class SimpleAssistant:
    async def __init__(self):
        self.client = settings.openai_client
        self.tokko_client = settings.tokko_client
        self.assistant_id = await self._create_assistant()
        self.thread_id = None
        self.search_context = {
            'location': None,
            'operation_type': None,
            'property_type': None,
            'rooms': None
        }
        logger.info("Real Estate Assistant initialized")

    async def _create_assistant(self) -> str:
        assistant = await self.client.beta.assistants.create(
            name="Real Estate Assistant",
            instructions="""Sos un asistente inmobiliario profesional para Altamirano Properties en Argentina.

            COMPORTAMIENTO:
            - Usar español argentino siempre (vos, che, etc.)
            - Ser cordial pero profesional
            - Mantener un tono amigable sin perder formalidad
            - NUNCA inventar propiedades
            - NUNCA decir "un momento" o "estoy buscando"
            - NUNCA usar "tú" o expresiones españolas

            RECOLECCIÓN DE INFO (EN ORDEN):
            1. Primero preguntar zona si no la menciona
            2. Después preguntar si busca alquilar o comprar
            3. Después qué tipo de propiedad:
               - Depto
               - Casa
               - Local
               - Oficina
               - PH
            4. Después cantidad de ambientes
            5. Por último, presupuesto (opcional)

            EJEMPLOS DE DIÁLOGO:
            Usuario: "en ballester"
            Asistente: "¿Estás buscando para alquilar o comprar en Villa Ballester?"
            
            Usuario: "alquilar"
            Asistente: "¿Qué tipo de propiedad te interesa? (depto, casa, local, etc.)"
            
            Usuario: "un depto"
            Asistente: "¿Cuántos ambientes necesitás?"

            TÉRMINOS ARGENTINOS:
            - Usar "depto" o "departamento"
            - "Ambientes" (no "habitaciones" ni "dormitorios")
            - "Expensas" para gastos comunes
            - "Cochera" (no "estacionamiento" ni "parking")
            - "PH" para Propiedad Horizontal""",
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
                        }
                    }
                }
            }]
        )
        return assistant.id

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

    async def chat(self, message: str, thread_id: Optional[str] = None) -> Dict:
        try:
            logger.info("=== New Chat Message ===")
            logger.info(f"User message: {message}")

            # Use provided thread_id or create new one
            if thread_id:
                self.thread_id = thread_id
            elif not self.thread_id:
                thread = self.client.beta.threads.create()
                self.thread_id = thread.id
                logger.info(f"Created new thread: {self.thread_id}")

            # Add message to thread
            self.client.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=message
            )

            # Run assistant
            run = self.client.beta.threads.runs.create(
                thread_id=self.thread_id,
                assistant_id=self.assistant_id
            )

            # Wait for completion
            while True:
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread_id,
                    run_id=run.id
                )
                if run.status == 'completed':
                    break
                elif run.status == 'requires_action':
                    # Handle function calls
                    if run.required_action.type == 'submit_tool_outputs':
                        tool_outputs = []
                        for tool_call in run.required_action.submit_tool_outputs.tool_calls:
                            if tool_call.function.name == 'search_properties':
                                args = json.loads(tool_call.function.arguments)
                                results = self.tokko_client.search_properties(args)
                                
                                if results.get('properties'):
                                    properties_data = []
                                    for prop in results['properties']:
                                        operation = next((op for op in prop.get('operations', []) 
                                                    if op.get('prices')), {})
                                        price = next(iter(operation.get('prices', [])), {}).get('price', 'Consultar')
                                        
                                        properties_data.append({
                                            'title': prop.get('publication_title'),
                                            'operation': operation.get('operation_type'),
                                            'price': price,
                                            'rooms': prop.get('room_amount'),
                                            'surface': prop.get('total_surface'),
                                            'expenses': prop.get('expenses'),
                                            'description': prop.get('description'),
                                            'image': next((p['image'] for p in prop.get('photos', []) 
                                                        if p.get('image')), None),
                                            'link': prop.get('public_url')
                                        })
                                    
                                    tool_outputs.append({
                                        "tool_call_id": tool_call.id,
                                        "output": json.dumps({
                                            "type": "properties",
                                            "data": properties_data,
                                            "count": len(properties_data)
                                        })
                                    })
                                else:
                                    tool_outputs.append({
                                        "tool_call_id": tool_call.id,
                                        "output": json.dumps({
                                            "type": "error",
                                            "message": "No se encontraron propiedades"
                                        })
                                    })
                        
                        run = self.client.beta.threads.runs.submit_tool_outputs(
                            thread_id=self.thread_id,
                            run_id=run.id,
                            tool_outputs=tool_outputs
                        )
                await asyncio.sleep(1)

            # Get messages
            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread_id
            )

            for msg in messages.data:
                if msg.role == "assistant":
                    return {
                        "type": "text",
                        "content": msg.content[0].text.value,
                        "thread_id": self.thread_id  # Add this line
                    }

            return {
                "type": "error",
                "content": "No se recibió respuesta del asistente",
                "thread_id": self.thread_id  # Add this line
            }

        except Exception as e:
            logger.error(f"Chat error: {str(e)}", exc_info=True)
            return {
                "type": "error",
                "content": "❌ Lo siento, ocurrió un error. Por favor, intentá nuevamente.",
                "thread_id": self.thread_id  # Add this line
            }

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