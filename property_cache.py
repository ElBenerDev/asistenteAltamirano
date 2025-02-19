import json
import time
from typing import Dict, List
from datetime import datetime

class PropertyCache:
    def __init__(self):
        self.cache_file = "properties_cache.json"
        self.cache_duration = 3600  # 1 hour in seconds
        self.properties = []
        self.last_update = None
    
    def needs_update(self) -> bool:
        """Check if cache needs to be refreshed"""
        if not self.last_update:
            return True
        return (datetime.now() - self.last_update).total_seconds() > self.cache_duration
    
    def update_cache(self, properties: List[Dict]):
        """Update cache with new properties"""
        self.properties = properties
        self.last_update = datetime.now()
        self._save_cache()
    
    def _save_cache(self):
        """Save properties to cache file"""
        cache_data = {
            "last_update": self.last_update.isoformat(),
            "properties": self.properties
        }
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
    
    def _load_cache(self) -> bool:
        """Load properties from cache file"""
        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.properties = data["properties"]
                self.last_update = datetime.fromisoformat(data["last_update"])
                return True
        except:
            return False
    
    def filter_properties(self, criteria: Dict) -> List[Dict]:
        """Filter properties based on search criteria"""
        filtered = []
        
        for prop in self.properties:
            matches = True
            
            # Check operation type (rent/sale)
            if criteria.get('operation_type'):
                op_type = criteria['operation_type'].lower()
                if not any(op['operation_type'].lower() == op_type 
                          for op in prop.get('operations', [])):
                    matches = False
            
            # Check location
            if matches and criteria.get('location'):
                location = criteria['location'].lower()
                if not any(location in loc['name'].lower() 
                          for loc in prop.get('location', {}).get('divisions', [])):
                    matches = False
            
            # Check number of rooms
            if matches and criteria.get('rooms'):
                if prop.get('room_amount') != criteria['rooms']:
                    matches = False
            
            # Check price range
            if matches and (criteria.get('price_from') or criteria.get('price_to')):
                for op in prop.get('operations', []):
                    prices = op.get('prices', [])
                    if prices:
                        price = prices[0].get('price', 0)
                        if criteria.get('price_from') and price < criteria['price_from']:
                            matches = False
                        if criteria.get('price_to') and price > criteria['price_to']:
                            matches = False
            
            if matches:
                filtered.append(prop)
        
        return filtered