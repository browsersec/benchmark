"""
Configuration and data classes for the benchmark suite.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any, Optional


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
    console_errors: List[Dict[str, Any]] = None  # New field for console errors
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.console_errors is None:
            self.console_errors = []

