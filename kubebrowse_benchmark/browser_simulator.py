"""
Browser session simulation using Playwright.
"""

import asyncio
import time
import logging
from datetime import datetime

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from .config import BenchmarkConfig, SessionMetrics

logger = logging.getLogger(__name__)


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
        
    async def setup_browser(self) -> bool:
        """Setup Playwright browser with options"""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=False,
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
            
            # Minimal wait after browser initiation - prioritize quick start
            logger.debug(f"Session {self.session_id}: Browser initiated, starting immediately")
            await asyncio.sleep(0.5)  # Minimal wait for browser stability
            
            return True
        except Exception as e:
            self.metrics.errors.append(f"Browser setup failed: {e}")
            logger.error(f"Session {self.session_id}: Browser setup failed: {e}")
            return False
    
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
            self.metrics.end_time = datetime.now()
            
        return self.metrics
    
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
            
            # Keep session open for configured time (default behavior from run_playwright.py)
            # Using a reasonable wait time for benchmarking
            wait_time = min(2 * 60, 3600)  # 2 minutes or 1 hour max
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

