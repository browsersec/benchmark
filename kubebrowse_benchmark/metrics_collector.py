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
            'browser_pod_counts': [],  # Browser sandbox pods
            'file_viewer_pod_counts': [],  # File viewer (office) pods
            'hpa_metrics': {},
            'session_metrics': [],
            'websocket_metrics': [],
            'websocket_rtt_summary': [],  # Aggregated WebSocket RTT stats over time
            'api_latency': [],
            'api_sessions': [],  # API sessions data
            'concurrent_users': [],  # Track concurrent users over time
            'etcd_metrics': [],  # etcd cluster metrics
            'pod_distribution': [],  # Pod distribution across nodes
            'sandbox_pod_distribution': [],  # Detailed sandbox pod distribution (browser vs file viewer)
            'pod_type_summary': [],  # Summary of pod types over time
            'latency_by_load': [],  # Latency measurements with concurrent user count
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
                
                # Collect pod counts (total sandbox pods)
                browser_pods = self.k8s_monitor.get_pod_metrics(
                    label_selector="app=browser-sandbox-test"
                )
                running_pods = sum(1 for pod in browser_pods.values() 
                                 if pod['status'] == 'Running')
                self.metrics_data['pod_counts'].append(running_pods)
                
                # Collect detailed sandbox pod distribution (browser vs file viewer)
                sandbox_distribution = self.k8s_monitor.get_sandbox_pod_distribution(
                    label_selector="app=browser-sandbox-test"
                )
                self.metrics_data['sandbox_pod_distribution'].append(sandbox_distribution)
                
                # Collect pod type summary
                pod_type_summary = self.k8s_monitor.get_pod_type_summary(
                    label_selector="app=browser-sandbox-test"
                )
                self.metrics_data['pod_type_summary'].append(pod_type_summary)
                
                # Track browser and file viewer counts separately
                browser_running = pod_type_summary['browser']['running']
                file_viewer_running = pod_type_summary['file_viewer']['running']
                self.metrics_data['browser_pod_counts'].append(browser_running)
                self.metrics_data['file_viewer_pod_counts'].append(file_viewer_running)
                
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
                
                # Collect etcd metrics
                etcd_metrics = self.k8s_monitor.get_etcd_metrics()
                self.metrics_data['etcd_metrics'].append(etcd_metrics)
                
                # Collect pod distribution
                pod_distribution = self.k8s_monitor.get_pod_distribution()
                self.metrics_data['pod_distribution'].append(pod_distribution)
                
                # Calculate concurrent users (active sessions at this timestamp)
                concurrent_users = self._calculate_concurrent_users(timestamp)
                self.metrics_data['concurrent_users'].append(concurrent_users)
                
                # Track latency by load for box plots
                self._update_latency_by_load(concurrent_users)
                
                # Aggregate WebSocket RTT statistics
                self._update_websocket_rtt_summary()
                
                logger.debug(f"Collected metrics at {timestamp}")
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                
            time.sleep(self.config.polling_interval)
    
    def add_session_metrics(self, session_metrics: SessionMetrics):
        """Add session metrics to collection"""
        self.metrics_data['session_metrics'].append(asdict(session_metrics))
    
    def _calculate_concurrent_users(self, timestamp: datetime) -> int:
        """Calculate number of concurrent users at given timestamp"""
        concurrent = 0
        for session in self.metrics_data['session_metrics']:
            try:
                start_time = session.get('start_time')
                end_time = session.get('end_time')
                
                if start_time:
                    if isinstance(start_time, str):
                        start_time = datetime.fromisoformat(start_time)
                    
                    # Session started before or at timestamp
                    if start_time <= timestamp:
                        if end_time:
                            if isinstance(end_time, str):
                                end_time = datetime.fromisoformat(end_time)
                            # Session ended after timestamp
                            if end_time >= timestamp:
                                concurrent += 1
                        else:
                            # Session still running
                            concurrent += 1
            except Exception:
                pass
        
        return concurrent
    
    def _update_latency_by_load(self, concurrent_users: int):
        """Update latency by load data for box plots"""
        # Get recent session metrics with response times
        for session in self.metrics_data['session_metrics']:
            response_time = session.get('first_click_response_time')
            if response_time is not None:
                # Bucket by user load ranges (0-10, 10-25, 25-50, 50-100, 100+)
                if concurrent_users <= 10:
                    load_bucket = '1-10'
                elif concurrent_users <= 25:
                    load_bucket = '11-25'
                elif concurrent_users <= 50:
                    load_bucket = '26-50'
                elif concurrent_users <= 100:
                    load_bucket = '51-100'
                else:
                    load_bucket = '100+'
                
                # Check if this session already has a load bucket assigned
                if 'load_bucket' not in session:
                    session['load_bucket'] = load_bucket
                    self.metrics_data['latency_by_load'].append({
                        'load_bucket': load_bucket,
                        'concurrent_users': concurrent_users,
                        'response_time': response_time,
                        'file_upload_times': session.get('file_upload_times', [])
                    })
    
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
    
    def _update_websocket_rtt_summary(self):
        """Aggregate WebSocket RTT statistics from all sessions"""
        import statistics
        
        all_rtt_samples = []
        total_frames_sent = 0
        total_frames_received = 0
        total_bytes_sent = 0
        total_bytes_received = 0
        sessions_with_rtt = 0
        
        for session in self.metrics_data['session_metrics']:
            rtt_samples = session.get('websocket_rtt_samples', [])
            if rtt_samples:
                all_rtt_samples.extend(rtt_samples)
                sessions_with_rtt += 1
            
            total_frames_sent += session.get('websocket_frames_sent', 0)
            total_frames_received += session.get('websocket_frames_received', 0)
            total_bytes_sent += session.get('websocket_bytes_sent', 0)
            total_bytes_received += session.get('websocket_bytes_received', 0)
        
        # Calculate aggregate statistics
        summary = {
            'timestamp': datetime.now().isoformat(),
            'sessions_with_rtt': sessions_with_rtt,
            'total_samples': len(all_rtt_samples),
            'total_frames_sent': total_frames_sent,
            'total_frames_received': total_frames_received,
            'total_bytes_sent': total_bytes_sent,
            'total_bytes_received': total_bytes_received,
            'rtt_avg_ms': None,
            'rtt_min_ms': None,
            'rtt_max_ms': None,
            'rtt_p50_ms': None,
            'rtt_p95_ms': None,
            'rtt_p99_ms': None,
        }
        
        if all_rtt_samples:
            sorted_samples = sorted(all_rtt_samples)
            n = len(sorted_samples)
            
            def percentile(data, p):
                k = (len(data) - 1) * (p / 100)
                f = int(k)
                c = f + 1 if f + 1 < len(data) else f
                return data[f] + (data[c] - data[f]) * (k - f)
            
            summary['rtt_avg_ms'] = statistics.mean(sorted_samples)
            summary['rtt_min_ms'] = min(sorted_samples)
            summary['rtt_max_ms'] = max(sorted_samples)
            summary['rtt_p50_ms'] = percentile(sorted_samples, 50)
            summary['rtt_p95_ms'] = percentile(sorted_samples, 95)
            summary['rtt_p99_ms'] = percentile(sorted_samples, 99)
        
        self.metrics_data['websocket_rtt_summary'].append(summary)
    
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

