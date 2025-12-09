"""
WebSocket connection testing functionality.
"""

import time
import websocket


class WebSocketTester:
    """Test WebSocket connections"""
    
    def __init__(self, url: str, timeout: int = 30):
        self.url = url
        self.timeout = timeout
        self.connection_time = None
        self.error = None
        
    def test_connection(self) -> float:
        """Test WebSocket connection and return connection time"""
        start_time = time.time()
        try:
            ws = websocket.create_connection(self.url, timeout=self.timeout)
            self.connection_time = time.time() - start_time
            ws.close()
            return self.connection_time
        except Exception as e:
            self.error = str(e)
            return -1

