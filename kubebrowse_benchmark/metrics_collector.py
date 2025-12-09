"""
Metrics collection and storage functionality.
"""

import json
import time
import threading
import logging
from datetime import datetime
from dataclasses import asdict

from .config import BenchmarkConfig, SessionMetrics
from .kubernetes_monitor import KubernetesMonitor
from .sessions_monitor import SessionsAPIMonitor

logger = logging.getLogger(__name__)


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

