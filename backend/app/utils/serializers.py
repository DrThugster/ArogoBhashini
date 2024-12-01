from datetime import datetime
import base64
from typing import Any, Dict

class StreamingStateSerializer:
    @staticmethod
    def serialize(state: Dict[str, Any]) -> Dict[str, Any]:
        serialized = state.copy()
        
        # Handle bytes buffer
        if 'buffer' in serialized:
            serialized['buffer'] = (
                base64.b64encode(serialized['buffer']).decode() 
                if isinstance(serialized['buffer'], bytes) 
                else ""
            )
            
        # Handle datetime
        if 'start_time' in serialized and isinstance(serialized['start_time'], datetime):
            serialized['start_time'] = serialized['start_time'].isoformat()
            
        return serialized
