"""
Browser session simulation using Playwright.
"""

import asyncio
import time
import logging
import statistics
from datetime import datetime
from typing import Dict, List, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from .config import BenchmarkConfig, SessionMetrics

logger = logging.getLogger(__name__)


class WebSocketRTTTracker:
    """
    Track WebSocket round-trip time (RTT) for Guacamole connections.
    
    Guacamole uses a custom protocol over WebSocket. We track RTT by:
    1. Recording timestamps when frames are sent
    2. Recording timestamps when frames are received
    3. For ping/pong style messages, calculating actual RTT
    4. For general traffic, estimating RTT from frame patterns
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.rtt_samples: List[float] = []
        self.frames_sent = 0
        self.frames_received = 0
        self.bytes_sent = 0
        self.bytes_received = 0
        self.last_sent_time: Optional[float] = None
        self.pending_requests: Dict[str, float] = {}  # Track request timestamps
        self._lock = asyncio.Lock()
        
    async def on_frame_sent(self, payload: str) -> None:
        """Called when a WebSocket frame is sent"""
        async with self._lock:
            self.frames_sent += 1
            self.bytes_sent += len(payload) if payload else 0
            self.last_sent_time = time.time() * 1000  # ms
            
            # Track Guacamole instruction for RTT measurement
            # Guacamole instructions start with length.opcode format
            if payload:
                try:
                    # Extract instruction opcode for tracking
                    # Format: "4.sync,1.0,..." where 4 is length and sync is opcode
                    parts = payload.split(',')
                    if parts:
                        first_part = parts[0]
                        if '.' in first_part:
                            opcode = first_part.split('.')[1] if len(first_part.split('.')) > 1 else ''
                            # Track sync instructions - these get responses
                            if opcode in ['sync', 'key', 'mouse', 'size', 'audio']:
                                request_id = f"{opcode}_{self.frames_sent}"
                                self.pending_requests[request_id] = self.last_sent_time
                except Exception:
                    pass
    
    async def on_frame_received(self, payload: str) -> None:
        """Called when a WebSocket frame is received"""
        async with self._lock:
            current_time = time.time() * 1000  # ms
            self.frames_received += 1
            self.bytes_received += len(payload) if payload else 0
            
            # Calculate RTT from last sent frame (approximate)
            if self.last_sent_time is not None:
                rtt = current_time - self.last_sent_time
                # Only count reasonable RTT values (< 10 seconds)
                if 0 < rtt < 10000:
                    self.rtt_samples.append(rtt)
            
            # Check for matching response to track specific RTT
            if payload and self.pending_requests:
                try:
                    parts = payload.split(',')
                    if parts:
                        first_part = parts[0]
                        if '.' in first_part:
                            opcode = first_part.split('.')[1] if len(first_part.split('.')) > 1 else ''
                            # Match response opcodes
                            if opcode in ['sync', 'ack', 'ready', 'nest', 'png', 'img', 'rect']:
                                # Find oldest pending request and calculate RTT
                                if self.pending_requests:
                                    oldest_key = min(self.pending_requests.keys(), 
                                                    key=lambda k: self.pending_requests[k])
                                    sent_time = self.pending_requests.pop(oldest_key)
                                    rtt = current_time - sent_time
                                    if 0 < rtt < 10000:
                                        self.rtt_samples.append(rtt)
                except Exception:
                    pass
            
            # Cleanup old pending requests (> 30 seconds)
            stale_keys = [k for k, v in self.pending_requests.items() 
                         if current_time - v > 30000]
            for key in stale_keys:
                del self.pending_requests[key]
    
    def get_statistics(self) -> Dict[str, Optional[float]]:
        """Calculate RTT statistics from collected samples"""
        if not self.rtt_samples:
            return {
                'avg': None,
                'min': None,
                'max': None,
                'p50': None,
                'p95': None,
                'p99': None,
                'samples': 0
            }
        
        sorted_samples = sorted(self.rtt_samples)
        n = len(sorted_samples)
        
        def percentile(data, p):
            k = (len(data) - 1) * (p / 100)
            f = int(k)
            c = f + 1 if f + 1 < len(data) else f
            return data[f] + (data[c] - data[f]) * (k - f)
        
        return {
            'avg': statistics.mean(sorted_samples),
            'min': min(sorted_samples),
            'max': max(sorted_samples),
            'p50': percentile(sorted_samples, 50),
            'p95': percentile(sorted_samples, 95),
            'p99': percentile(sorted_samples, 99),
            'samples': n
        }


class BrowserSimulator:
    """Simulate browser sessions using Playwright"""
    
    def __init__(self, config: BenchmarkConfig, session_id: str):
        self.config = config
        self.session_id = session_id
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.metrics = SessionMetrics(session_id=session_id, start_time=datetime.now())
        self.ws_tracker: Optional[WebSocketRTTTracker] = None
        self.active_websockets: List = []
        
    async def setup_browser(self) -> bool:
        """Setup Playwright browser with options"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=self.config.headless,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-extensions',
                ]
            )
            self.context = await self.browser.new_context(
                viewport={'width': self.config.viewport_width, 'height': self.config.viewport_height}
            )
            self.page = await self.context.new_page()
            
            # Setup console error capture
            self.page.on('console', self._handle_console_message)
            
            # Setup WebSocket RTT tracking for Guacamole connections
            self.ws_tracker = WebSocketRTTTracker(self.session_id)
            self.page.on('websocket', self._handle_websocket)
            
            # Minimal wait after browser initiation - prioritize quick start
            logger.debug(f"Session {self.session_id}: Browser initiated, starting immediately")
            await asyncio.sleep(0.5)  # Minimal wait for browser stability
            
            return True
        except Exception as e:
            self.metrics.errors.append(f"Browser setup failed: {e}")
            logger.error(f"Session {self.session_id}: Browser setup failed: {e}")
            return False
    
    def _handle_websocket(self, ws) -> None:
        """Handle WebSocket connection for RTT tracking"""
        ws_url = ws.url
        logger.debug(f"Session {self.session_id}: WebSocket connected to {ws_url}")
        
        # Track Guacamole WebSocket connections (typically contain 'guac' or 'tunnel')
        if 'guac' in ws_url.lower() or 'tunnel' in ws_url.lower() or 'websocket' in ws_url.lower():
            logger.info(f"Session {self.session_id}: Tracking Guacamole WebSocket RTT for {ws_url}")
            self.active_websockets.append(ws)
            
            # Record connection time
            connection_start = time.time()
            self.metrics.websocket_connection_time = connection_start
            
            # Setup frame handlers
            ws.on('framesent', lambda payload: asyncio.create_task(
                self._on_ws_frame_sent(payload)
            ))
            ws.on('framereceived', lambda payload: asyncio.create_task(
                self._on_ws_frame_received(payload)
            ))
            ws.on('close', lambda: self._on_ws_close(ws_url))
    
    async def _on_ws_frame_sent(self, payload) -> None:
        """Handle WebSocket frame sent event"""
        if self.ws_tracker:
            try:
                # payload is a FrameSentEvent with 'payload' attribute
                data = payload.payload if hasattr(payload, 'payload') else str(payload)
                await self.ws_tracker.on_frame_sent(data)
            except Exception as e:
                logger.debug(f"Session {self.session_id}: Error tracking WS frame sent: {e}")
    
    async def _on_ws_frame_received(self, payload) -> None:
        """Handle WebSocket frame received event"""
        if self.ws_tracker:
            try:
                # payload is a FrameReceivedEvent with 'payload' attribute
                data = payload.payload if hasattr(payload, 'payload') else str(payload)
                await self.ws_tracker.on_frame_received(data)
            except Exception as e:
                logger.debug(f"Session {self.session_id}: Error tracking WS frame received: {e}")
    
    def _on_ws_close(self, ws_url: str) -> None:
        """Handle WebSocket close event"""
        logger.debug(f"Session {self.session_id}: WebSocket closed: {ws_url}")
    
    def _handle_console_message(self, msg):
        """Handle console messages from the browser"""
        try:
            level = msg.type
            if level in ['error', 'warning']:
                console_error = {
                    'timestamp': datetime.now().isoformat(),
                    'level': level.upper(),
                    'message': msg.text,
                    'source': 'console'
                }
                self.metrics.console_errors.append(console_error)
                
                # Also add to regular errors for backward compatibility
                error_msg = f"Console {level.upper()}: {msg.text}"
                if error_msg not in self.metrics.errors:
                    self.metrics.errors.append(error_msg)
        except Exception as e:
            logger.debug(f"Session {self.session_id}: Could not capture console log: {e}")
    
    async def disconnect_session(self) -> None:
        """Attempt to disconnect the session, forcing click if necessary."""
        try:
            disconnect_btn = self.page.get_by_role("button", name="Disconnect").nth(1)
            # Try normal click first with short timeout
            await disconnect_btn.click(timeout=5000)
        except PlaywrightTimeoutError:
            logger.warning(f"Session {self.session_id}: Normal disconnect failed, attempting force click...")
            try:
                # Force click even if disabled
                await self.page.get_by_role("button", name="Disconnect").nth(1).click(force=True, timeout=5000)
            except Exception as e:
                logger.error(f"Session {self.session_id}: Force disconnect also failed: {e}")
    
    async def run_session(self) -> SessionMetrics:
        """Run a complete browser session simulation"""
        logger.info(f"Session {self.session_id}: Starting session")
        
        if not await self.setup_browser():
            self.metrics.end_time = datetime.now()
            return self.metrics
            
        try:
            # Navigate to application immediately
            logger.info(f"Session {self.session_id}: Navigating to {self.config.target_url}")
            start_time = time.time()
            await self.page.goto(self.config.target_url)
            self.metrics.total_api_calls += 1
            
            # Brief wait for page to load and generate any errors
            await asyncio.sleep(1)
            
            # Wait for page load
            await self.page.wait_for_load_state('domcontentloaded')
            logger.info(f"Session {self.session_id}: Page loaded, starting interactions")
            
            # Start interactions immediately - no additional wait
            await self._simulate_user_interactions()
            
        except Exception as e:
            self.metrics.errors.append(f"Session error: {e}")
            self.metrics.failed_api_calls += 1
            logger.error(f"Session {self.session_id}: Error - {e}")
            # Always try to disconnect on error
            await self.disconnect_session()
        finally:
            # Collect WebSocket RTT metrics before ending session
            self._collect_websocket_metrics()
            self.metrics.end_time = datetime.now()
            
        return self.metrics
    
    def _collect_websocket_metrics(self) -> None:
        """Collect WebSocket RTT statistics and store in metrics"""
        if self.ws_tracker:
            stats = self.ws_tracker.get_statistics()
            
            # Store RTT samples and statistics
            self.metrics.websocket_rtt_samples = self.ws_tracker.rtt_samples.copy()
            self.metrics.websocket_rtt_avg = stats['avg']
            self.metrics.websocket_rtt_min = stats['min']
            self.metrics.websocket_rtt_max = stats['max']
            self.metrics.websocket_rtt_p50 = stats['p50']
            self.metrics.websocket_rtt_p95 = stats['p95']
            self.metrics.websocket_rtt_p99 = stats['p99']
            self.metrics.websocket_frames_sent = self.ws_tracker.frames_sent
            self.metrics.websocket_frames_received = self.ws_tracker.frames_received
            self.metrics.websocket_bytes_sent = self.ws_tracker.bytes_sent
            self.metrics.websocket_bytes_received = self.ws_tracker.bytes_received
            
            if stats['samples'] > 0:
                logger.info(
                    f"Session {self.session_id}: WebSocket RTT - "
                    f"avg={stats['avg']:.2f}ms, min={stats['min']:.2f}ms, "
                    f"max={stats['max']:.2f}ms, p95={stats['p95']:.2f}ms, "
                    f"samples={stats['samples']}"
                )
            else:
                logger.debug(f"Session {self.session_id}: No WebSocket RTT samples collected")
    
    async def _simulate_user_interactions(self):
        """Simulate the user interactions (based on run_playwright.py pattern)"""
        try:
            # Minimal wait for page stability - prioritize immediate interaction
            logger.debug(f"Session {self.session_id}: Starting interaction simulation")
            await asyncio.sleep(0.5)  # Very short wait for DOM stability
            
            # Click on Browser Session link - start timing immediately
            first_click_start = time.time()
            logger.info(f"Session {self.session_id}: Clicking Browser Session link")
            
            await self.page.get_by_role("link", name="Browser Session").click()
            self.metrics.first_click_response_time = time.time() - first_click_start
            self.metrics.total_api_calls += 1
            logger.info(f"Session {self.session_id}: First click completed in {self.metrics.first_click_response_time:.3f}s")
            
            # Click Create Browser Session button
            logger.info(f"Session {self.session_id}: Clicking Create Browser Session")
            await self.page.get_by_role("button", name="Create Browser Session").click()
            self.metrics.total_api_calls += 1
            
            # Interact with guac-display element
            await self.page.locator(".guac-display").press("ControlOrMeta+l")
            await asyncio.sleep(12)  # Wait for address bar to focus
            
            # Type URL
            await self.page.locator(".guac-display").type("https://tinyurl.com/ytrickroll", delay=100)
            await asyncio.sleep(5)
            await self.page.locator(".guac-display").press("Enter")
            await asyncio.sleep(10)
            
            # Press K multiple times (likely for video controls)
            await self.page.locator(".guac-display").press("K")
            await asyncio.sleep(2)
            await self.page.locator(".guac-display").press("K")
            await asyncio.sleep(2)
            await self.page.locator(".guac-display").press("K")
            await self.page.locator(".guac-display").press("F")  # Fullscreen
            
            logger.info(f"Session {self.session_id}: Pressed ControlOrMeta+F")
            
            # Wait for video to play
            await asyncio.sleep(0.5 * 60)
            logger.info(f"Session {self.session_id}: Video started.")
            await asyncio.sleep(0.5 * 60)
            
            # Click copy connection ID button multiple times
            await self.page.get_by_role("button", name="Copy connection ID to").click()
            await self.page.get_by_role("button", name="Copy connection ID to").click()
            await self.page.get_by_role("button", name="Copy connection ID to").click()
            
            # Keep session open for configured duration
            wait_time = self.config.session_duration
            logger.info(f"Session {self.session_id}: Keeping session open for {wait_time} seconds")
            await asyncio.sleep(wait_time)
            
            # Disconnect the session
            await self.disconnect_session()
            logger.info(f"Session {self.session_id}: Disconnected the session.")
                    
        except PlaywrightTimeoutError:
            self.metrics.errors.append("Timeout waiting for elements")
            self.metrics.failed_api_calls += 1
            logger.error(f"Session {self.session_id}: Timeout waiting for elements")
        except Exception as e:
            self.metrics.errors.append(f"Interaction error - {e}")
            self.metrics.failed_api_calls += 1
            logger.error(f"Session {self.session_id}: Interaction error - {e}")
    
    async def close_browser(self):
        """Manually close the browser when needed"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.debug(f"Session {self.session_id}: Error closing browser: {e}")

