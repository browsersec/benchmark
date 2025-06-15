#!/usr/bin/env python3
"""
KubeBrowse Comprehensive Benchmarking Suite
===========================================
This suite performs load testing and monitoring for the KubeBrowse application
with detailed metrics collection and visualization for white paper analysis.
"""

import asyncio
import threading
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import signal
import sys
import os
import argparse

# Core libraries
import pandas as pd
import numpy as np
# Set matplotlib backend before importing pyplot to avoid GUI issues
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.animation import FuncAnimation
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

# Kubernetes and monitoring
from kubernetes import client, config
import psutil
import requests
import websocket
from prometheus_client.parser import text_string_to_metric_families

# Selenium for browser automation
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kubebrowse_benchmark.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class BenchmarkConfig:
    """Configuration for benchmark parameters"""
    target_url: str = "http://4.156.203.206/"
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
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

class KubernetesMonitor:
    """Monitor Kubernetes cluster metrics"""
    
    def __init__(self, namespace: str, kubeconfig_path: Optional[str] = None):
        self.namespace = namespace
        self.kubeconfig_path = kubeconfig_path
        
        try:
            if kubeconfig_path:
                logger.info(f"Using custom kubeconfig: {kubeconfig_path}")
                config.load_kube_config(config_file=kubeconfig_path)
            else:
                try:
                    config.load_incluster_config()
                    logger.info("Using in-cluster configuration")
                except:
                    config.load_kube_config()
                    logger.info("Using default kubeconfig from kubectl context")
        except Exception as e:
            logger.error(f"Failed to load Kubernetes configuration: {e}")
            raise
        
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.metrics_v1beta1 = client.CustomObjectsApi()
        
    def get_node_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get CPU and memory usage for all nodes"""
        metrics = {}
        try:
            nodes = self.v1.list_node()
            for node in nodes.items:
                node_name = node.metadata.name
                
                # Get node metrics from metrics server
                try:
                    node_metrics = self.metrics_v1beta1.get_cluster_custom_object(
                        group="metrics.k8s.io",
                        version="v1beta1",
                        plural="nodes",
                        name=node_name
                    )
                    
                    cpu_usage = self._parse_cpu(node_metrics['usage']['cpu'])
                    memory_usage = self._parse_memory(node_metrics['usage']['memory'])
                    
                    # Get allocatable resources
                    cpu_allocatable = self._parse_cpu(node.status.allocatable['cpu'])
                    memory_allocatable = self._parse_memory(node.status.allocatable['memory'])
                    
                    metrics[node_name] = {
                        'cpu_usage_cores': cpu_usage,
                        'memory_usage_bytes': memory_usage,
                        'cpu_usage_percent': (cpu_usage / cpu_allocatable) * 100,
                        'memory_usage_percent': (memory_usage / memory_allocatable) * 100,
                        'cpu_allocatable': cpu_allocatable,
                        'memory_allocatable': memory_allocatable
                    }
                except Exception as e:
                    logger.warning(f"Could not get metrics for node {node_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error getting node metrics: {e}")
            
        return metrics
    
    def get_pod_metrics(self, label_selector: str = None) -> Dict[str, Dict[str, Any]]:
        """Get pod information and metrics"""
        pods_info = {}
        try:
            if label_selector:
                pods = self.v1.list_namespaced_pod(
                    namespace=self.namespace,
                    label_selector=label_selector
                )
            else:
                pods = self.v1.list_namespaced_pod(namespace=self.namespace)
                
            for pod in pods.items:
                pod_name = pod.metadata.name
                
                # Fix container status checking
                container_statuses = pod.status.container_statuses or []
                ready_containers = [cs for cs in container_statuses if cs.ready]
                total_containers = len(container_statuses)
                
                pods_info[pod_name] = {
                    'status': pod.status.phase,
                    'node_name': pod.spec.node_name,
                    'creation_timestamp': pod.metadata.creation_timestamp,
                    'labels': pod.metadata.labels or {},
                    'ready': len(ready_containers) == total_containers and total_containers > 0,
                    'restart_count': sum(cs.restart_count for cs in container_statuses)
                }
                
                # Try to get pod metrics
                try:
                    pod_metrics = self.metrics_v1beta1.get_namespaced_custom_object(
                        group="metrics.k8s.io",
                        version="v1beta1",
                        namespace=self.namespace,
                        plural="pods",
                        name=pod_name
                    )
                    
                    for container in pod_metrics.get('containers', []):
                        container_name = container['name']
                        cpu_usage = self._parse_cpu(container['usage']['cpu'])
                        memory_usage = self._parse_memory(container['usage']['memory'])
                        
                        pods_info[pod_name][f'{container_name}_cpu_usage'] = cpu_usage
                        pods_info[pod_name][f'{container_name}_memory_usage'] = memory_usage
                        
                except Exception as e:
                    logger.debug(f"Could not get metrics for pod {pod_name}: {e}")
                    
        except Exception as e:
            logger.error(f"Error getting pod metrics: {e}")
            
        return pods_info
    
    def get_hpa_status(self) -> Dict[str, Dict[str, Any]]:
        """Get HPA status for all HPAs in namespace"""
        hpa_status = {}
        try:
            hpa_v2 = client.AutoscalingV2Api()
            hpas = hpa_v2.list_namespaced_horizontal_pod_autoscaler(self.namespace)
            
            for hpa in hpas.items:
                hpa_name = hpa.metadata.name
                hpa_status[hpa_name] = {
                    'current_replicas': hpa.status.current_replicas or 0,
                    'desired_replicas': hpa.status.desired_replicas or 0,
                    'min_replicas': hpa.spec.min_replicas or 0,
                    'max_replicas': hpa.spec.max_replicas or 0,
                    'target_ref': hpa.spec.scale_target_ref.name,
                    'current_metrics': []
                }
                
                if hpa.status.current_metrics:
                    for metric in hpa.status.current_metrics:
                        if metric.resource:
                            hpa_status[hpa_name]['current_metrics'].append({
                                'type': 'resource',
                                'name': metric.resource.name,
                                'current_utilization': metric.resource.current.average_utilization
                            })
                        elif metric.pods:
                            hpa_status[hpa_name]['current_metrics'].append({
                                'type': 'pods',
                                'name': metric.pods.metric.name,
                                'current_value': metric.pods.current.average_value
                            })
                            
        except Exception as e:
            logger.error(f"Error getting HPA status: {e}")
            
        return hpa_status
    
    @staticmethod
    def _parse_cpu(cpu_str: str) -> float:
        """Parse CPU string to cores"""
        if cpu_str.endswith('n'):
            return float(cpu_str[:-1]) / 1e9
        elif cpu_str.endswith('u'):
            return float(cpu_str[:-1]) / 1e6
        elif cpu_str.endswith('m'):
            return float(cpu_str[:-1]) / 1000
        else:
            return float(cpu_str)
    
    @staticmethod
    def _parse_memory(memory_str: str) -> float:
        """Parse memory string to bytes"""
        units = {'Ki': 1024, 'Mi': 1024**2, 'Gi': 1024**3, 'Ti': 1024**4}
        for unit, multiplier in units.items():
            if memory_str.endswith(unit):
                return float(memory_str[:-len(unit)]) * multiplier
        return float(memory_str)

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

class BrowserSimulator:
    """Simulate browser sessions using Selenium"""
    
    def __init__(self, config: BenchmarkConfig, session_id: str):
        self.config = config
        self.session_id = session_id
        self.driver = None
        self.metrics = SessionMetrics(session_id=session_id, start_time=datetime.now())
        
    def setup_driver(self):
        """Setup Chrome driver with options"""
        chrome_options = Options()
        # chrome_options.add_argument('--headless')  # Commented out to show browser window
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')  # Start with maximized window
        chrome_options.add_argument('--disable-extensions')  # Disable extensions for faster startup
        chrome_options.add_argument('--disable-plugins')   # Disable plugins for faster startup
        chrome_options.add_argument('--disable-images')    # Disable image loading for faster page loads
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(self.config.api_timeout)
            
            # Minimal wait after browser initiation - prioritize quick start
            logger.debug(f"Session {self.session_id}: Browser initiated, starting immediately")
            time.sleep(0.5)  # Minimal wait for browser stability
            
            return True
        except Exception as e:
            self.metrics.errors.append(f"Driver setup failed: {e}")
            return False
    
    def run_session(self) -> SessionMetrics:
        """Run a complete browser session simulation"""
        logger.info(f"Session {self.session_id}: Starting session")
        
        if not self.setup_driver():
            self.metrics.end_time = datetime.now()
            return self.metrics
            
        try:
            # Navigate to application immediately
            logger.info(f"Session {self.session_id}: Navigating to {self.config.target_url}")
            start_time = time.time()
            self.driver.get(self.config.target_url)
            self.metrics.total_api_calls += 1
            
            # Wait for page load with shorter timeout
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            logger.info(f"Session {self.session_id}: Page loaded, starting interactions")
            
            # Start interactions immediately - no additional wait
            self._simulate_user_interactions()
            
        except Exception as e:
            self.metrics.errors.append(f"Session error: {e}")
            self.metrics.failed_api_calls += 1
            logger.error(f"Session {self.session_id}: Error - {e}")
        finally:
            # Don't quit the driver automatically - keep window open
            # if self.driver:
            #     self.driver.quit()
            self.metrics.end_time = datetime.now()
            
        return self.metrics
    
    def _simulate_user_interactions(self):
        """Simulate the user interactions from the test"""
        try:
            # Minimal wait for page stability - prioritize immediate interaction
            logger.debug(f"Session {self.session_id}: Starting click simulation immediately")
            time.sleep(0.5)  # Very short wait for DOM stability
            
            # Click first element if available - start timing immediately
            first_click_start = time.time()
            logger.info(f"Session {self.session_id}: Attempting first click")
            
            element = WebDriverWait(self.driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".mb-6:nth-child(1) .ml-3"))
            )
            element.click()
            self.metrics.first_click_response_time = time.time() - first_click_start
            self.metrics.total_api_calls += 1
            logger.info(f"Session {self.session_id}: First click completed in {self.metrics.first_click_response_time:.3f}s")
            
            # Short wait before next interaction
            time.sleep(0.5)
            
            # Click first py-2 button
            logger.info(f"Session {self.session_id}: Looking for py-2 elements")
            py2_elements = self.driver.find_elements(By.CSS_SELECTOR, ".py-2")
            if py2_elements and py2_elements[0].is_enabled() and py2_elements[0].is_displayed():
                py2_elements[0].click()
                self.metrics.total_api_calls += 1
                logger.info(f"Session {self.session_id}: Clicked first py-2 button")
                time.sleep(0.5)
                
                # Check for second py-2 button or wait like in selenium test
                py2_elements_after = self.driver.find_elements(By.CSS_SELECTOR, ".py-2")
                if len(py2_elements_after) > 1:
                    # Multiple py-2 elements found, click the second one
                    if py2_elements_after[1].is_enabled() and py2_elements_after[1].is_displayed():
                        py2_elements_after[1].click()
                        self.metrics.total_api_calls += 1
                        logger.info(f"Session {self.session_id}: Successfully clicked second py-2 button")
                else:
                    # Keep window open like in selenium test - use proper wait mechanism
                    logger.info(f"Session {self.session_id}: Keeping browser window open...")
                    # Use a proper wait mechanism instead of extremely large sleep
                    try:
                        # Wait for user to manually close or for a reasonable timeout
                        # This prevents the timestamp overflow issue
                        wait_time = 3600  # 1 hour maximum wait
                        start_wait = time.time()
                        while time.time() - start_wait < wait_time:
                            if not self.driver or not self.driver.service.is_connectable():
                                break
                            time.sleep(30)  # Check every 30 seconds if browser is still open
                    except Exception as e:
                        logger.info(f"Session {self.session_id}: Wait interrupted: {e}")
            else:
                logger.warning(f"Session {self.session_id}: No py-2 elements found or not clickable")
                    
        except TimeoutException:
            self.metrics.errors.append("Timeout waiting for elements")
            self.metrics.failed_api_calls += 1
            logger.error(f"Session {self.session_id}: Timeout waiting for elements")
        except Exception as e:
            self.metrics.errors.append(f"Interaction error - {e}")
            self.metrics.failed_api_calls += 1
            logger.error(f"Session {self.session_id}: Interaction error - {e}")
    
    def close_driver(self):
        """Manually close the driver when needed"""
        if self.driver:
            self.driver.quit()
            self.driver = None

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

class MetricsCollector:
    """Collect and store all metrics during benchmark"""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.k8s_monitor = KubernetesMonitor(config.namespace, config.kubeconfig_path)
        self.sessions_monitor = None
        
        if config.enable_sessions_monitoring and config.sessions_api_url:
            self.sessions_monitor = SessionsAPIMonitor(
                config.sessions_api_url,
                config.sessions_api_insecure,
                config.api_timeout
            )
            
        self.metrics_data = {
            'timestamps': [],
            'node_metrics': {},
            'pod_counts': [],
            'hpa_metrics': {},
            'session_metrics': [],
            'websocket_metrics': [],
            'api_latency': [],
            'api_sessions': []  # New field for API sessions data
        }
        self.running = False
        
    def start_collection(self):
        """Start metrics collection in background thread"""
        self.running = True
        self.collection_thread = threading.Thread(target=self._collect_loop)
        self.collection_thread.daemon = True
        self.collection_thread.start()
        
    def stop_collection(self):
        """Stop metrics collection"""
        self.running = False
        if hasattr(self, 'collection_thread'):
            self.collection_thread.join(timeout=5)
            
    def _collect_loop(self):
        """Main collection loop"""
        while self.running:
            timestamp = datetime.now()
            self.metrics_data['timestamps'].append(timestamp)
            
            try:
                # Collect node metrics
                node_metrics = self.k8s_monitor.get_node_metrics()
                for node_name, metrics in node_metrics.items():
                    if node_name not in self.metrics_data['node_metrics']:
                        self.metrics_data['node_metrics'][node_name] = {
                            'cpu_usage': [], 'memory_usage': [], 
                            'cpu_percent': [], 'memory_percent': []
                        }
                    
                    self.metrics_data['node_metrics'][node_name]['cpu_usage'].append(
                        metrics['cpu_usage_cores']
                    )
                    self.metrics_data['node_metrics'][node_name]['memory_usage'].append(
                        metrics['memory_usage_bytes'] / (1024**3)  # GB
                    )
                    self.metrics_data['node_metrics'][node_name]['cpu_percent'].append(
                        metrics['cpu_usage_percent']
                    )
                    self.metrics_data['node_metrics'][node_name]['memory_percent'].append(
                        metrics['memory_usage_percent']
                    )
                
                # Collect pod counts
                browser_pods = self.k8s_monitor.get_pod_metrics(
                    label_selector="app=browser-sandbox-test"
                )
                running_pods = sum(1 for pod in browser_pods.values() 
                                 if pod['status'] == 'Running')
                self.metrics_data['pod_counts'].append(running_pods)
                
                # Collect sessions API data
                if self.sessions_monitor:
                    sessions_data = self.sessions_monitor.get_active_sessions()
                    self.metrics_data['api_sessions'].append(sessions_data)
                
                # Collect HPA metrics
                hpa_status = self.k8s_monitor.get_hpa_status()
                for hpa_name, status in hpa_status.items():
                    if hpa_name not in self.metrics_data['hpa_metrics']:
                        self.metrics_data['hpa_metrics'][hpa_name] = {
                            'current_replicas': [], 'desired_replicas': [],
                            'cpu_utilization': [], 'memory_utilization': []
                        }
                    
                    self.metrics_data['hpa_metrics'][hpa_name]['current_replicas'].append(
                        status['current_replicas']
                    )
                    self.metrics_data['hpa_metrics'][hpa_name]['desired_replicas'].append(
                        status['desired_replicas']
                    )
                    
                    # Extract CPU and memory utilization
                    cpu_util = next((m['current_utilization'] for m in status['current_metrics'] 
                                   if m['type'] == 'resource' and m['name'] == 'cpu'), 0)
                    memory_util = next((m['current_utilization'] for m in status['current_metrics'] 
                                      if m['type'] == 'resource' and m['name'] == 'memory'), 0)
                    
                    self.metrics_data['hpa_metrics'][hpa_name]['cpu_utilization'].append(cpu_util)
                    self.metrics_data['hpa_metrics'][hpa_name]['memory_utilization'].append(memory_util)
                
                logger.debug(f"Collected metrics at {timestamp}")
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                
            time.sleep(self.config.polling_interval)
    
    def add_session_metrics(self, session_metrics: SessionMetrics):
        """Add session metrics to collection"""
        self.metrics_data['session_metrics'].append(asdict(session_metrics))
    
    def save_metrics(self, filename: str = None):
        """Save all collected metrics to file"""
        if filename is None:
            filename = f"kubebrowse_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
        # Convert datetime objects to strings for JSON serialization
        serializable_data = self._make_serializable(self.metrics_data.copy())
        
        with open(filename, 'w') as f:
            json.dump(serializable_data, f, indent=2)
            
        logger.info(f"Metrics saved to {filename}")
        return filename
    
    def _make_serializable(self, obj):
        """Convert datetime objects to strings for JSON serialization"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._make_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        else:
            return obj

class PeriodicVisualizationSaver:
    """Save visualizations at periodic intervals during benchmark"""
    
    def __init__(self, metrics_collector: MetricsCollector, config: BenchmarkConfig):
        self.metrics_collector = metrics_collector
        self.config = config
        self.running = False
        self.save_counter = 0
        self._lock = threading.Lock()  # Add thread lock for safety
        
        # Create output directory
        os.makedirs(self.config.output_dir, exist_ok=True)
        
    def start_saving(self):
        """Start periodic visualization saving in background thread"""
        if not self.config.save_visualizations:
            return
            
        self.running = True
        self.save_thread = threading.Thread(target=self._save_loop)
        self.save_thread.daemon = True
        self.save_thread.start()
        logger.info(f"Started periodic visualization saving every {self.config.save_interval} seconds")
        
    def stop_saving(self):
        """Stop periodic visualization saving"""
        self.running = False
        if hasattr(self, 'save_thread'):
            self.save_thread.join(timeout=5)
            
    def _save_loop(self):
        """Main saving loop"""
        while self.running:
            time.sleep(self.config.save_interval)
            if self.running:  # Check again after sleep
                self._save_current_visualizations()
                
    def _save_current_visualizations(self):
        """Save current state visualizations"""
        with self._lock:  # Thread safety
            try:
                self.save_counter += 1
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                snapshot_dir = f"{self.config.output_dir}/snapshot_{self.save_counter:03d}_{timestamp}"
                os.makedirs(snapshot_dir, exist_ok=True)
                
                data = self.metrics_collector.metrics_data
                
                # Only save if we have data
                if not data['timestamps']:
                    logger.debug("No data available for visualization yet")
                    return
                    
                timestamps = data['timestamps']
                
                # Ensure matplotlib is using non-interactive backend
                plt.ioff()
                matplotlib.use('Agg')
                
                # Create enhanced dashboard visualization with sessions monitoring
                try:
                    fig, axes = plt.subplots(3, 3, figsize=(20, 15))
                    fig.suptitle(f'KubeBrowse Comprehensive Performance Dashboard - {timestamp}', fontsize=16, fontweight='bold')
                    
                    # Node CPU Usage
                    axes[0, 0].set_title('Node CPU Usage (%)')
                    axes[0, 0].set_xlabel('Time Points')
                    axes[0, 0].set_ylabel('CPU %')
                    axes[0, 0].grid(True, alpha=0.3)
                    
                    if data['node_metrics']:
                        time_points = list(range(len(timestamps)))
                        for node_name, metrics in data['node_metrics'].items():
                            if metrics['cpu_percent']:
                                axes[0, 0].plot(time_points[-len(metrics['cpu_percent']):], 
                                               metrics['cpu_percent'], 
                                               label=f'{node_name}', marker='o', markersize=3)
                        axes[0, 0].legend()
                    
                    # Node Memory Usage
                    axes[0, 1].set_title('Node Memory Usage (%)')
                    axes[0, 1].set_xlabel('Time Points')
                    axes[0, 1].set_ylabel('Memory %')
                    axes[0, 1].grid(True, alpha=0.3)
                    
                    if data['node_metrics']:
                        time_points = list(range(len(timestamps)))
                        for node_name, metrics in data['node_metrics'].items():
                            if metrics['memory_percent']:
                                axes[0, 1].plot(time_points[-len(metrics['memory_percent']):], 
                                               metrics['memory_percent'], 
                                               label=f'{node_name}', marker='s', markersize=3)
                        axes[0, 1].legend()
                    
                    # Running Pods
                    axes[0, 2].set_title('Running Pods')
                    axes[0, 2].set_xlabel('Time Points')
                    axes[0, 2].set_ylabel('Pod Count')
                    axes[0, 2].grid(True, alpha=0.3)
                    
                    if data['pod_counts']:
                        time_points = list(range(len(data['pod_counts'])))
                        axes[0, 2].plot(time_points, data['pod_counts'], 
                                       color='blue', marker='o', markersize=4)
                        axes[0, 2].fill_between(time_points, data['pod_counts'], alpha=0.3)
                    
                    # API Active Sessions (NEW)
                    axes[1, 0].set_title('API Active Sessions')
                    axes[1, 0].set_xlabel('Time Points')
                    axes[1, 0].set_ylabel('Active Sessions')
                    axes[1, 0].grid(True, alpha=0.3)
                    
                    if data['api_sessions']:
                        time_points = list(range(len(data['api_sessions'])))
                        active_sessions = [s.get('active_sessions', 0) for s in data['api_sessions']]
                        total_connections = [s.get('total_connections', 0) for s in data['api_sessions']]
                        
                        axes[1, 0].plot(time_points, active_sessions, 
                                       color='green', marker='o', markersize=4, label='Active Sessions')
                        axes[1, 0].plot(time_points, total_connections, 
                                       color='orange', marker='s', markersize=4, label='Total Connections')
                        axes[1, 0].legend()
                        axes[1, 0].fill_between(time_points, active_sessions, alpha=0.3, color='green')
                    
                    # Session Summary
                    axes[1, 1].set_title('Session Summary')
                    axes[1, 1].set_xlabel('Status')
                    axes[1, 1].set_ylabel('Count')
                    axes[1, 1].grid(True, alpha=0.3)
                    
                    if data['session_metrics']:
                        total_sessions = len(data['session_metrics'])
                        successful_sessions = sum(1 for s in data['session_metrics'] 
                                                if s.get('failed_api_calls', 0) == 0)
                        failed_sessions = total_sessions - successful_sessions
                        
                        axes[1, 1].bar(['Successful', 'Failed'], 
                                      [successful_sessions, failed_sessions],
                                      color=['green', 'red'], alpha=0.7)
                    
                    # Response Times
                    axes[1, 2].set_title('Recent Response Times')
                    axes[1, 2].set_xlabel('Recent Sessions')
                    axes[1, 2].set_ylabel('Response Time (s)')
                    axes[1, 2].grid(True, alpha=0.3)
                    
                    if data['session_metrics']:
                        recent_sessions = data['session_metrics'][-20:]
                        response_times = [s.get('first_click_response_time', 0) 
                                        for s in recent_sessions 
                                        if s.get('first_click_response_time') is not None]
                        
                        if response_times:
                            axes[1, 2].plot(range(len(response_times)), response_times, 
                                           'go-', markersize=4)
                            axes[1, 2].axhline(y=np.mean(response_times), 
                                              color='red', linestyle='--', 
                                              label=f'Avg: {np.mean(response_times):.2f}s')
                            axes[1, 2].legend()
                    
                    # HPA Replica Counts (NEW)
                    axes[2, 0].set_title('HPA Replica Counts')
                    axes[2, 0].set_xlabel('Time Points')
                    axes[2, 0].set_ylabel('Replicas')
                    axes[2, 0].grid(True, alpha=0.3)
                    
                    if data['hpa_metrics']:
                        time_points = list(range(len(timestamps)))
                        for hpa_name, metrics in data['hpa_metrics'].items():
                            if metrics['current_replicas']:
                                axes[2, 0].plot(time_points[-len(metrics['current_replicas']):], 
                                               metrics['current_replicas'], 
                                               label=f'{hpa_name} Current', marker='o', markersize=3)
                                axes[2, 0].plot(time_points[-len(metrics['desired_replicas']):], 
                                               metrics['desired_replicas'], 
                                               label=f'{hpa_name} Desired', marker='s', markersize=3, linestyle='--')
                        axes[2, 0].legend()
                    
                    # API vs Browser Sessions Correlation (NEW)
                    axes[2, 1].set_title('API vs Browser Sessions')
                    axes[2, 1].set_xlabel('Time Points')
                    axes[2, 1].set_ylabel('Session Count')
                    axes[2, 1].grid(True, alpha=0.3)
                    
                    if data['api_sessions'] and data['session_metrics']:
                        time_points = list(range(min(len(data['api_sessions']), len(timestamps))))
                        api_sessions = [data['api_sessions'][i].get('active_sessions', 0) for i in range(len(time_points))]
                        
                        # Calculate browser sessions over time (cumulative)
                        browser_sessions_count = []
                        for i in range(len(time_points)):
                            # Count sessions active at this time point
                            if i < len(timestamps):
                                current_time = timestamps[i]
                                active_browser_sessions = sum(1 for s in data['session_metrics'] 
                                                            if datetime.fromisoformat(s['start_time']) <= current_time and 
                                                               (s.get('end_time') is None or datetime.fromisoformat(s['end_time']) >= current_time))
                                browser_sessions_count.append(active_browser_sessions)
                            else:
                                browser_sessions_count.append(0)
                        
                        axes[2, 1].plot(time_points, api_sessions, 
                                       color='green', marker='o', markersize=4, label='API Active Sessions')
                        axes[2, 1].plot(time_points, browser_sessions_count, 
                                       color='blue', marker='s', markersize=4, label='Browser Sessions')
                        axes[2, 1].legend()
                    
                    # Success Rate Over Time
                    axes[2, 2].set_title('Success Rate Over Time')
                    axes[2, 2].set_xlabel('Time Buckets')
                    axes[2, 2].set_ylabel('Success Rate (%)')
                    axes[2, 2].grid(True, alpha=0.3)
                    axes[2, 2].set_ylim(0, 105)
                    
                    if data['session_metrics'] and len(data['session_metrics']) > 5:
                        bucket_size = max(1, len(data['session_metrics']) // 10)
                        success_rates = []
                        
                        for i in range(0, len(data['session_metrics']), bucket_size):
                            bucket = data['session_metrics'][i:i+bucket_size]
                            total_calls = sum(s.get('total_api_calls', 0) for s in bucket)
                            failed_calls = sum(s.get('failed_api_calls', 0) for s in bucket)
                            
                            if total_calls > 0:
                                success_rate = ((total_calls - failed_calls) / total_calls) * 100
                                success_rates.append(success_rate)
                        
                        if success_rates:
                            axes[2, 2].plot(range(len(success_rates)), success_rates, 
                                           'b-o', markersize=4)
                            axes[2, 2].axhline(y=np.mean(success_rates), 
                                              color='green', linestyle='--', 
                                              label=f'Avg: {np.mean(success_rates):.1f}%')
                            axes[2, 2].legend()
                    
                    plt.tight_layout()
                    
                    # Save the dashboard
                    dashboard_file = f"{snapshot_dir}/dashboard.png"
                    plt.savefig(dashboard_file, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
                    
                    # Properly close the figure to free memory
                    plt.close(fig)
                    plt.clf()  # Clear any remaining state
                    
                except Exception as plot_error:
                    logger.error(f"Error creating plot: {plot_error}")
                    # Try to clean up any partial plot state
                    try:
                        plt.close('all')
                        plt.clf()
                    except:
                        pass
                
                # Save metrics data snapshot
                metrics_file = f"{snapshot_dir}/metrics_snapshot.json"
                serializable_data = self.metrics_collector._make_serializable(data.copy())
                with open(metrics_file, 'w') as f:
                    json.dump(serializable_data, f, indent=2)
                
                # Create enhanced summary file
                summary_file = f"{snapshot_dir}/summary.txt"
                with open(summary_file, 'w') as f:
                    f.write(f"Benchmark Snapshot - {timestamp}\n")
                    f.write("=" * 40 + "\n\n")
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write(f"Data points collected: {len(timestamps)}\n")
                    f.write(f"Total sessions: {len(data['session_metrics'])}\n")
                    f.write(f"Running pods: {data['pod_counts'][-1] if data['pod_counts'] else 0}\n")
                    
                    # Add API sessions summary
                    if data['api_sessions']:
                        latest_api_data = data['api_sessions'][-1]
                        f.write(f"API Active Sessions: {latest_api_data.get('active_sessions', 0)}\n")
                        f.write(f"API Total Connections: {latest_api_data.get('total_connections', 0)}\n")
                    
                    if data['session_metrics']:
                        successful = sum(1 for s in data['session_metrics'] 
                                       if s.get('failed_api_calls', 0) == 0)
                        f.write(f"Successful sessions: {successful}\n")
                        f.write(f"Failed sessions: {len(data['session_metrics']) - successful}\n")
                        
                        response_times = [s.get('first_click_response_time') 
                                        for s in data['session_metrics'] 
                                        if s.get('first_click_response_time') is not None]
                        if response_times:
                            f.write(f"Average response time: {np.mean(response_times):.3f}s\n")
                            f.write(f"Max response time: {max(response_times):.3f}s\n")
                
                logger.info(f"Saved visualization snapshot {self.save_counter} to {snapshot_dir}")
                
            except Exception as e:
                logger.error(f"Error saving visualization snapshot: {e}")
                # Clean up any matplotlib state on error
                try:
                    plt.close('all')
                    plt.clf()
                except:
                    pass

class LoadTestController:
    """Control the load testing process"""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.metrics_collector = MetricsCollector(config)
        self.visualization_saver = PeriodicVisualizationSaver(self.metrics_collector, config) if config.save_visualizations else None
        self.active_sessions = {}
        self.completed_sessions = []
        self.running = False
        self.last_session_start_time = 0  # Track last session start time
        
    def run_benchmark(self):
        """Run the complete benchmark test"""
        logger.info("Starting KubeBrowse benchmark...")
        
        # Start metrics collection
        self.metrics_collector.start_collection()
        
        # Start periodic visualization saving
        if self.visualization_saver:
            self.visualization_saver.start_saving()
        
        self.running = True
        
        try:
            # Calculate user ramp-up schedule
            total_time = (self.config.ramp_up_duration + 
                         self.config.test_duration + 
                         self.config.ramp_down_duration)
            
            user_schedule = self._calculate_user_schedule()
            
            # Execute load test
            with ThreadPoolExecutor(max_workers=self.config.max_concurrent_users * 2) as executor:
                futures = []
                
                start_time = time.time()
                for schedule_time, user_count in user_schedule:
                    # Wait until schedule time
                    while time.time() - start_time < schedule_time and self.running:
                        time.sleep(0.1)
                    
                    if not self.running:
                        break
                        
                    # Start new sessions to reach target user count with controlled intervals
                    current_active = len(self.active_sessions)
                    if user_count > current_active:
                        new_sessions = user_count - current_active
                        logger.info(f"Starting {new_sessions} new sessions with {self.config.session_start_interval}s interval")
                        
                        for i in range(new_sessions):
                            # Enforce session start interval
                            current_time = time.time()
                            time_since_last_start = current_time - self.last_session_start_time
                            
                            if time_since_last_start < self.config.session_start_interval:
                                wait_time = self.config.session_start_interval - time_since_last_start
                                logger.debug(f"Waiting {wait_time:.2f}s before starting next session")
                                time.sleep(wait_time)
                            
                            session_id = f"user_{len(self.completed_sessions) + len(self.active_sessions) + i + 1}"
                            simulator = BrowserSimulator(self.config, session_id)
                            future = executor.submit(self._run_session, simulator)
                            futures.append(future)
                            self.active_sessions[session_id] = future
                            self.last_session_start_time = time.time()
                            
                            logger.info(f"Started session {session_id} at {datetime.now().strftime('%H:%M:%S')}")
                    
                    # Clean up completed sessions
                    self._cleanup_completed_sessions()
                    
                    logger.info(f"Active sessions: {len(self.active_sessions)}, "
                              f"Completed: {len(self.completed_sessions)}")
                
                # Wait for all sessions to complete
                logger.info("Waiting for all sessions to complete...")
                for future in as_completed(futures):
                    try:
                        session_metrics = future.result()
                        self.completed_sessions.append(session_metrics)
                        self.metrics_collector.add_session_metrics(session_metrics)
                    except Exception as e:
                        logger.error(f"Session failed: {e}")
                        
        except KeyboardInterrupt:
            logger.info("Benchmark interrupted by user")
        finally:
            self.running = False
            self.metrics_collector.stop_collection()
            
            # Stop visualization saving
            if self.visualization_saver:
                self.visualization_saver.stop_saving()
            
        logger.info(f"Benchmark completed. Total sessions: {len(self.completed_sessions)}")
        return self.metrics_collector.save_metrics()
    
    def _calculate_user_schedule(self) -> List[tuple]:
        """Calculate when to start/stop users during test"""
        schedule = []
        
        # Ramp up phase - more frequent scheduling to respect session intervals
        ramp_up_steps = max(10, self.config.ramp_up_duration // 30)  # At least every 30 seconds
        for i in range(ramp_up_steps):
            time_point = i * (self.config.ramp_up_duration / ramp_up_steps)
            user_count = int((i + 1) * self.config.max_concurrent_users / ramp_up_steps)
            schedule.append((time_point, user_count))
        
        # Steady state phase
        steady_start = self.config.ramp_up_duration
        for i in range(self.config.test_duration // 60):  # Every minute during steady state
            time_point = steady_start + i * 60
            schedule.append((time_point, self.config.max_concurrent_users))
        
        # Ramp down phase
        ramp_down_start = self.config.ramp_up_duration + self.config.test_duration
        ramp_down_steps = max(10, self.config.ramp_down_duration // 30)
        for i in range(ramp_down_steps):
            time_point = ramp_down_start + i * (self.config.ramp_down_duration / ramp_down_steps)
            user_count = int(self.config.max_concurrent_users * 
                           (1 - (i + 1) / ramp_down_steps))
            schedule.append((time_point, max(0, user_count)))
        
        return schedule
    
    def _run_session(self, simulator: BrowserSimulator) -> SessionMetrics:
        """Run a single browser session"""
        try:
            return simulator.run_session()
        except Exception as e:
            logger.error(f"Session {simulator.session_id} failed: {e}")
            simulator.metrics.errors.append(f"Session failed: {e}")
            simulator.metrics.end_time = datetime.now()
            return simulator.metrics
        # Note: Driver is intentionally not closed here to keep windows open
    
    def _cleanup_completed_sessions(self):
        """Remove completed sessions from active tracking"""
        completed_keys = []
        for session_id, future in self.active_sessions.items():
            if future.done():
                completed_keys.append(session_id)
                
        for key in completed_keys:
            del self.active_sessions[key]

class BenchmarkVisualizer:
    """Create comprehensive visualizations of benchmark results"""
    
    def __init__(self, metrics_file: str):
        with open(metrics_file, 'r') as f:
            self.data = json.load(f)
        self.timestamps = [datetime.fromisoformat(ts) for ts in self.data['timestamps']]
        
        # Ensure we're using non-interactive backend
        matplotlib.use('Agg')
        plt.ioff()
        
    def create_comprehensive_dashboard(self, output_dir: str = "benchmark_results"):
        """Create all visualizations for the benchmark results"""
        os.makedirs(output_dir, exist_ok=True)
        
        # Set style
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # Create individual plots
        self._plot_node_metrics(output_dir)
        self._plot_pod_scaling(output_dir)
        self._plot_hpa_metrics(output_dir)
        self._plot_performance_metrics(output_dir)
        self._plot_session_analysis(output_dir)
        self._create_interactive_dashboard(output_dir)
        self._generate_summary_report(output_dir)
        
        # Clean up matplotlib state
        plt.close('all')
        plt.clf()
        
        logger.info(f"All visualizations saved to {output_dir}/")
    
    def _plot_node_metrics(self, output_dir: str):
        """Plot node CPU and memory usage"""
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Kubernetes Node Resource Usage', fontsize=16, fontweight='bold')
        
        for node_name, metrics in self.data['node_metrics'].items():
            # CPU Usage (Cores)
            axes[0, 0].plot(self.timestamps, metrics['cpu_usage'], 
                          label=f'{node_name}', linewidth=2, marker='o', markersize=3)
            
            # Memory Usage (GB)
            axes[0, 1].plot(self.timestamps, metrics['memory_usage'], 
                          label=f'{node_name}', linewidth=2, marker='s', markersize=3)
            
            # CPU Usage (%)
            axes[1, 0].plot(self.timestamps, metrics['cpu_percent'], 
                          label=f'{node_name}', linewidth=2, marker='^', markersize=3)
            
            # Memory Usage (%)
            axes[1, 1].plot(self.timestamps, metrics['memory_percent'], 
                          label=f'{node_name}', linewidth=2, marker='d', markersize=3)
        
        # Customize subplots
        axes[0, 0].set_title('CPU Usage (Cores)', fontweight='bold')
        axes[0, 0].set_ylabel('CPU Cores')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        axes[0, 1].set_title('Memory Usage (GB)', fontweight='bold')
        axes[0, 1].set_ylabel('Memory (GB)')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        axes[1, 0].set_title('CPU Usage (%)', fontweight='bold')
        axes[1, 0].set_ylabel('CPU Utilization (%)')
        axes[1, 0].set_xlabel('Time')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        axes[1, 1].set_title('Memory Usage (%)', fontweight='bold')
        axes[1, 1].set_ylabel('Memory Utilization (%)')
        axes[1, 1].set_xlabel('Time')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
        
        # Format x-axis
        for ax in axes.flat:
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(f'{output_dir}/node_metrics.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_pod_scaling(self, output_dir: str):
        """Plot pod scaling over time"""
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Plot browser sandbox pods
        ax.plot(self.timestamps, self.data['pod_counts'], 
               linewidth=3, marker='o', markersize=6, color='#2E86AB',
               label='Browser Sandbox Pods')
        
        # Add fill area
        ax.fill_between(self.timestamps, self.data['pod_counts'], 
                       alpha=0.3, color='#2E86AB')
        
        ax.set_title('Browser Sandbox Pod Scaling Over Time', 
                    fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Number of Running Pods', fontsize=12)
        ax.legend(fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Add statistics
        max_pods = max(self.data['pod_counts'])
        avg_pods = np.mean(self.data['pod_counts'])
        ax.axhline(y=avg_pods, color='red', linestyle='--', alpha=0.7, 
                  label=f'Average: {avg_pods:.1f}')
        ax.text(0.02, 0.98, f'Max Pods: {max_pods}\nAvg Pods: {avg_pods:.1f}', 
               transform=ax.transAxes, fontsize=11, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f'{output_dir}/pod_scaling.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_hpa_metrics(self, output_dir: str):
        """Plot HPA scaling metrics"""
        if not self.data['hpa_metrics']:
            logger.warning("No HPA metrics available")
            return
            
        n_hpas = len(self.data['hpa_metrics'])
        fig, axes = plt.subplots(n_hpas, 2, figsize=(16, 6 * n_hpas))
        if n_hpas == 1:
            axes = axes.reshape(1, -1)
        
        fig.suptitle('HPA Scaling Metrics', fontsize=16, fontweight='bold')
        
        for i, (hpa_name, metrics) in enumerate(self.data['hpa_metrics'].items()):
            # Replica counts
            axes[i, 0].plot(self.timestamps, metrics['current_replicas'], 
                          label='Current Replicas', linewidth=2, marker='o', color='#1f77b4')
            axes[i, 0].plot(self.timestamps, metrics['desired_replicas'], 
                          label='Desired Replicas', linewidth=2, marker='s', color='#ff7f0e')
            axes[i, 0].set_title(f'{hpa_name} - Replica Scaling', fontweight='bold')
            axes[i, 0].set_ylabel('Replicas')
            axes[i, 0].legend()
            axes[i, 0].grid(True, alpha=0.3)
            
            # Resource utilization
            axes[i, 1].plot(self.timestamps, metrics['cpu_utilization'], 
                          label='CPU Utilization %', linewidth=2, marker='^', color='#2ca02c')
            axes[i, 1].plot(self.timestamps, metrics['memory_utilization'], 
                          label='Memory Utilization %', linewidth=2, marker='d', color='#d62728')
            axes[i, 1].axhline(y=50, color='red', linestyle='--', alpha=0.5, label='Target (50%)')
            axes[i, 1].set_title(f'{hpa_name} - Resource Utilization', fontweight='bold')
            axes[i, 1].set_ylabel('Utilization (%)')
            axes[i, 1].legend()
            axes[i, 1].grid(True, alpha=0.3)
            
            # Format x-axis
            axes[i, 0].tick_params(axis='x', rotation=45)
            axes[i, 1].tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(f'{output_dir}/hpa_metrics.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_performance_metrics(self, output_dir: str):
        """Plot performance and latency metrics"""
        if not self.data['session_metrics']:
            logger.warning("No session metrics available")
            return
            
        sessions_df = pd.DataFrame(self.data['session_metrics'])
        
        # Convert timestamps
        sessions_df['start_time'] = pd.to_datetime(sessions_df['start_time'])
        sessions_df['end_time'] = pd.to_datetime(sessions_df['end_time'])
        sessions_df['duration'] = (sessions_df['end_time'] - sessions_df['start_time']).dt.total_seconds()
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Performance Metrics Analysis', fontsize=16, fontweight='bold')
        
        # API Response Time Distribution
        valid_response_times = sessions_df[sessions_df['first_click_response_time'].notna()]
        if not valid_response_times.empty:
            axes[0, 0].hist(valid_response_times['first_click_response_time'], 
                          bins=30, alpha=0.7, color='skyblue', edgecolor='black')
            axes[0, 0].axvline(valid_response_times['first_click_response_time'].mean(), 
                             color='red', linestyle='--', linewidth=2, 
                             label=f'Mean: {valid_response_times["first_click_response_time"].mean():.2f}s')
            axes[0, 0].set_title('API Response Time Distribution', fontweight='bold')
            axes[0, 0].set_xlabel('Response Time (seconds)')
            axes[0, 0].set_ylabel('Frequency')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
        
        # Session Duration Distribution
        axes[0, 1].hist(sessions_df['duration'], bins=30, alpha=0.7, 
                       color='lightgreen', edgecolor='black')
        axes[0, 1].axvline(sessions_df['duration'].mean(), color='red', 
                         linestyle='--', linewidth=2, 
                         label=f'Mean: {sessions_df["duration"].mean():.1f}s')
        axes[0, 1].set_title('Session Duration Distribution', fontweight='bold')
        axes[0, 1].set_xlabel('Duration (seconds)')
        axes[0, 1].set_ylabel('Frequency')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Success Rate Over Time
        sessions_df['success_rate'] = (sessions_df['total_api_calls'] - sessions_df['failed_api_calls']) / sessions_df['total_api_calls']
        sessions_df['time_bucket'] = pd.cut(sessions_df['start_time'], bins=20)
        success_by_time = sessions_df.groupby('time_bucket')['success_rate'].mean()
        
        axes[1, 0].plot(range(len(success_by_time)), success_by_time.values * 100, 
                       marker='o', linewidth=2, markersize=6, color='orange')
        axes[1, 0].set_title('Success Rate Over Time', fontweight='bold')
        axes[1, 0].set_xlabel('Time Bucket')
        axes[1, 0].set_ylabel('Success Rate (%)')
        axes[1, 0].grid(True, alpha=0.3)
        axes[1, 0].set_ylim(0, 105)
        
        # Error Analysis
        error_counts = {}
        for session in self.data['session_metrics']:
            for error in session.get('errors', []):
                error_type = error.split(':')[0]  # Get error type
                error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        if error_counts:
            axes[1, 1].bar(list(error_counts.keys()), list(error_counts.values()), 
                         color='salmon', alpha=0.7)
            axes[1, 1].set_title('Error Distribution', fontweight='bold')
            axes[1, 1].set_xlabel('Error Type')
            axes[1, 1].set_ylabel('Count')
            axes[1, 1].tick_params(axis='x', rotation=45)
            axes[1, 1].grid(True, alpha=0.3)
        else:
            axes[1, 1].text(0.5, 0.5, 'No Errors Recorded', 
                          ha='center', va='center', transform=axes[1, 1].transAxes,
                          fontsize=14, color='green', fontweight='bold')
            axes[1, 1].set_title('Error Distribution', fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(f'{output_dir}/performance_metrics.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _plot_session_analysis(self, output_dir: str):
        """Plot detailed session analysis"""
        if not self.data['session_metrics']:
            return
            
        sessions_df = pd.DataFrame(self.data['session_metrics'])
        sessions_df['start_time'] = pd.to_datetime(sessions_df['start_time'])
        sessions_df['end_time'] = pd.to_datetime(sessions_df['end_time'])
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Session Analysis Deep Dive', fontsize=16, fontweight='bold')
        
        # Concurrent Sessions Over Time
        time_range = pd.date_range(start=sessions_df['start_time'].min(), 
                                 end=sessions_df['end_time'].max(), freq='10S')
        concurrent_sessions = []
        
        for timestamp in time_range:
            active = sessions_df[
                (sessions_df['start_time'] <= timestamp) & 
                (sessions_df['end_time'] >= timestamp)
            ].shape[0]
            concurrent_sessions.append(active)
        
        axes[0, 0].plot(time_range, concurrent_sessions, linewidth=2, color='purple')
        axes[0, 0].fill_between(time_range, concurrent_sessions, alpha=0.3, color='purple')
        axes[0, 0].set_title('Concurrent Sessions Over Time', fontweight='bold')
        axes[0, 0].set_xlabel('Time')
        axes[0, 0].set_ylabel('Concurrent Sessions')
        axes[0, 0].grid(True, alpha=0.3)
        axes[0, 0].tick_params(axis='x', rotation=45)
        
        # API Calls vs Response Time
        valid_sessions = sessions_df[sessions_df['first_click_response_time'].notna()]
        if not valid_sessions.empty:
            scatter = axes[0, 1].scatter(valid_sessions['total_api_calls'], 
                                       valid_sessions['first_click_response_time'],
                                       c=valid_sessions['failed_api_calls'], 
                                       cmap='Reds', alpha=0.6, s=50)
            axes[0, 1].set_title('API Calls vs Response Time', fontweight='bold')
            axes[0, 1].set_xlabel('Total API Calls')
            axes[0, 1].set_ylabel('First Click Response Time (s)')
            axes[0, 1].grid(True, alpha=0.3)
            plt.colorbar(scatter, ax=axes[0, 1], label='Failed API Calls')
        
        # Session Start Rate
        sessions_df['hour'] = sessions_df['start_time'].dt.floor('5min')
        session_rate = sessions_df.groupby('hour').size()
        
        axes[1, 0].bar(range(len(session_rate)), session_rate.values, 
                      color='teal', alpha=0.7)
        axes[1, 0].set_title('Session Start Rate (5-min buckets)', fontweight='bold')
        axes[1, 0].set_xlabel('Time Bucket')
        axes[1, 0].set_ylabel('Sessions Started')
        axes[1, 0].grid(True, alpha=0.3)
        
        # Performance Percentiles
        if not valid_sessions.empty:
            percentiles = [50, 75, 90, 95, 99]
            response_time_percentiles = [valid_sessions['first_click_response_time'].quantile(p/100) 
                                       for p in percentiles]
            
            axes[1, 1].bar([f'P{p}' for p in percentiles], response_time_percentiles, 
                         color='gold', alpha=0.7)
            axes[1, 1].set_title('Response Time Percentiles', fontweight='bold')
            axes[1, 1].set_xlabel('Percentile')
            axes[1, 1].set_ylabel('Response Time (s)')
            axes[1, 1].grid(True, alpha=0.3)
            
            # Add values on bars
            for i, v in enumerate(response_time_percentiles):
                axes[1, 1].text(i, v + 0.01, f'{v:.2f}s', ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(f'{output_dir}/session_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    def _create_interactive_dashboard(self, output_dir: str):
        """Create interactive Plotly dashboard"""
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=('Node CPU Usage', 'Pod Scaling', 
                          'HPA Replica Scaling', 'Response Time Distribution',
                          'Concurrent Sessions', 'Success Rate'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # Node CPU Usage
        for node_name, metrics in self.data['node_metrics'].items():
            fig.add_trace(
                go.Scatter(x=self.timestamps, y=metrics['cpu_usage'],
                          name=f'{node_name} CPU', mode='lines+markers'),
                row=1, col=1
            )
        
        # Pod Scaling
        fig.add_trace(
            go.Scatter(x=self.timestamps, y=self.data['pod_counts'],
                      name='Browser Pods', mode='lines+markers',
                      fill='tozeroy'),
            row=1, col=2
        )
        
        # HPA Metrics
        if self.data['hpa_metrics']:
            hpa_name = list(self.data['hpa_metrics'].keys())[0]
            metrics = self.data['hpa_metrics'][hpa_name]
            fig.add_trace(
                go.Scatter(x=self.timestamps, y=metrics['current_replicas'],
                          name='Current Replicas', mode='lines+markers'),
                row=2, col=1
            )
            fig.add_trace(
                go.Scatter(x=self.timestamps, y=metrics['desired_replicas'],
                          name='Desired Replicas', mode='lines+markers'),
                row=2, col=1
            )
        
        # Response Time Distribution
        if self.data['session_metrics']:
            sessions_df = pd.DataFrame(self.data['session_metrics'])
            valid_response_times = sessions_df[sessions_df['first_click_response_time'].notna()]
            if not valid_response_times.empty:
                fig.add_trace(
                    go.Histogram(x=valid_response_times['first_click_response_time'],
                               name='Response Time', nbinsx=30),
                    row=2, col=2
                )
        
        # Update layout
        fig.update_layout(
            height=1200,
            title_text="KubeBrowse Interactive Benchmark Dashboard",
            title_x=0.5,
            showlegend=True
        )
        
        fig.write_html(f'{output_dir}/interactive_dashboard.html')
        logger.info(f"Interactive dashboard saved to {output_dir}/interactive_dashboard.html")
    
    def _generate_summary_report(self, output_dir: str):
        """Generate summary report with key metrics"""
        report = {
            'benchmark_summary': {
                'start_time': self.timestamps[0].isoformat() if self.timestamps else None,
                'end_time': self.timestamps[-1].isoformat() if self.timestamps else None,
                'duration_minutes': len(self.timestamps) * 10 / 60 if self.timestamps else 0,
                'total_sessions': len(self.data['session_metrics']),
            },
            'infrastructure_metrics': {},
            'performance_metrics': {},
            'scaling_metrics': {}
        }
        
        # Infrastructure metrics
        if self.data['node_metrics']:
            node_data = list(self.data['node_metrics'].values())[0]
            report['infrastructure_metrics'] = {
                'peak_cpu_usage_cores': max(node_data['cpu_usage']) if node_data['cpu_usage'] else 0,
                'peak_memory_usage_gb': max(node_data['memory_usage']) if node_data['memory_usage'] else 0,
                'avg_cpu_utilization_percent': np.mean(node_data['cpu_percent']) if node_data['cpu_percent'] else 0,
                'avg_memory_utilization_percent': np.mean(node_data['memory_percent']) if node_data['memory_percent'] else 0,
            }
        
        # Pod scaling metrics
        if self.data['pod_counts']:
            report['scaling_metrics'] = {
                'max_pods': max(self.data['pod_counts']),
                'min_pods': min(self.data['pod_counts']),
                'avg_pods': np.mean(self.data['pod_counts']),
                'pod_scaling_events': sum(1 for i in range(1, len(self.data['pod_counts'])) 
                                        if self.data['pod_counts'][i] != self.data['pod_counts'][i-1])
            }
        
        # Performance metrics
        if self.data['session_metrics']:
            sessions_df = pd.DataFrame(self.data['session_metrics'])
            sessions_df['start_time'] = pd.to_datetime(sessions_df['start_time'])
            sessions_df['end_time'] = pd.to_datetime(sessions_df['end_time'])
            sessions_df['duration'] = (sessions_df['end_time'] - sessions_df['start_time']).dt.total_seconds()
            
            valid_response_times = sessions_df[sessions_df['first_click_response_time'].notna()]
            total_api_calls = sessions_df['total_api_calls'].sum()
            total_failed_calls = sessions_df['failed_api_calls'].sum()
            
            report['performance_metrics'] = {
                'avg_response_time_seconds': valid_response_times['first_click_response_time'].mean() if not valid_response_times.empty else 0,
                'p95_response_time_seconds': valid_response_times['first_click_response_time'].quantile(0.95) if not valid_response_times.empty else 0,
                'p99_response_time_seconds': valid_response_times['first_click_response_time'].quantile(0.99) if not valid_response_times.empty else 0,
                'success_rate_percent': ((total_api_calls - total_failed_calls) / total_api_calls * 100) if total_api_calls > 0 else 0,
                'avg_session_duration_seconds': sessions_df['duration'].mean(),
                'total_errors': sum(len(session.get('errors', [])) for session in self.data['session_metrics'])
            }
        
        # Save report
        with open(f'{output_dir}/benchmark_summary.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        # Create readable report
        with open(f'{output_dir}/benchmark_report.md', 'w') as f:
            f.write("# KubeBrowse Benchmark Report\n\n")
            f.write(f"## Test Summary\n")
            f.write(f"- **Start Time:** {report['benchmark_summary']['start_time']}\n")
            f.write(f"- **End Time:** {report['benchmark_summary']['end_time']}\n")
            f.write(f"- **Duration:** {report['benchmark_summary']['duration_minutes']:.1f} minutes\n")
            f.write(f"- **Total Sessions:** {report['benchmark_summary']['total_sessions']}\n\n")
            
            f.write("## Infrastructure Performance\n")
            infra = report['infrastructure_metrics']
            f.write(f"- **Peak CPU Usage:** {infra.get('peak_cpu_usage_cores', 0):.2f} cores\n")
            f.write(f"- **Peak Memory Usage:** {infra.get('peak_memory_usage_gb', 0):.2f} GB\n")
            f.write(f"- **Average CPU Utilization:** {infra.get('avg_cpu_utilization_percent', 0):.1f}%\n")
            f.write(f"- **Average Memory Utilization:** {infra.get('avg_memory_utilization_percent', 0):.1f}%\n\n")
            
            f.write("## Scaling Performance\n")
            scaling = report['scaling_metrics']
            f.write(f"- **Maximum Pods:** {scaling.get('max_pods', 0)}\n")
            f.write(f"- **Minimum Pods:** {scaling.get('min_pods', 0)}\n")
            f.write(f"- **Average Pods:** {scaling.get('avg_pods', 0):.1f}\n")
            f.write(f"- **Scaling Events:** {scaling.get('pod_scaling_events', 0)}\n\n")
            
            f.write("## Application Performance\n")
            perf = report['performance_metrics']
            f.write(f"- **Average Response Time:** {perf.get('avg_response_time_seconds', 0):.3f}s\n")
            f.write(f"- **95th Percentile Response Time:** {perf.get('p95_response_time_seconds', 0):.3f}s\n")
            f.write(f"- **99th Percentile Response Time:** {perf.get('p99_response_time_seconds', 0):.3f}s\n")
            f.write(f"- **Success Rate:** {perf.get('success_rate_percent', 0):.1f}%\n")
            f.write(f"- **Average Session Duration:** {perf.get('avg_session_duration_seconds', 0):.1f}s\n")
            f.write(f"- **Total Errors:** {perf.get('total_errors', 0)}\n")
        
        logger.info(f"Summary report saved to {output_dir}/benchmark_report.md")

def signal_handler(signum, frame):
    """Handle interrupt signals gracefully"""
    logger.info("Received interrupt signal, stopping benchmark...")
    sys.exit(0)

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='KubeBrowse Comprehensive Benchmarking Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --kubeconfig ~/.kube/config-prod --max-users 50
  %(prog)s --namespace my-namespace --save-interval 30
  %(prog)s --target-url http://example.com --test-duration 3600
  %(prog)s --sessions-api-url https://172.18.120.152:30006/sessions/ --sessions-api-insecure
  %(prog)s --browser-init-wait 5 --max-users 10 --session-start-interval 2
        """
    )
    
    # Kubernetes configuration
    parser.add_argument(
        '--kubeconfig', '--kubeconfig-path',
        type=str,
        help='Path to custom kubeconfig file (default: use kubectl default context or in-cluster config)'
    )
    parser.add_argument(
        '--namespace', '-n',
        type=str,
        default='browser-sandbox',
        help='Kubernetes namespace to monitor (default: browser-sandbox)'
    )
    
    # Application configuration
    parser.add_argument(
        '--target-url', '--url',
        type=str,
        default='http://4.156.203.206/',
        help='Target URL for load testing (default: http://4.156.203.206/)'
    )
    
    # Browser configuration
    parser.add_argument(
        '--browser-init-wait',
        type=int,
        default=2,
        help='Wait time in seconds after browser window initiation and page load (default: 2)'
    )
    parser.add_argument(
        '--session-start-interval',
        type=float,
        default=1.0,
        help='Time interval in seconds between starting new sessions (default: 1.0)'
    )
    
    # Sessions API monitoring
    parser.add_argument(
        '--sessions-api-url',
        type=str,
        help='Sessions API endpoint URL for monitoring active sessions (e.g., https://172.18.120.152:30006/sessions/)'
    )
    parser.add_argument(
        '--sessions-api-insecure',
        action='store_true',
        help='Allow insecure HTTPS connections for sessions API'
    )
    parser.add_argument(
        '--enable-sessions-monitoring',
        action='store_true',
        help='Enable sessions API monitoring (automatically enabled if --sessions-api-url is provided)'
    )

    # Load test parameters
    parser.add_argument(
        '--max-users', '--max-concurrent-users',
        type=int,
        default=20,
        help='Maximum number of concurrent users (default: 20)'
    )
    parser.add_argument(
        '--ramp-up-duration',
        type=int,
        default=300,
        help='Ramp-up duration in seconds (default: 300)'
    )
    parser.add_argument(
        '--test-duration',
        type=int,
        default=1800,
        help='Test duration in seconds (default: 1800)'
    )
    parser.add_argument(
        '--ramp-down-duration',
        type=int,
        default=300,
        help='Ramp-down duration in seconds (default: 300)'
    )
    
    # Monitoring configuration
    parser.add_argument(
        '--polling-interval',
        type=int,
        default=10,
        help='Metrics polling interval in seconds (default: 10)'
    )
    parser.add_argument(
        '--api-timeout',
        type=int,
        default=10,
        help='API request timeout in seconds (default: 10)'
    )
    parser.add_argument(
        '--websocket-timeout',
        type=int,
        default=30,
        help='WebSocket connection timeout in seconds (default: 30)'
    )
    
    # Visualization configuration
    parser.add_argument(
        '--save-visualizations',
        action='store_true',
        default=True,
        help='Enable periodic visualization saving (default: enabled)'
    )
    parser.add_argument(
        '--no-save-visualizations',
        action='store_false',
        dest='save_visualizations',
        help='Disable periodic visualization saving'
    )
    parser.add_argument(
        '--save-interval',
        type=int,
        default=60,
        help='Visualization save interval in seconds (default: 60)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='benchmark_snapshots',
        help='Output directory for visualization snapshots (default: benchmark_snapshots)'
    )
    
    # Logging configuration
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    parser.add_argument(
        '--log-file',
        type=str,
        default='kubebrowse_benchmark.log',
        help='Log file path (default: kubebrowse_benchmark.log)'
    )
    
    return parser.parse_args()

def setup_logging(log_level: str, log_file: str):
    """Setup logging configuration"""
    # Clear existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def validate_kubeconfig(kubeconfig_path: str) -> bool:
    """Validate that the kubeconfig file exists and is readable"""
    if not kubeconfig_path:
        return True
        
    if not os.path.exists(kubeconfig_path):
        logger.error(f"Kubeconfig file not found: {kubeconfig_path}")
        return False
        
    if not os.access(kubeconfig_path, os.R_OK):
        logger.error(f"Kubeconfig file is not readable: {kubeconfig_path}")
        return False
        
    # Try to load and validate the kubeconfig
    try:
        from kubernetes import config as k8s_config
        k8s_config.load_kube_config(config_file=kubeconfig_path, persist_config=False)
        logger.info(f"Kubeconfig validation successful: {kubeconfig_path}")
        return True
    except Exception as e:
        logger.error(f"Invalid kubeconfig file {kubeconfig_path}: {e}")
        return False

def create_config_from_args(args) -> BenchmarkConfig:
    """Create BenchmarkConfig from parsed arguments"""
    # Auto-enable sessions monitoring if API URL is provided
    enable_sessions = args.enable_sessions_monitoring or bool(args.sessions_api_url)
    
    return BenchmarkConfig(
        target_url=args.target_url,
        namespace=args.namespace,
        max_concurrent_users=args.max_users,
        ramp_up_duration=args.ramp_up_duration,
        test_duration=args.test_duration,
        ramp_down_duration=args.ramp_down_duration,
        polling_interval=args.polling_interval,
        websocket_timeout=args.websocket_timeout,
        api_timeout=args.api_timeout,
        save_visualizations=args.save_visualizations,
        save_interval=args.save_interval,
        output_dir=args.output_dir,
        kubeconfig_path=args.kubeconfig,
        sessions_api_url=args.sessions_api_url,
        sessions_api_insecure=args.sessions_api_insecure,
        enable_sessions_monitoring=enable_sessions,
        browser_init_wait=args.browser_init_wait,
        session_start_interval=args.session_start_interval
    )

def main():
    """Main function to run the benchmark"""
    # Set matplotlib backend at the very beginning
    matplotlib.use('Agg')
    plt.ioff()
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Setup logging
    setup_logging(args.log_level, args.log_file)
    
    # Validate kubeconfig if provided
    if args.kubeconfig and not validate_kubeconfig(args.kubeconfig):
        sys.exit(1)
    
    # Create configuration from arguments
    config = create_config_from_args(args)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting KubeBrowse comprehensive benchmark suite...")
    logger.info(f"Configuration: {config}")
    
    if config.kubeconfig_path:
        logger.info(f"Using custom kubeconfig: {config.kubeconfig_path}")
    else:
        logger.info("Using default kubectl context or in-cluster configuration")
    
    if config.enable_sessions_monitoring and config.sessions_api_url:
        logger.info(f"Sessions API monitoring enabled: {config.sessions_api_url}")
        if config.sessions_api_insecure:
            logger.info("Using insecure HTTPS connections for sessions API")
    
    logger.info(f"Browser initialization wait time: {config.browser_init_wait} seconds")
    logger.info(f"Session start interval: {config.session_start_interval} seconds")
    logger.info("Using non-interactive matplotlib backend for thread safety")
    logger.info("Optimized for immediate click simulation with minimal delays")
    
    if config.save_visualizations:
        logger.info(f"Enhanced visualizations will be saved every {config.save_interval} seconds to {config.output_dir}/")
    
    try:
        # Run benchmark
        controller = LoadTestController(config)
        metrics_file = controller.run_benchmark()
        
        # Generate final visualizations
        visualizer = BenchmarkVisualizer(metrics_file)
        visualizer.create_comprehensive_dashboard()
        
        logger.info("Benchmark completed successfully!")
        logger.info("Check the 'benchmark_results' directory for detailed reports and visualizations")
        if config.save_visualizations:
            logger.info(f"Check the '{config.output_dir}' directory for periodic visualization snapshots")
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        raise
    finally:
        # Clean up matplotlib state on exit
        try:
            plt.close('all')
            plt.clf()
        except:
            pass

if __name__ == "__main__":
    main()