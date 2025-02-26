import json
import aiohttp
import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def explore_tokko_api():
    base_url = "https://www.tokkobroker.com/api/v1"
    api_key = "34430fc661d5b961de6fd53a9382f7a232de3ef0"
    
    endpoint = "/property/"
    
    async with aiohttp.ClientSession() as session:
        print("\n=== Exploring Tokko API Capabilities ===")
        
        params = {
            "key": api_key,
            "limit": "0"  # Get all properties
        }
        
        print("\nFetching all properties to analyze types...")
        
        try:
            async with session.get(f"{base_url}{endpoint}", params=params) as response:
                print(f"Request URL: {response.url}")
                
                if response.status == 200:
                    data = await response.json()
                    properties = data.get('objects', [])
                    
                    # Analysis containers
                    property_types = set()
                    operation_types = set()
                    property_fields = set()
                    locations = set()
                    
                    for prop in properties:
                        # Get property type
                        if 'type' in prop:
                            property_types.add(json.dumps(prop['type'], ensure_ascii=False))
                        
                        # Get operation types
                        for operation in prop.get('operations', []):
                            operation_types.add(json.dumps(operation['operation_type'], ensure_ascii=False))
                        
                        # Get location
                        if 'location' in prop:
                            locations.add(prop['location'].get('name', 'Unknown'))
                        
                        # Get all fields
                        property_fields.update(prop.keys())
                    
                    # Print findings
                    print(f"\nFound {len(properties)} properties")
                    
                    print("\nProperty Types:")
                    for pt in sorted(property_types):
                        print(f"- {pt}")
                    
                    print("\nOperation Types:")
                    for ot in sorted(operation_types):
                        print(f"- {ot}")
                    
                    print("\nLocations:")
                    for loc in sorted(locations):
                        print(f"- {loc}")
                    
                    print("\nAvailable Fields:")
                    for field in sorted(property_fields):
                        print(f"- {field}")
                    
                    # Save detailed analysis
                    analysis = {
                        "total_properties": len(properties),
                        "property_types": [json.loads(pt) for pt in sorted(property_types)],
                        "operation_types": [json.loads(ot) for ot in sorted(operation_types)],
                        "locations": list(sorted(locations)),
                        "available_fields": list(sorted(property_fields)),
                        "sample_properties": properties[:3]  # Save first 3 properties as samples
                    }
                    
                    with open("tokko_api_analysis.json", "w", encoding="utf-8") as f:
                        json.dump(analysis, f, indent=2, ensure_ascii=False)
                    print("\nDetailed analysis saved to tokko_api_analysis.json")
                
                else:
                    error_text = await response.text()
                    print(f"Failed with status {response.status}")
                    print(f"Error: {error_text}")
        
        except Exception as e:
            print(f"Error during API exploration: {str(e)}")

if __name__ == "__main__":
    asyncio.run(explore_tokko_api())