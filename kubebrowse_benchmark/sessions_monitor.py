"""
Sessions API monitoring functionality.
"""

import logging
from datetime import datetime
from typing import Dict, Any

import requests

logger = logging.getLogger(__name__)


class SessionsAPIMonitor:
    """Monitor active sessions via API endpoint"""
    
    def __init__(self, api_url: str, insecure: bool = False, timeout: int = 10):
        self.api_url = api_url
        self.timeout = timeout
        self.session = requests.Session()
        
        if insecure:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self.session.verify = False
    
    def get_active_sessions(self) -> Dict[str, Any]:
        """Get active sessions from API endpoint"""
        try:
            response = self.session.get(self.api_url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            return {
                'active_sessions': data.get('active_sessions', 0),
                'connection_ids': data.get('connection_ids', []),
                'total_connections': len(data.get('connection_ids', [])),
                'timestamp': datetime.now()
            }
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to fetch sessions data from API: {e}")
            return {
                'active_sessions': 0,
                'connection_ids': [],
                'total_connections': 0,
                'timestamp': datetime.now(),
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Error parsing sessions API response: {e}")
            return {
                'active_sessions': 0,
                'connection_ids': [],
                'total_connections': 0,
                'timestamp': datetime.now(),
                'error': str(e)
            }

