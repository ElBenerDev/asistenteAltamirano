import os
import json
import requests
import asyncio  # Add this import
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Optional

# Update logging configuration at the top of the file
import logging
logging.basicConfig(level=logging.INFO)  # Change from DEBUG to INFO
logger = logging.getLogger(__name__)

# Configure loggers to minimize noise
logging.getLogger('httpcore').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('openai').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

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
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("No API key found in environment variables")
        self.client = OpenAI(api_key=api_key)
        self.tokko_client = TokkoClient(TOKKO_API_KEY)
        self.assistant_id = self._create_assistant()
        self.thread_id = None
        self.current_search = {}  # Store search context
        self.search_context = {
            'location': None,
            'operation_type': None,
            'rooms': None,
            'search_ready': False
        }
        self.property_pool = None  # Add this to store filtered properties
        logger.info("Real Estate Assistant initialized")

    def _create_assistant(self) -> str:
        assistant = self.client.beta.assistants.create(
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

        MANEJO DE PRECIOS:
        - Para alquileres, consultar presupuesto máximo mensual
        - Aceptar precios en USD o pesos
        - Entender expresiones como:
          * "hasta X USD/pesos"
          * "máximo X USD/pesos"
          * "que no pase de X USD/pesos"
        
        TÉRMINOS ARGENTINOS:
        - Usar "depto" o "departamento"
        - "Ambientes" (no "habitaciones" ni "dormitorios")
        - "Expensas" para gastos comunes
        - "Cochera" (no "estacionamiento" ni "parking")
        - "PH" para Propiedad Horizontal
        - "Monoambiente" para estudios
        - "Dueño directo" vs "inmobiliaria"
        - "Garantía propietaria" o "seguro de caución"
        
        EXPRESIONES ARGENTINAS:
        - "¿Qué tipo de propiedad estás buscando?"
        - "¿En qué zona te interesa?"
        - "¿Te sirve que tenga cochera?"
        - "¿Necesitás que acepten mascotas?"
        - "¿Te viene bien ver algunas opciones?"
        
        RESPUESTAS NATURALES:
        Usuario: "hola"
        Asistente: "¡Hola! ¿En qué zona estás buscando propiedad?"
        
        Usuario: "busco depto"
        Asistente: "¿En qué barrio te gustaría encontrar el depto?"
        
        Usuario: "en ballester, 2 ambientes"
        Asistente: "¿Estás buscando para alquilar o comprar?"
        
        DATOS IMPORTANTES:
        - Mencionar si acepta mascotas
        - Aclarar si tiene expensas
        - Informar requisitos (garantía, seguro, etc.)
        - Especificar si es apto profesional
        - Indicar si es luminoso/exterior""",
        model="gpt-3.5-turbo"
        )
        return assistant.id

    async def start_conversation(self):
        """Initialize a new conversation thread"""
        thread = self.client.beta.threads.create()
        self.thread_id = thread.id
        return thread.id

    async def chat(self, message: str) -> Dict:
        try:
            logger.info("=== New Chat Message ===")
            logger.info(f"User message: {message}")
            message_lower = message.lower()

            # Update search context based on user message
            context_changed = False

            # Location detection
            if 'ballester' in message_lower:
                self.search_context['location'] = 'Villa Ballester'
                context_changed = True
                logger.info("Location set: Villa Ballester")
            
            # Operation type detection
            if any(word in message_lower for word in ['alquil', 'renta', 'alquilar']):
                self.search_context['operation_type'] = 'Rent'
                context_changed = True
                logger.info("Operation type set: Rent")
            elif any(word in message_lower for word in ['compr', 'venta', 'comprar']):
                self.search_context['operation_type'] = 'Sale'
                context_changed = True
                logger.info("Operation type set: Sale")
            
            # Property type detection
            if any(word in message_lower for word in ['departamento', 'apartamento', 'depto', 'dpto']):
                self.search_context['property_type'] = 'Apartment'
                context_changed = True
                logger.info("Property type set: Apartment")
            elif 'casa' in message_lower:
                self.search_context['property_type'] = 'House'
                context_changed = True
                logger.info("Property type set: House")

            # Get assistant response
            if not self.thread_id:
                await self.start_conversation()

            self.client.beta.threads.messages.create(
                thread_id=self.thread_id,
                role="user",
                content=message
            )

            run = self.client.beta.threads.runs.create(
                thread_id=self.thread_id,
                assistant_id=self.assistant_id
            )

            while True:
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread_id,
                    run_id=run.id
                )
                if run_status.status == 'completed':
                    break
                await asyncio.sleep(1)

            messages = self.client.beta.threads.messages.list(
                thread_id=self.thread_id
            )

            for msg in messages.data:
                if msg.role == "assistant":
                    assistant_response = msg.content[0].text.value
                    logger.info(f"Assistant response: {assistant_response}")

                    # Check if we have minimum required info to search
                    has_minimum_info = all([
                        self.search_context.get('location'),
                        self.search_context.get('operation_type'),
                        self.search_context.get('property_type')
                    ])

                    logger.info(f"Has minimum info: {has_minimum_info}")
                    logger.info(f"Current context: {self.search_context}")

                    if has_minimum_info and context_changed:
                        logger.info("Searching properties with current criteria...")
                        tokko_results = self.tokko_client.search_properties(self.search_context)
                        
                        if not "error" in tokko_results and tokko_results.get('count', 0) > 0:
                            filtered = tokko_results['properties']
                            
                            if filtered:
                                logger.info(f"Found {len(filtered)} matching properties")
                                properties_text = [
                                    self.tokko_client._format_property_with_photos(prop) 
                                    for prop in filtered[:3]
                                ]
                                
                                return {
                                    "type": "text",
                                    "content": (
                                        f"{assistant_response}\n\n"
                                        "🏠 **Propiedades Disponibles**\n\n"
                                        f"{''.join(properties_text)}\n\n"
                                        "💡 *¿Necesitás más información sobre alguna propiedad?*"
                                    )
                                }
                    
                    return {"type": "text", "content": assistant_response}

            return {"type": "error", "content": "No se recibió respuesta del asistente"}

        except Exception as e:
            logger.error(f"Chat error: {str(e)}", exc_info=True)
            return {
                "type": "error", 
                "content": "❌ Lo siento, ocurrió un error. Por favor, intentá nuevamente."
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