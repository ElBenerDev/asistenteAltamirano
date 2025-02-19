import json
import requests
from aiAssistant import TokkoClient, TOKKO_API_KEY
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def explore_api():
    client = TokkoClient(TOKKO_API_KEY)
    base_url = "https://www.tokkobroker.com/api/v1"
    
    # Define endpoints to test
    endpoints = [
        "/property/",
        "/property/search/",
        "/property/property_types/",
        "/property/operation_types/",
        "/property/tags/"
    ]

    print("\n=== Exploring Tokko API Structure ===")
    api_structure = {}

    for endpoint in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            params = {
                "key": TOKKO_API_KEY,
                "format": "json",
                "lang": "es",
                "limit": 1  # Just get one result to test
            }
            
            print(f"\nTesting endpoint: {url}")
            response = requests.get(url, params=params)
            
            print(f"Status Code: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                api_structure[endpoint] = {
                    "status": "success",
                    "data_structure": data if isinstance(data, dict) else {"type": "list", "count": len(data)}
                }
                print("Response structure:")
                print(json.dumps(data, indent=2)[:500] + "...")
            else:
                print(f"Response text: {response.text[:200]}")
                api_structure[endpoint] = {
                    "status": "error",
                    "status_code": response.status_code
                }

        except Exception as e:
            print(f"Error testing {endpoint}: {str(e)}")
            api_structure[endpoint] = {
                "status": "error",
                "error": str(e)
            }

    # Save the API structure to file
    with open("tokko_api_structure.json", "w", encoding="utf-8") as f:
        json.dump(api_structure, f, indent=2, ensure_ascii=False)
    print("\nAPI structure saved to tokko_api_structure.json")

    # Test a basic property search
    print("\n=== Testing Basic Property Search ===")
    try:
        test_search = {
            "key": TOKKO_API_KEY,
            "limit": 5,
            "format": "json",
            "lang": "es"
        }
        url = f"{base_url}/property/"
        response = requests.get(url, params=test_search)
        if response.status_code == 200:
            properties = response.json()
            print(f"\nFound {len(properties.get('objects', []))} properties")
            print("Sample property structure:")
            if properties.get('objects'):
                print(json.dumps(properties['objects'][0], indent=2))
    except Exception as e:
        print(f"Search test error: {str(e)}")

def test_property_search():
    client = TokkoClient(TOKKO_API_KEY)
    base_url = "https://www.tokkobroker.com/api/v1"
    
    # Define search criteria
    search_tests = [
        {
            "name": "Search by location (Villa Ballester)",
            "filters": {
                "location": "Villa Ballester",
                "price_from": 0,
                "price_to": 1000000,
                "property_type": "Apartment",
                "operation_type": "Sale"
            }
        },
        {
            "name": "Search 2+ rooms properties",
            "filters": {
                "min_rooms": 2,
                "min_bathrooms": 1,
                "property_type": "Apartment",
                "operation_type": "Rent"
            }
        }
    ]

    # Get all properties first
    try:
        url = f"{base_url}/property/"
        params = {
            "key": TOKKO_API_KEY,
            "format": "json",
            "lang": "es",
            "limit": 100  # Get more properties for better testing
        }
        
        print("\n=== Fetching all properties ===")
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        properties = data.get('objects', [])
        print(f"Found {len(properties)} total properties")

        # Test each search scenario
        for test in search_tests:
            print(f"\n=== {test['name']} ===")
            print(f"Applying filters: {json.dumps(test['filters'], indent=2)}")
            
            # Filter properties
            filtered = []
            for prop in properties:
                matches = True
                filters = test['filters']
                
                # Check location
                if matches and filters.get('location'):
                    location_match = False
                    prop_location = prop.get('location', {})
                    if filters['location'].lower() in prop_location.get('name', '').lower():
                        location_match = True
                    for div in prop_location.get('divisions', []):
                        if filters['location'].lower() in div.get('name', '').lower():
                            location_match = True
                            break
                    matches = location_match

                # Check price range
                if matches and (filters.get('price_from') is not None or filters.get('price_to') is not None):
                    for op in prop.get('operations', []):
                        prices = op.get('prices', [])
                        if prices:
                            price = prices[0].get('price', 0)
                            if filters.get('price_from') and price < filters['price_from']:
                                matches = False
                            if filters.get('price_to') and price > filters['price_to']:
                                matches = False

                # Check property type
                if matches and filters.get('property_type'):
                    prop_type = prop.get('type', {}).get('name', '')
                    matches = filters['property_type'].lower() == prop_type.lower()

                # Check operation type
                if matches and filters.get('operation_type'):
                    op_match = False
                    for op in prop.get('operations', []):
                        if op.get('operation_type', '').lower() == filters['operation_type'].lower():
                            op_match = True
                            break
                    matches = op_match

                # Check room count
                if matches and filters.get('min_rooms'):
                    rooms = prop.get('room_amount', 0)
                    matches = rooms >= filters['min_rooms']

                # Check bathroom count
                if matches and filters.get('min_bathrooms'):
                    bathrooms = prop.get('bathroom_amount', 0)
                    matches = bathrooms >= filters['min_bathrooms']

                if matches:
                    filtered.append(prop)

            # Show results
            print(f"\nFound {len(filtered)} matching properties")
            for prop in filtered[:3]:  # Show first 3 matches
                print("\nProperty:")
                print(f"- Title: {prop.get('publication_title')}")
                print(f"- Address: {prop.get('address')}")
                print(f"- Type: {prop.get('type', {}).get('name')}")
                print(f"- Rooms: {prop.get('room_amount')}")
                print(f"- Bathrooms: {prop.get('bathroom_amount')}")
                print(f"- Surface: {prop.get('total_surface')} m²")
                for op in prop.get('operations', []):
                    prices = op.get('prices', [])
                    if prices:
                        print(f"- Price ({op.get('operation_type')}): {prices[0].get('currency')} {prices[0].get('price')}")

    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_property_search()