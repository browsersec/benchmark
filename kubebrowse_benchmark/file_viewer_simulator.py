"""
File Viewer/Office Session simulation using Playwright.
Simulates file upload and viewing in an isolated sandbox.
"""

import asyncio
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

from .config import BenchmarkConfig, SessionMetrics

logger = logging.getLogger(__name__)

# Default files to upload for testing
DEFAULT_TEST_FILES = [
    # Documents
    "Module2-Topic5-Graph Based Data Model.pptx",
    "sample1.odt",
    "sample2.docx",
    "sample1.odp",
    "sample2.csv",
    "sample3.txt",
    "sample3.pdf",
    "sample3.ods",
    # Images
    "sample_5184×3456.jpeg",
    "sample_1280×853.gif",
    "sample1.webp",
    "sample_5184×3456.jpg",
    # Audio
    "sample3.mp3",
    # Video
    "sample_640x360.mov",
    "sample_960x540.mp4",
    "sample_640x360.mkv",
    "sample_960x540.flv",
    "sample_960x540.wmv",
    "sample_640x360.avi",
    "sample_640x360.webm",
    # Archives
    "sample-1.zip",
    "sample-1.rar",
    "sample-1.tar",
    "sample-3.gz",
    "sample-3.bz2",
    "sample-1.7z",
]


class FileViewerSimulator:
    """Simulate file viewer/office session using Playwright"""
    
    def __init__(self, config: BenchmarkConfig, session_id: str):
        self.config = config
        self.session_id = session_id
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.metrics = SessionMetrics(session_id=session_id, start_time=datetime.now())
        self.files_uploaded = 0
        self.files_failed = 0
        
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
            
            # Minimal wait after browser initiation
            logger.debug(f"Session {self.session_id}: Browser initiated, starting immediately")
            await asyncio.sleep(0.5)
            
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
                
                error_msg = f"Console {level.upper()}: {msg.text}"
                if error_msg not in self.metrics.errors:
                    self.metrics.errors.append(error_msg)
        except Exception as e:
            logger.debug(f"Session {self.session_id}: Could not capture console log: {e}")
    
    async def upload_file(self, file_path: str) -> bool:
        """Upload a file using the file chooser dialog"""
        try:
            start_time = time.time()
            
            # Start waiting for file chooser before clicking
            async with self.page.expect_file_chooser() as fc_info:
                await self.page.get_by_role("button", name="Upload File").click()
            file_chooser = await fc_info.value
            await file_chooser.set_files(file_path)
            
            # Wait for upload to complete
            await asyncio.sleep(self.config.file_upload_wait)
            
            upload_time = time.time() - start_time
            self.metrics.total_api_calls += 1
            self.files_uploaded += 1
            
            # Track file upload time for metrics
            self.metrics.file_upload_times.append(upload_time)
            self.metrics.files_uploaded = self.files_uploaded
            
            logger.debug(f"Session {self.session_id}: Uploaded {Path(file_path).name} in {upload_time:.2f}s")
            return True
            
        except PlaywrightTimeoutError as e:
            self.metrics.errors.append(f"Upload timeout for {Path(file_path).name}: {e}")
            self.metrics.failed_api_calls += 1
            self.files_failed += 1
            self.metrics.files_failed = self.files_failed
            logger.warning(f"Session {self.session_id}: Upload timeout for {Path(file_path).name}")
            return False
        except Exception as e:
            self.metrics.errors.append(f"Upload failed for {Path(file_path).name}: {e}")
            self.metrics.failed_api_calls += 1
            self.files_failed += 1
            self.metrics.files_failed = self.files_failed
            logger.error(f"Session {self.session_id}: Upload failed for {Path(file_path).name}: {e}")
            return False
    
    async def disconnect_session(self) -> None:
        """Attempt to disconnect the session, forcing click if necessary."""
        try:
            disconnect_btn = self.page.get_by_role("button", name="Disconnect").nth(1)
            await disconnect_btn.click(timeout=5000)
        except PlaywrightTimeoutError:
            logger.warning(f"Session {self.session_id}: Normal disconnect failed, attempting force click...")
            try:
                await self.page.get_by_role("button", name="Disconnect").nth(1).click(force=True, timeout=5000)
            except Exception as e:
                logger.error(f"Session {self.session_id}: Force disconnect also failed: {e}")
    
    def _get_test_files(self) -> List[Path]:
        """Get list of test files to upload"""
        files_dir = Path(self.config.temp_files_dir)
        
        if not files_dir.exists():
            logger.warning(f"Session {self.session_id}: Test files directory not found: {files_dir}")
            return []
        
        # Use custom file list if provided, otherwise use defaults
        filenames = self.config.test_files if self.config.test_files else DEFAULT_TEST_FILES
        
        valid_files = []
        for filename in filenames:
            file_path = files_dir / filename
            if file_path.exists():
                valid_files.append(file_path)
            else:
                logger.debug(f"Session {self.session_id}: Test file not found: {file_path}")
        
        return valid_files
    
    async def run_session(self) -> SessionMetrics:
        """Run a complete file viewer session simulation"""
        logger.info(f"Session {self.session_id}: Starting file viewer session")
        
        if not await self.setup_browser():
            self.metrics.end_time = datetime.now()
            return self.metrics
            
        try:
            # Navigate to application
            logger.info(f"Session {self.session_id}: Navigating to {self.config.target_url}")
            start_time = time.time()
            await self.page.goto(self.config.target_url)
            self.metrics.total_api_calls += 1
            
            # Wait for page to load
            await asyncio.sleep(1)
            await self.page.wait_for_load_state('domcontentloaded')
            logger.info(f"Session {self.session_id}: Page loaded, starting file viewer interactions")
            
            # Start file viewer interactions
            await self._simulate_file_viewer_interactions()
            
        except Exception as e:
            self.metrics.errors.append(f"Session error: {e}")
            self.metrics.failed_api_calls += 1
            logger.error(f"Session {self.session_id}: Error - {e}")
            await self.disconnect_session()
        finally:
            self.metrics.end_time = datetime.now()
            
        return self.metrics
    
    async def _simulate_file_viewer_interactions(self):
        """Simulate the file viewer/office session interactions"""
        try:
            logger.debug(f"Session {self.session_id}: Starting file viewer simulation")
            await asyncio.sleep(0.5)
            
            # Click on Office Session link
            first_click_start = time.time()
            logger.info(f"Session {self.session_id}: Clicking Office Session link")
            
            await self.page.get_by_role("link", name="Office Session").click()
            self.metrics.first_click_response_time = time.time() - first_click_start
            self.metrics.total_api_calls += 1
            logger.info(f"Session {self.session_id}: First click completed in {self.metrics.first_click_response_time:.3f}s")
            
            # Click Create Office Session button
            logger.info(f"Session {self.session_id}: Clicking Create Office Session")
            await self.page.get_by_role("button", name="Create Office Session").click()
            self.metrics.total_api_calls += 1
            
            # Wait for the office session to be ready
            await asyncio.sleep(self.config.office_session_init_wait)
            
            # Get test files
            test_files = self._get_test_files()
            
            if not test_files:
                logger.warning(f"Session {self.session_id}: No test files found, skipping file uploads")
            else:
                logger.info(f"Session {self.session_id}: Uploading {len(test_files)} files...")
                
                # Upload each file with delay between uploads
                for file_path in test_files:
                    logger.debug(f"Session {self.session_id}: Uploading {file_path.name}")
                    
                    # Wait between file uploads
                    await asyncio.sleep(self.config.file_upload_interval)
                    
                    success = await self.upload_file(str(file_path))
                    if success:
                        logger.info(f"Session {self.session_id}: Uploaded {file_path.name}")
                    else:
                        logger.warning(f"Session {self.session_id}: Failed to upload {file_path.name}")
                
                # Calculate average upload time
                if self.metrics.file_upload_times:
                    self.metrics.avg_file_upload_time = sum(self.metrics.file_upload_times) / len(self.metrics.file_upload_times)
                
                logger.info(f"Session {self.session_id}: File upload complete. "
                           f"Success: {self.files_uploaded}, Failed: {self.files_failed}, "
                           f"Avg upload time: {self.metrics.avg_file_upload_time:.2f}s" if self.metrics.avg_file_upload_time else "")
            
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

