"""
Configuration and data classes for the benchmark suite.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional


class BenchmarkMode(Enum):
    """Benchmark mode selection"""
    BROWSER_SESSION = "browser"  # Browser Session - video streaming test
    FILE_VIEWER = "file_viewer"  # Office Session - file upload/viewing test


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark parameters"""
    target_url: str = "http://localhost:5173/"
    namespace: str = "browser-sandbox"
    max_concurrent_users: int = 50
    ramp_up_duration: int = 300  # 5 minutes
    test_duration: int = 1800    # 30 minutes
    ramp_down_duration: int = 300  # 5 minutes
    polling_interval: int = 10   # seconds
    websocket_timeout: int = 30
    api_timeout: int = 10
    save_visualizations: bool = True  # Enable periodic visualization saving
    save_interval: int = 60  # Save visualizations every 60 seconds
    output_dir: str = "benchmark_snapshots"  # Directory for saved visualizations
    kubeconfig_path: Optional[str] = None  # Custom kubeconfig file path
    sessions_api_url: Optional[str] = None  # Sessions API endpoint URL
    sessions_api_insecure: bool = False  # Allow insecure HTTPS connections
    enable_sessions_monitoring: bool = False  # Enable sessions API monitoring
    browser_init_wait: int = 2  # Wait time after browser window initiation in seconds
    session_start_interval: float = 1.0  # Time interval between starting new sessions in seconds
    # Browser viewport dimensions (default: 1280x720)
    viewport_width: int = 1280
    viewport_height: int = 720
    # Browser headless mode (default: False - show browser windows)
    headless: bool = False
    # Session duration - how long each browser session stays open after interactions (seconds)
    session_duration: int = 3600  # Default 1 hour
    
    # Benchmark mode selection
    benchmark_mode: BenchmarkMode = BenchmarkMode.BROWSER_SESSION
    
    # File Viewer / Office Session specific settings
    temp_files_dir: str = "temp_files"  # Directory containing test files
    test_files: Optional[List[str]] = None  # Custom list of files to upload (None = use defaults)
    file_upload_wait: float = 2.0  # Wait time after each file upload in seconds
    file_upload_interval: float = 6.0  # Delay between starting each file upload
    office_session_init_wait: float = 5.0  # Wait time for office session to initialize


@dataclass
class MetricPoint:
    """Single metric measurement"""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = None


@dataclass
class SessionMetrics:
    """Metrics for a single user session"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    pod_creation_time: Optional[float] = None
    websocket_connection_time: Optional[float] = None
    first_click_response_time: Optional[float] = None
    total_api_calls: int = 0
    failed_api_calls: int = 0
    errors: List[str] = None
    console_errors: List[Dict[str, Any]] = None  # Console errors from browser
    # File viewer specific metrics
    files_uploaded: int = 0
    files_failed: int = 0
    file_upload_times: List[float] = None  # Upload time for each file
    avg_file_upload_time: Optional[float] = None
    # WebSocket RTT metrics (Guacamole stream)
    websocket_rtt_samples: List[float] = None  # Individual RTT measurements in ms
    websocket_rtt_avg: Optional[float] = None  # Average RTT in ms
    websocket_rtt_min: Optional[float] = None  # Minimum RTT in ms
    websocket_rtt_max: Optional[float] = None  # Maximum RTT in ms
    websocket_rtt_p50: Optional[float] = None  # Median RTT in ms
    websocket_rtt_p95: Optional[float] = None  # 95th percentile RTT in ms
    websocket_rtt_p99: Optional[float] = None  # 99th percentile RTT in ms
    websocket_frames_sent: int = 0  # Total frames sent
    websocket_frames_received: int = 0  # Total frames received
    websocket_bytes_sent: int = 0  # Total bytes sent
    websocket_bytes_received: int = 0  # Total bytes received
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.console_errors is None:
            self.console_errors = []
        if self.file_upload_times is None:
            self.file_upload_times = []
        if self.websocket_rtt_samples is None:
            self.websocket_rtt_samples = []

