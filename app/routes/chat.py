from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
from app.services.aiAssistant import SimpleAssistant, OpenAIError
from pydantic import BaseModel
import logging
import json

logger = logging.getLogger(__name__)
router = APIRouter()

class ChatMessage(BaseModel):
    content: str
    thread_id: str | None = None

@router.post("/chat")
async def chat(message: ChatMessage):
    try:
        logger.info("="*50)
        logger.info("NEW CHAT REQUEST STARTED")
        
        assistant = await SimpleAssistant.get_instance()
        response = await assistant.chat(message=message.content, thread_id=message.thread_id)
        
        # Debug the full response
        logger.info("="*50)
        logger.info("FULL RESPONSE:")
        logger.info(json.dumps(response, indent=2))
        
        logger.info("="*50)
        logger.info("RESPONSE KEYS:")
        logger.info(f"Keys in response: {list(response.keys())}")
        if "function_output" in response:
            logger.info(f"Function output type: {type(response['function_output'])}")
            logger.info(f"Function output preview: {str(response['function_output'])[:200]}")
        
        logger.info("="*50)
        logger.info("CHECKING RESPONSE TYPE")
        logger.info(f"Has function output: {bool(response.get('function_output'))}")
        
        # Check for function outputs in all possible locations
        function_output = (
            response.get("function_output") or 
            response.get("tool_outputs", [{}])[0].get("output") or
            response.get("outputs", {}).get("properties")
        )
        
        if function_output:
            try:
                logger.info("="*50)
                logger.info("PROCESSING FUNCTION OUTPUT")
                logger.info(f"Raw output: {function_output[:200]}...")
                
                properties_data = (
                    json.loads(function_output) 
                    if isinstance(function_output, str) 
                    else function_output
                )
                
                logger.info(f"Properties data type: {properties_data.get('type')}")
                
                # Check specifically for properties data
                if (properties_data.get("type") == "properties" and 
                    isinstance(properties_data.get("data"), list) and 
                    len(properties_data["data"]) > 0):
                    
                    logger.info("="*50)
                    logger.info("GENERATING PROPERTY CARDS HTML")
                    
                    html = '<div class="properties-grid">'
                    for prop in properties_data["data"]:
                        html += f'''
                            <div class="property-card">
                                <div class="property-image">
                                    <img src="{prop['image_url']}" alt="{prop['title']}">
                                    <div class="property-tags">
                                        <span class="tag operation-tag">{prop['operation_type']}</span>
                                        <span class="tag price-tag">{prop['price']}</span>
                                    </div>
                                </div>
                                <div class="property-content">
                                    <h3 class="property-title">{prop['title']}</h3>
                                    <p class="property-location"><i class="fas fa-map-marker-alt"></i> {prop['address']}</p>
                                    <div class="property-details">
                                        <span class="detail-item"><i class="fas fa-ruler-combined"></i> {prop.get('surface', 'N/A')}</span>
                                        <span class="detail-item"><i class="fas fa-money-bill-wave"></i> Exp: {prop.get('expenses', 'N/A')}</span>
                                    </div>
                                    <p class="property-description">{prop['description'][:150]}...</p>
                                    <a href="{prop['url']}" class="property-button" target="_blank">
                                        Ver más detalles <i class="fas fa-external-link-alt"></i>
                                    </a>
                                </div>
                            </div>
                        '''
                    html += '</div>'
                    
                    logger.info("="*50)
                    logger.info("SENDING HTML RESPONSE")
                    
                    return JSONResponse(content={
                        "response": html,
                        "status": "success",
                        "thread_id": response.get("thread_id"),
                        "isHtml": True
                    })
                else:
                    logger.info("Invalid properties data structure")
                    
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing properties: {str(e)}")

        logger.info("="*50)
        logger.info("FALLING BACK TO PLAIN TEXT")
        return JSONResponse(content={
            "response": str(response.get("content", "")),
            "status": "success",
            "thread_id": response.get("thread_id"),
            "isHtml": False
        })

    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return JSONResponse(
            content={"error": str(e), "status": "error"},
            status_code=500
        )

def parse_properties(content):
    logger.info("="*50)
    logger.info("PARSING PROPERTIES")
    logger.info(f"Raw content: {content[:200]}...")  # First 200 chars of content
    """Parse markdown content into structured property data"""
    properties = []
    current_property = None
    
    for line in content.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        if line.startswith(('1.', '2.', '3.')) and '**' in line:
            logger.info(f"Found property: {line}")
            if current_property:
                properties.append(current_property)
            title = line.split('**')[1].strip('* ')
            current_property = {
                'title': title,
                'operation_type': 'Alquiler',  # Default to rental
                'features': []
            }
            
        elif current_property and line.startswith(' - '):
            if ': ' in line:
                key, value = line.strip(' -').split(': ', 1)
                key = key.lower()
                
                if 'dirección' in key:
                    current_property['address'] = value
                elif 'precio' in key:
                    current_property['price'] = value
                    # Format price with comma thousands separator
                    try:
                        price_num = int(''.join(filter(str.isdigit, value)))
                        current_property['price_formatted'] = f"ARS {price_num:,}"
                    except:
                        current_property['price_formatted'] = value
                elif 'superficie' in key:
                    current_property['area'] = value
                    if value != 'No especificada':
                        current_property['features'].append(f"Superficie: {value}")
                elif 'gastos' in key:
                    current_property['expenses'] = value
                    try:
                        exp_num = int(''.join(filter(str.isdigit, value)))
                        current_property['expenses_formatted'] = f"ARS {exp_num:,}"
                    except:
                        current_property['expenses_formatted'] = value
                elif 'descripción' in key:
                    current_property['description'] = value
                    # Extract features from description
                    features = []
                    if 'cochera' in value.lower():
                        features.append('Cochera')
                    if 'balcón' in value.lower():
                        features.append('Balcón')
                    if 'piscina' in value.lower():
                        features.append('Piscina')
                    if 'quincho' in value.lower():
                        features.append('Quincho')
                    if 'parrilla' in value.lower():
                        features.append('Parrilla')
                    current_property['features'].extend(features)
            
        elif current_property and '![' in line:
            logger.info(f"Processing image line: {line}")
            try:
                # Extract image URL between parentheses
                img_start = line.find('(') + 1
                img_end = line.find(')', img_start)
                if img_start > 0 and img_end > 0:
                    image_url = line[img_start:img_end].strip()
                    current_property['image_url'] = image_url
                    logger.info(f"Found image URL: {image_url}")
            except Exception as e:
                logger.error(f"Error parsing image URL: {str(e)}")
                current_property['image_url'] = ''
        elif current_property and '[más información]' in line.lower():
            current_property['url'] = line.split('(')[1].split(')')[0]
    
    if current_property:
        logger.info("Property details:")
        logger.info(json.dumps(current_property, indent=2))
        properties.append(current_property)
    
    return properties

def render_properties_grid(properties):
    """Generate HTML grid for properties"""
    html = '<div class="properties-grid">'
    
    for prop in properties:
        # Get property details from Tokko data
        operation = next((op for op in prop.get('operations', []) if op.get('prices')), {})
        price_data = next(iter(operation.get('prices', [])), {})
        
        # Get the first image if available
        image_url = next((
            p['image'].get('url', '') if isinstance(p.get('image'), dict) else p.get('image', '')
            for p in prop.get('photos', []) if p.get('image')
        ), '')
        
        # Format price with thousands separator
        try:
            price = int(price_data.get('price', 0))
            price_formatted = f"ARS {price:,}"
        except:
            price_formatted = "Consultar"
            
        # Format expenses
        try:
            expenses = int(prop.get('expenses', 0))
            expenses_formatted = f"ARS {expenses:,}"
        except:
            expenses_formatted = "Consultar"

        html += f'''
            <div class="property-card">
                <div class="property-image">
                    <img src="{image_url}" alt="{prop.get('publication_title', 'Propiedad')}" loading="lazy">
                    <div class="property-tags">
                        <span class="tag operation-tag">{operation.get('operation_type', 'Alquiler')}</span>
                        <span class="tag price-tag">{price_formatted}</span>
                    </div>
                </div>
                <div class="property-content">
                    <h3 class="property-title">{prop.get('publication_title', '')}</h3>
                    <p class="property-location">
                        <i class="fas fa-map-marker-alt"></i> 
                        {prop.get('location', {}).get('address', 'Consultar ubicación')}
                    </p>
                    <div class="property-details">
                        <div class="detail-row">
                            <span class="detail-item">
                                <i class="fas fa-ruler-combined"></i> {prop.get('total_surface', 'N/A')} m²
                            </span>
                            <span class="detail-item">
                                <i class="fas fa-money-bill-wave"></i> Exp: {expenses_formatted}
                            </span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-item">
                                <i class="fas fa-door-open"></i> {prop.get('room_amount', 'N/A')} Amb.
                            </span>
                            <span class="detail-item">
                                <i class="fas fa-bath"></i> {prop.get('bathroom_amount', 'N/A')} Baños
                            </span>
                        </div>
                    </div>
                    <p class="property-description">{prop.get('description', '')[:200]}...</p>
                    <a href="{prop.get('public_url', '#')}" class="property-button" target="_blank">
                        <span>Ver más detalles en Tokko</span>
                        <i class="fas fa-external-link-alt"></i>
                    </a>
                </div>
            </div>
        '''
    
    html += '</div>'
    return html

def generate_property_card(prop):
    """Generate HTML for a single property card"""
    return f'''
        <div class="property-card" onclick="window.open('{prop.get('url', '#')}', '_blank')">
            <div class="property-image">
                <img src="{prop.get('image_url', '')}" alt="{prop.get('title', '')}" loading="lazy">
                <div class="property-price">{prop.get('price_formatted', 'Consultar')}</div>
            </div>
            <div class="property-info">
                <h3>{prop.get('title', '')}</h3>
                <p class="address">
                    <i class="fas fa-map-marker-alt"></i> {prop.get('address', '')}
                </p>
                <div class="property-features">
                    <span><i class="fas fa-ruler-combined"></i> {prop.get('area', 'N/A')}</span>
                    <span><i class="fas fa-money-bill-wave"></i> {prop.get('expenses', 'N/A')}</span>
                </div>
                <p class="description">{prop.get('description', '')}</p>
            </div>
        </div>
    '''

@router.post("/test-property-card")
async def test_property_card():
    test_property = {
        "title": "Test Departamento",
        "image_url": "https://example.com/image.jpg",
        "price_formatted": "ARS 500,000",
        "address": "Test Address 123",
        "area": "50m²",
        "expenses": "ARS 10,000",
        "description": "Test description",
        "url": "https://example.com"
    }
    
    html = generate_property_card(test_property)
    logger.info("[DEBUG] Test property card HTML:")
    logger.info(html)
    
    return JSONResponse(content={"html": html})