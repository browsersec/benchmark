"""
Sessions API monitoring functionality.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)


class SessionsAPIMonitor:
    """Monitor active sessions via API endpoint"""
    
    def __init__(self, api_url: str, insecure: bool = False, timeout: int = 10):
        self.api_url = api_url
        self.base_url = api_url.rstrip('/sessions/').rstrip('/sessions')
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
    
    def get_websocket_metrics_summary(self) -> Dict[str, Any]:
        """
        Get aggregated WebSocket RTT metrics from the backend API.
        
        Returns metrics summary including:
        - Total sessions with RTT data
        - Average, min, max, P95 RTT values
        - Total bytes/messages sent/received
        """
        try:
            url = f"{self.base_url}/metrics/websocket/summary"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            return {
                'success': True,
                'total_sessions': data.get('total_sessions', 0),
                'total_rtt_samples': data.get('total_rtt_samples', 0),
                'avg_rtt_ms': data.get('avg_rtt_ms'),
                'min_rtt_ms': data.get('min_rtt_ms'),
                'max_rtt_ms': data.get('max_rtt_ms'),
                'p95_rtt_ms': data.get('p95_rtt_ms'),
                'total_bytes_sent': data.get('total_bytes_sent', 0),
                'total_bytes_received': data.get('total_bytes_received', 0),
                'total_messages_sent': data.get('total_messages_sent', 0),
                'total_messages_received': data.get('total_messages_received', 0),
                'timestamp': datetime.now()
            }
        except requests.exceptions.RequestException as e:
            logger.debug(f"Failed to fetch WebSocket metrics summary: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.debug(f"Error parsing WebSocket metrics summary: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now()
            }
    
    def get_all_websocket_metrics(self) -> Dict[str, Any]:
        """
        Get WebSocket metrics for all active sessions.
        
        Returns metrics keyed by session ID.
        """
        try:
            url = f"{self.base_url}/metrics/websocket"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            return {
                'success': True,
                'sessions': data,
                'session_count': len(data),
                'timestamp': datetime.now()
            }
        except requests.exceptions.RequestException as e:
            logger.debug(f"Failed to fetch all WebSocket metrics: {e}")
            return {
                'success': False,
                'sessions': {},
                'session_count': 0,
                'error': str(e),
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.debug(f"Error parsing WebSocket metrics: {e}")
            return {
                'success': False,
                'sessions': {},
                'session_count': 0,
                'error': str(e),
                'timestamp': datetime.now()
            }
    
    def get_session_websocket_metrics(self, session_id: str) -> Dict[str, Any]:
        """
        Get WebSocket RTT metrics for a specific session.
        
        Args:
            session_id: The session/connection ID
            
        Returns:
            RTT and traffic metrics for the session
        """
        try:
            url = f"{self.base_url}/sessions/{session_id}/metrics"
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            return {
                'success': True,
                'session_id': session_id,
                'rtt': data.get('rtt', {}),
                'traffic': data.get('traffic', {}),
                'timing': data.get('timing', {}),
                'errors': data.get('errors', 0),
                'timestamp': datetime.now()
            }
        except requests.exceptions.RequestException as e:
            logger.debug(f"Failed to fetch WebSocket metrics for session {session_id}: {e}")
            return {
                'success': False,
                'session_id': session_id,
                'error': str(e),
                'timestamp': datetime.now()
            }
        except Exception as e:
            logger.debug(f"Error parsing WebSocket metrics for session {session_id}: {e}")
            return {
                'success': False,
                'session_id': session_id,
                'error': str(e),
                'timestamp': datetime.now()
            }

