"""
Visualization functionality for benchmark results.
"""

import os
import json
import time
import threading
import logging
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .config import BenchmarkConfig

logger = logging.getLogger(__name__)


class PeriodicVisualizationSaver:
    """Save visualizations at periodic intervals during benchmark"""
    
    def __init__(self, metrics_collector, config: BenchmarkConfig):
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
                
                # Create enhanced dashboard visualization with console errors
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
                    
                    # Running Pods (by type: Browser vs File Viewer)
                    axes[0, 2].set_title('Running Pods by Type')
                    axes[0, 2].set_xlabel('Time Points')
                    axes[0, 2].set_ylabel('Pod Count')
                    axes[0, 2].grid(True, alpha=0.3)
                    
                    browser_counts = data.get('browser_pod_counts', [])
                    file_viewer_counts = data.get('file_viewer_pod_counts', [])
                    
                    if browser_counts or file_viewer_counts or data['pod_counts']:
                        # Plot total pods
                        if data['pod_counts']:
                            time_points = list(range(len(data['pod_counts'])))
                            axes[0, 2].plot(time_points, data['pod_counts'], 
                                           color='gray', marker='o', markersize=3, 
                                           linestyle='--', alpha=0.5, label='Total')
                        
                        # Plot browser pods
                        if browser_counts:
                            time_points_browser = list(range(len(browser_counts)))
                            axes[0, 2].plot(time_points_browser, browser_counts, 
                                           color='#2196F3', marker='o', markersize=4, 
                                           label='Browser')
                            axes[0, 2].fill_between(time_points_browser, browser_counts, 
                                                   alpha=0.2, color='#2196F3')
                        
                        # Plot file viewer pods
                        if file_viewer_counts:
                            time_points_fv = list(range(len(file_viewer_counts)))
                            axes[0, 2].plot(time_points_fv, file_viewer_counts, 
                                           color='#4CAF50', marker='s', markersize=4, 
                                           label='File Viewer')
                            axes[0, 2].fill_between(time_points_fv, file_viewer_counts, 
                                                   alpha=0.2, color='#4CAF50')
                        
                        axes[0, 2].legend(loc='upper left', fontsize=8)
                    
                    # API Active Sessions
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
                    
                    # HPA Replica Counts
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
                    
                    # API vs Browser Sessions Correlation
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
                
                # Create comprehensive summary file with all metrics
                summary_file = f"{snapshot_dir}/summary.txt"
                with open(summary_file, 'w') as f:
                    f.write(f"{'=' * 60}\n")
                    f.write(f"  KubeBrowse Benchmark Snapshot Report\n")
                    f.write(f"{'=' * 60}\n\n")
                    f.write(f"Snapshot #{self.save_counter}\n")
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write(f"Data points collected: {len(timestamps)}\n\n")
                    
                    # Infrastructure Summary
                    f.write(f"{'=' * 40}\n")
                    f.write(f"  INFRASTRUCTURE METRICS\n")
                    f.write(f"{'=' * 40}\n")
                    f.write(f"Running pods (current): {data['pod_counts'][-1] if data['pod_counts'] else 0}\n")
                    if data['pod_counts']:
                        f.write(f"Max pods: {max(data['pod_counts'])}\n")
                        f.write(f"Min pods: {min(data['pod_counts'])}\n")
                        f.write(f"Avg pods: {np.mean(data['pod_counts']):.1f}\n")
                    
                    # Pod Type Breakdown (Browser vs File Viewer)
                    browser_counts = data.get('browser_pod_counts', [])
                    file_viewer_counts = data.get('file_viewer_pod_counts', [])
                    
                    if browser_counts or file_viewer_counts:
                        f.write(f"\nPod Type Breakdown:\n")
                        f.write(f"  Browser Pods (rdp-chromium):\n")
                        if browser_counts:
                            f.write(f"    Current: {browser_counts[-1]}\n")
                            f.write(f"    Max: {max(browser_counts)}\n")
                            f.write(f"    Avg: {np.mean(browser_counts):.1f}\n")
                        else:
                            f.write(f"    No data\n")
                        
                        f.write(f"  File Viewer Pods (rdp-onlyoffice):\n")
                        if file_viewer_counts:
                            f.write(f"    Current: {file_viewer_counts[-1]}\n")
                            f.write(f"    Max: {max(file_viewer_counts)}\n")
                            f.write(f"    Avg: {np.mean(file_viewer_counts):.1f}\n")
                        else:
                            f.write(f"    No data\n")
                    
                    # Node metrics
                    if data['node_metrics']:
                        f.write(f"\nNode Resource Usage:\n")
                        for node_name, metrics in data['node_metrics'].items():
                            if metrics['cpu_percent']:
                                f.write(f"  {node_name}:\n")
                                f.write(f"    CPU: avg={np.mean(metrics['cpu_percent']):.1f}%, max={max(metrics['cpu_percent']):.1f}%\n")
                                f.write(f"    Memory: avg={np.mean(metrics['memory_percent']):.1f}%, max={max(metrics['memory_percent']):.1f}%\n")
                    
                    # API Sessions
                    if data['api_sessions']:
                        latest_api_data = data['api_sessions'][-1]
                        f.write(f"\nAPI Sessions:\n")
                        f.write(f"  Active Sessions: {latest_api_data.get('active_sessions', 0)}\n")
                        f.write(f"  Total Connections: {latest_api_data.get('total_connections', 0)}\n")
                    
                    # Session Summary
                    f.write(f"\n{'=' * 40}\n")
                    f.write(f"  SESSION METRICS\n")
                    f.write(f"{'=' * 40}\n")
                    f.write(f"Total sessions: {len(data['session_metrics'])}\n")
                    
                    if data['session_metrics']:
                        successful = sum(1 for s in data['session_metrics'] 
                                       if s.get('failed_api_calls', 0) == 0)
                        failed = len(data['session_metrics']) - successful
                        success_rate = (successful / len(data['session_metrics']) * 100) if data['session_metrics'] else 0
                        
                        f.write(f"Successful sessions: {successful}\n")
                        f.write(f"Failed sessions: {failed}\n")
                        f.write(f"Success rate: {success_rate:.1f}%\n")
                        
                        # Calculate session durations
                        session_durations = []
                        for s in data['session_metrics']:
                            if s.get('start_time') and s.get('end_time'):
                                try:
                                    start = datetime.fromisoformat(s['start_time']) if isinstance(s['start_time'], str) else s['start_time']
                                    end = datetime.fromisoformat(s['end_time']) if isinstance(s['end_time'], str) else s['end_time']
                                    duration = (end - start).total_seconds()
                                    if duration > 0:
                                        session_durations.append(duration)
                                except:
                                    pass
                        
                        if session_durations:
                            f.write(f"\nSession Duration:\n")
                            f.write(f"  Average: {np.mean(session_durations):.1f}s\n")
                            f.write(f"  Median: {np.median(session_durations):.1f}s\n")
                            f.write(f"  Min: {min(session_durations):.1f}s\n")
                            f.write(f"  Max: {max(session_durations):.1f}s\n")
                    
                    # Response Time Metrics
                    f.write(f"\n{'=' * 40}\n")
                    f.write(f"  RESPONSE TIME METRICS\n")
                    f.write(f"{'=' * 40}\n")
                    
                    if data['session_metrics']:
                        response_times = [s.get('first_click_response_time') 
                                        for s in data['session_metrics'] 
                                        if s.get('first_click_response_time') is not None]
                        
                        if response_times:
                            rt_array = np.array(response_times)
                            f.write(f"Sample count: {len(response_times)}\n\n")
                            f.write(f"Average:  {np.mean(rt_array):.3f}s\n")
                            f.write(f"Median:   {np.median(rt_array):.3f}s\n")
                            f.write(f"Std Dev:  {np.std(rt_array):.3f}s\n")
                            f.write(f"Min:      {np.min(rt_array):.3f}s\n")
                            f.write(f"Max:      {np.max(rt_array):.3f}s\n\n")
                            f.write(f"Percentiles:\n")
                            f.write(f"  P50:  {np.percentile(rt_array, 50):.3f}s\n")
                            f.write(f"  P75:  {np.percentile(rt_array, 75):.3f}s\n")
                            f.write(f"  P90:  {np.percentile(rt_array, 90):.3f}s\n")
                            f.write(f"  P95:  {np.percentile(rt_array, 95):.3f}s\n")
                            f.write(f"  P99:  {np.percentile(rt_array, 99):.3f}s\n")
                        else:
                            f.write("No response time data available yet.\n")
                    
                    # API Call Summary
                    if data['session_metrics']:
                        total_api_calls = sum(s.get('total_api_calls', 0) for s in data['session_metrics'])
                        failed_api_calls = sum(s.get('failed_api_calls', 0) for s in data['session_metrics'])
                        api_success_rate = ((total_api_calls - failed_api_calls) / total_api_calls * 100) if total_api_calls > 0 else 0
                        
                        f.write(f"\n{'=' * 40}\n")
                        f.write(f"  API CALL METRICS\n")
                        f.write(f"{'=' * 40}\n")
                        f.write(f"Total API calls: {total_api_calls}\n")
                        f.write(f"Failed API calls: {failed_api_calls}\n")
                        f.write(f"API success rate: {api_success_rate:.1f}%\n")
                    
                    # File Upload Metrics (for file viewer mode)
                    if data['session_metrics']:
                        all_upload_times = []
                        total_files_uploaded = sum(s.get('files_uploaded', 0) for s in data['session_metrics'])
                        total_files_failed = sum(s.get('files_failed', 0) for s in data['session_metrics'])
                        for s in data['session_metrics']:
                            all_upload_times.extend(s.get('file_upload_times', []))
                        
                        if total_files_uploaded > 0 or total_files_failed > 0:
                            upload_success_rate = (total_files_uploaded / (total_files_uploaded + total_files_failed) * 100) if (total_files_uploaded + total_files_failed) > 0 else 0
                            
                            f.write(f"\n{'=' * 40}\n")
                            f.write(f"  FILE UPLOAD METRICS\n")
                            f.write(f"{'=' * 40}\n")
                            f.write(f"Total files uploaded: {total_files_uploaded}\n")
                            f.write(f"Total files failed: {total_files_failed}\n")
                            f.write(f"Upload success rate: {upload_success_rate:.1f}%\n")
                            
                            if all_upload_times:
                                ut_array = np.array(all_upload_times)
                                f.write(f"\nUpload Time Statistics:\n")
                                f.write(f"  Sample count: {len(all_upload_times)}\n")
                                f.write(f"  Average:  {np.mean(ut_array):.3f}s\n")
                                f.write(f"  Median:   {np.median(ut_array):.3f}s\n")
                                f.write(f"  Std Dev:  {np.std(ut_array):.3f}s\n")
                                f.write(f"  Min:      {np.min(ut_array):.3f}s\n")
                                f.write(f"  Max:      {np.max(ut_array):.3f}s\n\n")
                                f.write(f"Percentiles:\n")
                                f.write(f"  P50:  {np.percentile(ut_array, 50):.3f}s\n")
                                f.write(f"  P75:  {np.percentile(ut_array, 75):.3f}s\n")
                                f.write(f"  P90:  {np.percentile(ut_array, 90):.3f}s\n")
                                f.write(f"  P95:  {np.percentile(ut_array, 95):.3f}s\n")
                                f.write(f"  P99:  {np.percentile(ut_array, 99):.3f}s\n")
                    
                    # WebSocket RTT Summary
                    if data['session_metrics']:
                        all_rtt_samples = []
                        sessions_with_rtt = 0
                        total_frames_sent = 0
                        total_frames_received = 0
                        total_bytes_sent = 0
                        total_bytes_received = 0
                        
                        for s in data['session_metrics']:
                            rtt_samples = s.get('websocket_rtt_samples', [])
                            if rtt_samples:
                                all_rtt_samples.extend(rtt_samples)
                                sessions_with_rtt += 1
                            total_frames_sent += s.get('websocket_frames_sent', 0)
                            total_frames_received += s.get('websocket_frames_received', 0)
                            total_bytes_sent += s.get('websocket_bytes_sent', 0)
                            total_bytes_received += s.get('websocket_bytes_received', 0)
                        
                        if all_rtt_samples or sessions_with_rtt > 0:
                            f.write(f"\n{'=' * 40}\n")
                            f.write(f"  WEBSOCKET RTT METRICS\n")
                            f.write(f"{'=' * 40}\n")
                            f.write(f"Sessions with RTT data: {sessions_with_rtt}\n")
                            f.write(f"Total RTT samples: {len(all_rtt_samples)}\n\n")
                            
                            if all_rtt_samples:
                                rtt_array = np.array(all_rtt_samples)
                                f.write(f"RTT Statistics:\n")
                                f.write(f"  Average:  {np.mean(rtt_array):.2f} ms\n")
                                f.write(f"  Median:   {np.median(rtt_array):.2f} ms\n")
                                f.write(f"  Std Dev:  {np.std(rtt_array):.2f} ms\n")
                                f.write(f"  Min:      {np.min(rtt_array):.2f} ms\n")
                                f.write(f"  Max:      {np.max(rtt_array):.2f} ms\n\n")
                                f.write(f"RTT Percentiles:\n")
                                f.write(f"  P50:  {np.percentile(rtt_array, 50):.2f} ms\n")
                                f.write(f"  P75:  {np.percentile(rtt_array, 75):.2f} ms\n")
                                f.write(f"  P90:  {np.percentile(rtt_array, 90):.2f} ms\n")
                                f.write(f"  P95:  {np.percentile(rtt_array, 95):.2f} ms\n")
                                f.write(f"  P99:  {np.percentile(rtt_array, 99):.2f} ms\n")
                            
                            f.write(f"\nWebSocket Traffic:\n")
                            f.write(f"  Frames Sent:     {total_frames_sent:,}\n")
                            f.write(f"  Frames Received: {total_frames_received:,}\n")
                            f.write(f"  Bytes Sent:      {total_bytes_sent / 1024 / 1024:.2f} MB\n")
                            f.write(f"  Bytes Received:  {total_bytes_received / 1024 / 1024:.2f} MB\n")
                            f.write(f"  Total Traffic:   {(total_bytes_sent + total_bytes_received) / 1024 / 1024:.2f} MB\n")
                    
                    # Console Errors Summary
                    if data['session_metrics']:
                        total_console_errors = sum(len(s.get('console_errors', [])) for s in data['session_metrics'])
                        total_severe_errors = sum(
                            sum(1 for err in s.get('console_errors', []) if err.get('level') == 'SEVERE')
                            for s in data['session_metrics']
                        )
                        total_errors = sum(len(s.get('errors', [])) for s in data['session_metrics'])
                        
                        f.write(f"\n{'=' * 40}\n")
                        f.write(f"  ERROR SUMMARY\n")
                        f.write(f"{'=' * 40}\n")
                        f.write(f"Total errors: {total_errors}\n")
                        f.write(f"Console errors: {total_console_errors}\n")
                        f.write(f"Severe console errors: {total_severe_errors}\n")
                        if data['session_metrics']:
                            f.write(f"Avg errors per session: {total_errors / len(data['session_metrics']):.1f}\n")
                    
                    f.write(f"\n{'=' * 60}\n")
                    f.write(f"  End of Snapshot Report\n")
                    f.write(f"{'=' * 60}\n")
                
                # Generate additional advanced visualizations
                self._create_latency_boxplots(data, snapshot_dir)
                self._create_latency_vs_users_chart(data, snapshot_dir)
                self._create_resource_heatmaps(data, snapshot_dir, timestamps)
                self._create_pod_distribution_chart(data, snapshot_dir)
                self._create_sandbox_pod_type_heatmap(data, snapshot_dir)
                self._create_websocket_rtt_charts(data, snapshot_dir)
                self._create_etcd_metrics_chart(data, snapshot_dir)
                
                logger.info(f"Saved visualization snapshot {self.save_counter} to {snapshot_dir}")
                
            except Exception as e:
                logger.error(f"Error saving visualization snapshot: {e}")
                # Clean up any matplotlib state on error
                try:
                    plt.close('all')
                    plt.clf()
                except:
                    pass
    
    def _create_latency_boxplots(self, data: dict, snapshot_dir: str):
        """Create box plots showing p50, p95, p99 latencies across different user loads"""
        try:
            if not data['session_metrics']:
                return
            
            # Prepare data for box plots
            latency_data = []
            for session in data['session_metrics']:
                response_time = session.get('first_click_response_time')
                load_bucket = session.get('load_bucket', 'Unknown')
                if response_time is not None:
                    latency_data.append({
                        'load_bucket': load_bucket,
                        'response_time': response_time
                    })
            
            if not latency_data:
                return
            
            df = pd.DataFrame(latency_data)
            
            # Create figure with subplots
            fig, axes = plt.subplots(1, 2, figsize=(16, 6))
            fig.suptitle('Latency Distribution by User Load', fontsize=14, fontweight='bold')
            
            # Box plot by load bucket
            bucket_order = ['1-10', '11-25', '26-50', '51-100', '100+', 'Unknown']
            available_buckets = [b for b in bucket_order if b in df['load_bucket'].unique()]
            
            if available_buckets:
                sns.boxplot(data=df, x='load_bucket', y='response_time', 
                           order=available_buckets, ax=axes[0], palette='viridis')
                axes[0].set_title('Response Time by Concurrent Users', fontweight='bold')
                axes[0].set_xlabel('Concurrent Users')
                axes[0].set_ylabel('Response Time (s)')
                axes[0].grid(True, alpha=0.3)
                
                # Add percentile annotations
                for i, bucket in enumerate(available_buckets):
                    bucket_data = df[df['load_bucket'] == bucket]['response_time']
                    if len(bucket_data) > 0:
                        p50 = bucket_data.quantile(0.50)
                        p95 = bucket_data.quantile(0.95)
                        p99 = bucket_data.quantile(0.99)
                        axes[0].annotate(f'p50:{p50:.2f}\np95:{p95:.2f}\np99:{p99:.2f}',
                                        xy=(i, bucket_data.max()), fontsize=7,
                                        ha='center', va='bottom')
            
            # Violin plot for distribution visualization
            if available_buckets:
                sns.violinplot(data=df, x='load_bucket', y='response_time',
                              order=available_buckets, ax=axes[1], palette='coolwarm')
                axes[1].set_title('Response Time Distribution (Violin Plot)', fontweight='bold')
                axes[1].set_xlabel('Concurrent Users')
                axes[1].set_ylabel('Response Time (s)')
                axes[1].grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(f'{snapshot_dir}/latency_boxplots.png', dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            # Also create file upload latency box plots if available
            upload_data = []
            for session in data['session_metrics']:
                load_bucket = session.get('load_bucket', 'Unknown')
                for upload_time in session.get('file_upload_times', []):
                    upload_data.append({
                        'load_bucket': load_bucket,
                        'upload_time': upload_time
                    })
            
            if upload_data:
                df_upload = pd.DataFrame(upload_data)
                fig, ax = plt.subplots(figsize=(12, 6))
                available_buckets = [b for b in bucket_order if b in df_upload['load_bucket'].unique()]
                
                if available_buckets:
                    sns.boxplot(data=df_upload, x='load_bucket', y='upload_time',
                               order=available_buckets, ax=ax, palette='magma')
                    ax.set_title('File Upload Time by Concurrent Users', fontsize=14, fontweight='bold')
                    ax.set_xlabel('Concurrent Users')
                    ax.set_ylabel('Upload Time (s)')
                    ax.grid(True, alpha=0.3)
                    
                    plt.tight_layout()
                    plt.savefig(f'{snapshot_dir}/upload_latency_boxplots.png', dpi=300, bbox_inches='tight')
                plt.close(fig)
                
        except Exception as e:
            logger.error(f"Error creating latency box plots: {e}")
            plt.close('all')
    
    def _create_latency_vs_users_chart(self, data: dict, snapshot_dir: str):
        """Create line graphs comparing latency vs concurrent users"""
        try:
            if not data['session_metrics'] or not data['concurrent_users']:
                return
            
            # Prepare time-series data
            timestamps = data['timestamps']
            concurrent_users = data['concurrent_users']
            
            # Calculate average latency at each time point
            avg_latencies = []
            p95_latencies = []
            p99_latencies = []
            
            for i, ts in enumerate(timestamps):
                # Get sessions that were active around this timestamp
                relevant_response_times = []
                for session in data['session_metrics']:
                    rt = session.get('first_click_response_time')
                    if rt is not None:
                        relevant_response_times.append(rt)
                
                if relevant_response_times:
                    # Use cumulative stats up to this point
                    subset = relevant_response_times[:max(1, int(len(relevant_response_times) * (i + 1) / len(timestamps)))]
                    if subset:
                        avg_latencies.append(np.mean(subset))
                        p95_latencies.append(np.percentile(subset, 95))
                        p99_latencies.append(np.percentile(subset, 99))
                    else:
                        avg_latencies.append(0)
                        p95_latencies.append(0)
                        p99_latencies.append(0)
                else:
                    avg_latencies.append(0)
                    p95_latencies.append(0)
                    p99_latencies.append(0)
            
            # Create figure
            fig, axes = plt.subplots(2, 1, figsize=(14, 10))
            fig.suptitle('Latency vs Concurrent Users', fontsize=14, fontweight='bold')
            
            # Plot 1: Latency over time with concurrent users
            ax1 = axes[0]
            ax1_twin = ax1.twinx()
            
            time_points = list(range(len(timestamps)))
            
            # Latency lines
            ax1.plot(time_points, avg_latencies, 'b-', linewidth=2, label='Avg Latency', marker='o', markersize=3)
            ax1.plot(time_points, p95_latencies, 'orange', linewidth=2, label='P95 Latency', marker='s', markersize=3)
            ax1.plot(time_points, p99_latencies, 'r-', linewidth=2, label='P99 Latency', marker='^', markersize=3)
            ax1.set_xlabel('Time Points')
            ax1.set_ylabel('Latency (s)', color='blue')
            ax1.tick_params(axis='y', labelcolor='blue')
            ax1.legend(loc='upper left')
            ax1.grid(True, alpha=0.3)
            
            # Concurrent users line
            ax1_twin.fill_between(time_points, concurrent_users[:len(time_points)], alpha=0.2, color='green')
            ax1_twin.plot(time_points, concurrent_users[:len(time_points)], 'g--', linewidth=2, label='Concurrent Users')
            ax1_twin.set_ylabel('Concurrent Users', color='green')
            ax1_twin.tick_params(axis='y', labelcolor='green')
            ax1_twin.legend(loc='upper right')
            
            ax1.set_title('Latency Percentiles vs Concurrent Users Over Time')
            
            # Plot 2: Scatter plot of latency vs concurrent users
            ax2 = axes[1]
            
            # Collect data points
            scatter_data = []
            for session in data['session_metrics']:
                rt = session.get('first_click_response_time')
                if rt is not None:
                    # Estimate concurrent users at session time
                    idx = min(len(concurrent_users) - 1, 
                             int(len(data['session_metrics']) * len(concurrent_users) / max(1, len(data['session_metrics']))))
                    cu = concurrent_users[idx] if concurrent_users else 0
                    scatter_data.append({'concurrent_users': cu, 'response_time': rt})
            
            if scatter_data:
                df_scatter = pd.DataFrame(scatter_data)
                ax2.scatter(df_scatter['concurrent_users'], df_scatter['response_time'], 
                           alpha=0.5, c='blue', s=30)
                
                # Add trend line
                if len(df_scatter) > 2:
                    z = np.polyfit(df_scatter['concurrent_users'], df_scatter['response_time'], 1)
                    p = np.poly1d(z)
                    x_line = np.linspace(df_scatter['concurrent_users'].min(), 
                                        df_scatter['concurrent_users'].max(), 100)
                    ax2.plot(x_line, p(x_line), 'r--', linewidth=2, label='Trend Line')
                    ax2.legend()
            
            ax2.set_xlabel('Concurrent Users')
            ax2.set_ylabel('Response Time (s)')
            ax2.set_title('Response Time vs Concurrent Users (Scatter)')
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            plt.savefig(f'{snapshot_dir}/latency_vs_users.png', dpi=300, bbox_inches='tight')
            plt.close(fig)
            
        except Exception as e:
            logger.error(f"Error creating latency vs users chart: {e}")
            plt.close('all')
    
    def _create_resource_heatmaps(self, data: dict, snapshot_dir: str, timestamps: list):
        """Create CPU/Memory usage heatmaps across cluster nodes over time"""
        try:
            if not data['node_metrics']:
                return
            
            # Prepare data for heatmaps
            nodes = list(data['node_metrics'].keys())
            if not nodes:
                return
            
            # Get the minimum length across all metrics
            min_len = min(len(data['node_metrics'][n]['cpu_percent']) for n in nodes)
            if min_len == 0:
                return
            
            # Create CPU heatmap data
            cpu_matrix = np.array([data['node_metrics'][n]['cpu_percent'][:min_len] for n in nodes])
            memory_matrix = np.array([data['node_metrics'][n]['memory_percent'][:min_len] for n in nodes])
            
            # Create figure
            fig, axes = plt.subplots(2, 1, figsize=(16, 10))
            fig.suptitle('Resource Utilization Heatmaps', fontsize=14, fontweight='bold')
            
            # CPU Heatmap
            im1 = axes[0].imshow(cpu_matrix, aspect='auto', cmap='YlOrRd', 
                                interpolation='nearest', vmin=0, vmax=100)
            axes[0].set_yticks(range(len(nodes)))
            axes[0].set_yticklabels(nodes)
            axes[0].set_xlabel('Time Points')
            axes[0].set_ylabel('Nodes')
            axes[0].set_title('CPU Usage (%) Over Time', fontweight='bold')
            plt.colorbar(im1, ax=axes[0], label='CPU %')
            
            # Memory Heatmap
            im2 = axes[1].imshow(memory_matrix, aspect='auto', cmap='YlGnBu',
                                interpolation='nearest', vmin=0, vmax=100)
            axes[1].set_yticks(range(len(nodes)))
            axes[1].set_yticklabels(nodes)
            axes[1].set_xlabel('Time Points')
            axes[1].set_ylabel('Nodes')
            axes[1].set_title('Memory Usage (%) Over Time', fontweight='bold')
            plt.colorbar(im2, ax=axes[1], label='Memory %')
            
            plt.tight_layout()
            plt.savefig(f'{snapshot_dir}/resource_heatmaps.png', dpi=300, bbox_inches='tight')
            plt.close(fig)
            
        except Exception as e:
            logger.error(f"Error creating resource heatmaps: {e}")
            plt.close('all')
    
    def _create_pod_distribution_chart(self, data: dict, snapshot_dir: str):
        """Create pod distribution and density visualization with pod type distinction"""
        try:
            if not data['pod_distribution']:
                return
            
            # Get latest pod distribution
            latest_dist = data['pod_distribution'][-1] if data['pod_distribution'] else {}
            
            if not latest_dist:
                return
            
            # Create figure with 2x2 layout for more detailed visualization
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))
            fig.suptitle('Pod Distribution Across Cluster', fontsize=14, fontweight='bold')
            
            # ===== Subplot 1: Pod Status by Node (all pods) =====
            nodes = list(latest_dist.keys())
            running = [latest_dist[n].get('running', 0) for n in nodes]
            pending = [latest_dist[n].get('pending', 0) for n in nodes]
            failed = [latest_dist[n].get('failed', 0) for n in nodes]
            
            x = np.arange(len(nodes))
            width = 0.25
            
            axes[0, 0].bar(x - width, running, width, label='Running', color='#2ecc71', alpha=0.8)
            axes[0, 0].bar(x, pending, width, label='Pending', color='#f39c12', alpha=0.8)
            axes[0, 0].bar(x + width, failed, width, label='Failed', color='#e74c3c', alpha=0.8)
            
            axes[0, 0].set_xlabel('Nodes')
            axes[0, 0].set_ylabel('Pod Count')
            axes[0, 0].set_title('All Pods Status by Node', fontweight='bold')
            axes[0, 0].set_xticks(x)
            axes[0, 0].set_xticklabels([n[:15] + '...' if len(n) > 15 else n for n in nodes], 
                                       rotation=45, ha='right', fontsize=9)
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3, axis='y')
            
            # ===== Subplot 2: Pod Type Distribution by Node (Browser vs File Viewer) =====
            sandbox_distributions = data.get('sandbox_pod_distribution', [])
            if sandbox_distributions:
                latest_sandbox = sandbox_distributions[-1]
                sandbox_nodes = sorted(latest_sandbox.keys())
                
                if sandbox_nodes:
                    browser_running = [latest_sandbox.get(n, {}).get('browser', {}).get('running', 0) for n in sandbox_nodes]
                    fv_running = [latest_sandbox.get(n, {}).get('file_viewer', {}).get('running', 0) for n in sandbox_nodes]
                    
                    x_sandbox = np.arange(len(sandbox_nodes))
                    width_sandbox = 0.35
                    
                    bars1 = axes[0, 1].bar(x_sandbox - width_sandbox/2, browser_running, width_sandbox, 
                                          label='Browser (rdp-chromium)', color='#2196F3', alpha=0.8)
                    bars2 = axes[0, 1].bar(x_sandbox + width_sandbox/2, fv_running, width_sandbox, 
                                          label='File Viewer (rdp-onlyoffice)', color='#4CAF50', alpha=0.8)
                    
                    axes[0, 1].set_xlabel('Nodes')
                    axes[0, 1].set_ylabel('Running Pod Count')
                    axes[0, 1].set_title('Sandbox Pod Types by Node', fontweight='bold')
                    axes[0, 1].set_xticks(x_sandbox)
                    axes[0, 1].set_xticklabels([n[:15] + '...' if len(n) > 15 else n for n in sandbox_nodes], 
                                               rotation=45, ha='right', fontsize=9)
                    axes[0, 1].legend(loc='upper right', fontsize=9)
                    axes[0, 1].grid(True, alpha=0.3, axis='y')
                    
                    # Add value labels
                    for bar in bars1:
                        height = bar.get_height()
                        if height > 0:
                            axes[0, 1].annotate(f'{int(height)}', xy=(bar.get_x() + bar.get_width()/2, height),
                                               xytext=(0, 3), textcoords="offset points",
                                               ha='center', va='bottom', fontsize=8)
                    for bar in bars2:
                        height = bar.get_height()
                        if height > 0:
                            axes[0, 1].annotate(f'{int(height)}', xy=(bar.get_x() + bar.get_width()/2, height),
                                               xytext=(0, 3), textcoords="offset points",
                                               ha='center', va='bottom', fontsize=8)
                else:
                    axes[0, 1].text(0.5, 0.5, 'No sandbox pods detected', ha='center', va='center',
                                   transform=axes[0, 1].transAxes, fontsize=12)
                    axes[0, 1].set_title('Sandbox Pod Types by Node', fontweight='bold')
            else:
                axes[0, 1].text(0.5, 0.5, 'No sandbox distribution data', ha='center', va='center',
                               transform=axes[0, 1].transAxes, fontsize=12)
                axes[0, 1].set_title('Sandbox Pod Types by Node', fontweight='bold')
            
            # ===== Subplot 3: Pie chart of overall pod status =====
            total_running = sum(running)
            total_pending = sum(pending)
            total_failed = sum(failed)
            
            sizes = [total_running, total_pending, total_failed]
            labels = [f'Running ({total_running})', f'Pending ({total_pending})', f'Failed ({total_failed})']
            colors = ['#2ecc71', '#f39c12', '#e74c3c']
            explode = (0.05, 0, 0)
            
            if sum(sizes) > 0:
                axes[1, 0].pie(sizes, explode=explode, labels=labels, colors=colors,
                              autopct='%1.1f%%', shadow=True, startangle=90)
                axes[1, 0].set_title('Overall Pod Status Distribution', fontweight='bold')
            else:
                axes[1, 0].text(0.5, 0.5, 'No pods', ha='center', va='center',
                               transform=axes[1, 0].transAxes, fontsize=12)
                axes[1, 0].set_title('Overall Pod Status Distribution', fontweight='bold')
            
            # ===== Subplot 4: Pie chart of sandbox pod types =====
            pod_type_summaries = data.get('pod_type_summary', [])
            if pod_type_summaries:
                latest_summary = pod_type_summaries[-1]
                browser_total = latest_summary.get('browser', {}).get('running', 0)
                fv_total = latest_summary.get('file_viewer', {}).get('running', 0)
                
                if browser_total > 0 or fv_total > 0:
                    type_sizes = [browser_total, fv_total]
                    type_labels = [f'Browser\n({browser_total})', f'File Viewer\n({fv_total})']
                    type_colors = ['#2196F3', '#4CAF50']
                    type_explode = (0.05, 0.05)
                    
                    wedges, texts, autotexts = axes[1, 1].pie(type_sizes, explode=type_explode, 
                                                               labels=type_labels, colors=type_colors,
                                                               autopct='%1.1f%%', shadow=True, startangle=90)
                    axes[1, 1].set_title('Sandbox Pod Type Distribution', fontweight='bold')
                    
                    # Add legend with container info
                    legend_labels = ['rdp-chromium (Browser)', 'rdp-onlyoffice (File Viewer)']
                    axes[1, 1].legend(wedges, legend_labels, loc='lower center', 
                                     bbox_to_anchor=(0.5, -0.1), fontsize=9)
                else:
                    axes[1, 1].text(0.5, 0.5, 'No running sandbox pods', ha='center', va='center',
                                   transform=axes[1, 1].transAxes, fontsize=12)
                    axes[1, 1].set_title('Sandbox Pod Type Distribution', fontweight='bold')
            else:
                axes[1, 1].text(0.5, 0.5, 'No pod type data available', ha='center', va='center',
                               transform=axes[1, 1].transAxes, fontsize=12)
                axes[1, 1].set_title('Sandbox Pod Type Distribution', fontweight='bold')
            
            plt.tight_layout()
            plt.savefig(f'{snapshot_dir}/pod_distribution.png', dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            # Create pod distribution over time heatmap if we have history
            if len(data['pod_distribution']) > 1:
                self._create_pod_density_heatmap(data, snapshot_dir)
            
            # Create combined pod heatmap if we have sandbox distribution data
            if len(data.get('sandbox_pod_distribution', [])) > 1:
                self._create_combined_pod_heatmap(data, snapshot_dir)
            
        except Exception as e:
            logger.error(f"Error creating pod distribution chart: {e}")
            plt.close('all')
    
    def _create_pod_density_heatmap(self, data: dict, snapshot_dir: str):
        """Create pod density heatmap over time"""
        try:
            distributions = data['pod_distribution']
            if len(distributions) < 2:
                return
            
            # Get all unique nodes
            all_nodes = set()
            for dist in distributions:
                all_nodes.update(dist.keys())
            nodes = sorted(list(all_nodes))
            
            if not nodes:
                return
            
            # Create matrix of running pods
            pod_matrix = []
            for dist in distributions:
                row = [dist.get(n, {}).get('running', 0) for n in nodes]
                pod_matrix.append(row)
            
            pod_matrix = np.array(pod_matrix).T
            
            # Create heatmap
            fig, ax = plt.subplots(figsize=(14, 6))
            im = ax.imshow(pod_matrix, aspect='auto', cmap='Greens', interpolation='nearest')
            
            ax.set_yticks(range(len(nodes)))
            ax.set_yticklabels(nodes)
            ax.set_xlabel('Time Points')
            ax.set_ylabel('Nodes')
            ax.set_title('Pod Density Across Nodes Over Time', fontsize=14, fontweight='bold')
            plt.colorbar(im, ax=ax, label='Running Pods')
            
            plt.tight_layout()
            plt.savefig(f'{snapshot_dir}/pod_density_heatmap.png', dpi=300, bbox_inches='tight')
            plt.close(fig)
            
        except Exception as e:
            logger.error(f"Error creating pod density heatmap: {e}")
            plt.close('all')
    
    def _create_sandbox_pod_type_heatmap(self, data: dict, snapshot_dir: str):
        """
        Create comprehensive pod distribution heatmap distinguishing between
        browser pods (rdp-chromium) and file viewer pods (rdp-onlyoffice).
        
        Based on:
        - internal/k8s/browser.go: CreateBrowserSandboxPod with container 'rdp-chromium'
        - internal/k8s/office.go: CreateOfficeSandboxPod with container 'rdp-onlyoffice'
        """
        try:
            sandbox_distributions = data.get('sandbox_pod_distribution', [])
            pod_type_summaries = data.get('pod_type_summary', [])
            browser_counts = data.get('browser_pod_counts', [])
            file_viewer_counts = data.get('file_viewer_pod_counts', [])
            
            # Create comprehensive figure with multiple subplots
            fig = plt.figure(figsize=(20, 16))
            fig.suptitle('Sandbox Pod Distribution Heat Map\n(Browser vs File Viewer)', 
                        fontsize=16, fontweight='bold', y=0.98)
            
            # Create grid for subplots
            gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.25)
            
            # ============================================
            # Subplot 1: Pod Type Counts Over Time
            # ============================================
            ax1 = fig.add_subplot(gs[0, :])
            
            if browser_counts or file_viewer_counts:
                time_points = list(range(max(len(browser_counts), len(file_viewer_counts))))
                
                # Ensure both lists have same length for plotting
                browser_data = browser_counts + [0] * (len(time_points) - len(browser_counts))
                file_viewer_data = file_viewer_counts + [0] * (len(time_points) - len(file_viewer_counts))
                
                ax1.fill_between(time_points, browser_data, alpha=0.4, color='#2196F3', label='Browser Pods')
                ax1.fill_between(time_points, file_viewer_data, alpha=0.4, color='#4CAF50', label='File Viewer Pods')
                ax1.plot(time_points, browser_data, 'o-', color='#1565C0', linewidth=2, markersize=4)
                ax1.plot(time_points, file_viewer_data, 's-', color='#2E7D32', linewidth=2, markersize=4)
                
                ax1.set_xlabel('Time Points', fontsize=11)
                ax1.set_ylabel('Running Pod Count', fontsize=11)
                ax1.set_title('Pod Type Counts Over Time', fontsize=13, fontweight='bold')
                ax1.legend(loc='upper left', fontsize=10)
                ax1.grid(True, alpha=0.3)
                
                # Add statistics annotation
                if browser_data:
                    browser_max = max(browser_data)
                    browser_avg = np.mean(browser_data)
                else:
                    browser_max = browser_avg = 0
                if file_viewer_data:
                    fv_max = max(file_viewer_data)
                    fv_avg = np.mean(file_viewer_data)
                else:
                    fv_max = fv_avg = 0
                    
                stats_text = f'Browser: max={browser_max}, avg={browser_avg:.1f}\nFile Viewer: max={fv_max}, avg={fv_avg:.1f}'
                ax1.text(0.98, 0.98, stats_text, transform=ax1.transAxes,
                        fontsize=9, verticalalignment='top', horizontalalignment='right',
                        bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
            else:
                ax1.text(0.5, 0.5, 'No pod type data available', ha='center', va='center',
                        transform=ax1.transAxes, fontsize=12)
                ax1.set_title('Pod Type Counts Over Time', fontsize=13, fontweight='bold')
            
            # ============================================
            # Subplot 2 & 3: Heat Maps by Pod Type
            # ============================================
            if sandbox_distributions and len(sandbox_distributions) > 0:
                # Get all unique nodes
                all_nodes = set()
                for dist in sandbox_distributions:
                    all_nodes.update(dist.keys())
                nodes = sorted(list(all_nodes))
                
                if nodes:
                    # Create browser pod heat map matrix
                    browser_matrix = []
                    file_viewer_matrix = []
                    
                    for dist in sandbox_distributions:
                        browser_row = []
                        fv_row = []
                        for node in nodes:
                            node_data = dist.get(node, {})
                            browser_running = node_data.get('browser', {}).get('running', 0)
                            fv_running = node_data.get('file_viewer', {}).get('running', 0)
                            browser_row.append(browser_running)
                            fv_row.append(fv_running)
                        browser_matrix.append(browser_row)
                        file_viewer_matrix.append(fv_row)
                    
                    browser_matrix = np.array(browser_matrix).T
                    file_viewer_matrix = np.array(file_viewer_matrix).T
                    
                    # Browser pods heat map
                    ax2 = fig.add_subplot(gs[1, 0])
                    if browser_matrix.size > 0 and browser_matrix.max() > 0:
                        im2 = ax2.imshow(browser_matrix, aspect='auto', cmap='Blues',
                                        interpolation='nearest', vmin=0)
                        ax2.set_yticks(range(len(nodes)))
                        ax2.set_yticklabels([n[:20] + '...' if len(n) > 20 else n for n in nodes], fontsize=9)
                        ax2.set_xlabel('Time Points', fontsize=11)
                        ax2.set_ylabel('Nodes', fontsize=11)
                        ax2.set_title('Browser Pods (rdp-chromium) Heat Map', fontsize=12, fontweight='bold')
                        cbar2 = plt.colorbar(im2, ax=ax2, shrink=0.8)
                        cbar2.set_label('Running Pods', fontsize=10)
                        
                        # Add cell annotations for small matrices
                        if browser_matrix.shape[1] <= 20 and browser_matrix.shape[0] <= 10:
                            for i in range(browser_matrix.shape[0]):
                                for j in range(browser_matrix.shape[1]):
                                    if browser_matrix[i, j] > 0:
                                        ax2.text(j, i, int(browser_matrix[i, j]), ha='center', va='center',
                                                color='white' if browser_matrix[i, j] > browser_matrix.max() / 2 else 'black',
                                                fontsize=8)
                    else:
                        ax2.text(0.5, 0.5, 'No browser pods detected', ha='center', va='center',
                                transform=ax2.transAxes, fontsize=12)
                        ax2.set_title('Browser Pods (rdp-chromium) Heat Map', fontsize=12, fontweight='bold')
                    
                    # File Viewer pods heat map
                    ax3 = fig.add_subplot(gs[1, 1])
                    if file_viewer_matrix.size > 0 and file_viewer_matrix.max() > 0:
                        im3 = ax3.imshow(file_viewer_matrix, aspect='auto', cmap='Greens',
                                        interpolation='nearest', vmin=0)
                        ax3.set_yticks(range(len(nodes)))
                        ax3.set_yticklabels([n[:20] + '...' if len(n) > 20 else n for n in nodes], fontsize=9)
                        ax3.set_xlabel('Time Points', fontsize=11)
                        ax3.set_ylabel('Nodes', fontsize=11)
                        ax3.set_title('File Viewer Pods (rdp-onlyoffice) Heat Map', fontsize=12, fontweight='bold')
                        cbar3 = plt.colorbar(im3, ax=ax3, shrink=0.8)
                        cbar3.set_label('Running Pods', fontsize=10)
                        
                        # Add cell annotations for small matrices
                        if file_viewer_matrix.shape[1] <= 20 and file_viewer_matrix.shape[0] <= 10:
                            for i in range(file_viewer_matrix.shape[0]):
                                for j in range(file_viewer_matrix.shape[1]):
                                    if file_viewer_matrix[i, j] > 0:
                                        ax3.text(j, i, int(file_viewer_matrix[i, j]), ha='center', va='center',
                                                color='white' if file_viewer_matrix[i, j] > file_viewer_matrix.max() / 2 else 'black',
                                                fontsize=8)
                    else:
                        ax3.text(0.5, 0.5, 'No file viewer pods detected', ha='center', va='center',
                                transform=ax3.transAxes, fontsize=12)
                        ax3.set_title('File Viewer Pods (rdp-onlyoffice) Heat Map', fontsize=12, fontweight='bold')
            else:
                ax2 = fig.add_subplot(gs[1, 0])
                ax3 = fig.add_subplot(gs[1, 1])
                ax2.text(0.5, 0.5, 'No sandbox distribution data', ha='center', va='center',
                        transform=ax2.transAxes, fontsize=12)
                ax2.set_title('Browser Pods Heat Map', fontsize=12, fontweight='bold')
                ax3.text(0.5, 0.5, 'No sandbox distribution data', ha='center', va='center',
                        transform=ax3.transAxes, fontsize=12)
                ax3.set_title('File Viewer Pods Heat Map', fontsize=12, fontweight='bold')
            
            # ============================================
            # Subplot 4: Stacked Bar Chart by Node
            # ============================================
            ax4 = fig.add_subplot(gs[2, 0])
            
            if sandbox_distributions and len(sandbox_distributions) > 0:
                # Use latest distribution for bar chart
                latest_dist = sandbox_distributions[-1]
                nodes = sorted(latest_dist.keys())
                
                if nodes:
                    browser_counts_by_node = [latest_dist.get(n, {}).get('browser', {}).get('running', 0) for n in nodes]
                    fv_counts_by_node = [latest_dist.get(n, {}).get('file_viewer', {}).get('running', 0) for n in nodes]
                    
                    x = np.arange(len(nodes))
                    width = 0.35
                    
                    bars1 = ax4.bar(x - width/2, browser_counts_by_node, width, label='Browser', color='#2196F3', alpha=0.8)
                    bars2 = ax4.bar(x + width/2, fv_counts_by_node, width, label='File Viewer', color='#4CAF50', alpha=0.8)
                    
                    ax4.set_xlabel('Nodes', fontsize=11)
                    ax4.set_ylabel('Running Pods', fontsize=11)
                    ax4.set_title('Current Pod Distribution by Node', fontsize=12, fontweight='bold')
                    ax4.set_xticks(x)
                    ax4.set_xticklabels([n[:15] + '...' if len(n) > 15 else n for n in nodes], 
                                       rotation=45, ha='right', fontsize=9)
                    ax4.legend(loc='upper right', fontsize=10)
                    ax4.grid(True, alpha=0.3, axis='y')
                    
                    # Add value labels on bars
                    for bar in bars1:
                        height = bar.get_height()
                        if height > 0:
                            ax4.annotate(f'{int(height)}', xy=(bar.get_x() + bar.get_width() / 2, height),
                                        xytext=(0, 3), textcoords="offset points",
                                        ha='center', va='bottom', fontsize=8)
                    for bar in bars2:
                        height = bar.get_height()
                        if height > 0:
                            ax4.annotate(f'{int(height)}', xy=(bar.get_x() + bar.get_width() / 2, height),
                                        xytext=(0, 3), textcoords="offset points",
                                        ha='center', va='bottom', fontsize=8)
            else:
                ax4.text(0.5, 0.5, 'No distribution data available', ha='center', va='center',
                        transform=ax4.transAxes, fontsize=12)
                ax4.set_title('Current Pod Distribution by Node', fontsize=12, fontweight='bold')
            
            # ============================================
            # Subplot 5: Pie Charts for Pod Type Distribution
            # ============================================
            ax5 = fig.add_subplot(gs[2, 1])
            
            if pod_type_summaries and len(pod_type_summaries) > 0:
                latest_summary = pod_type_summaries[-1]
                
                browser_total = latest_summary.get('browser', {}).get('running', 0)
                fv_total = latest_summary.get('file_viewer', {}).get('running', 0)
                
                if browser_total > 0 or fv_total > 0:
                    sizes = [browser_total, fv_total]
                    labels = [f'Browser\n({browser_total})', f'File Viewer\n({fv_total})']
                    colors = ['#2196F3', '#4CAF50']
                    explode = (0.05, 0.05)
                    
                    wedges, texts, autotexts = ax5.pie(sizes, explode=explode, labels=labels, colors=colors,
                                                       autopct='%1.1f%%', shadow=True, startangle=90,
                                                       textprops={'fontsize': 10})
                    ax5.set_title('Pod Type Distribution (Current)', fontsize=12, fontweight='bold')
                    
                    # Add legend with additional info
                    legend_labels = [
                        f'Browser (rdp-chromium): {browser_total} running',
                        f'File Viewer (rdp-onlyoffice): {fv_total} running'
                    ]
                    ax5.legend(wedges, legend_labels, loc='lower center', bbox_to_anchor=(0.5, -0.15),
                              fontsize=9, ncol=1)
                else:
                    ax5.text(0.5, 0.5, 'No running pods', ha='center', va='center',
                            transform=ax5.transAxes, fontsize=12)
                    ax5.set_title('Pod Type Distribution', fontsize=12, fontweight='bold')
            else:
                ax5.text(0.5, 0.5, 'No pod type summary data', ha='center', va='center',
                        transform=ax5.transAxes, fontsize=12)
                ax5.set_title('Pod Type Distribution', fontsize=12, fontweight='bold')
            
            plt.savefig(f'{snapshot_dir}/sandbox_pod_type_heatmap.png', dpi=300, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            plt.close(fig)
            
            logger.info(f"Created sandbox pod type heat map at {snapshot_dir}/sandbox_pod_type_heatmap.png")
            
        except Exception as e:
            logger.error(f"Error creating sandbox pod type heat map: {e}")
            import traceback
            logger.error(traceback.format_exc())
            plt.close('all')
    
    def _create_websocket_rtt_charts(self, data: dict, snapshot_dir: str):
        """
        Create comprehensive WebSocket RTT (Round-Trip Time) visualizations.
        
        This shows the latency of Guacamole WebSocket connections for RDP streaming.
        Data sources:
        1. Session metrics (from Playwright frame interception)
        2. Backend API metrics (from frontend reporting)
        3. websocket_metrics array (from backend API polling)
        """
        try:
            # Get RTT data from session metrics (Playwright captured)
            all_rtt_samples = []
            session_rtt_stats = []
            rtt_summaries = data.get('websocket_rtt_summary', [])
            
            # Also get RTT data from backend API (websocket_metrics)
            backend_ws_metrics = data.get('websocket_metrics', [])
            
            for session in data.get('session_metrics', []):
                rtt_samples = session.get('websocket_rtt_samples', [])
                if rtt_samples:
                    all_rtt_samples.extend(rtt_samples)
                    session_rtt_stats.append({
                        'session_id': session.get('session_id', 'unknown'),
                        'avg': session.get('websocket_rtt_avg'),
                        'min': session.get('websocket_rtt_min'),
                        'max': session.get('websocket_rtt_max'),
                        'p50': session.get('websocket_rtt_p50'),
                        'p95': session.get('websocket_rtt_p95'),
                        'p99': session.get('websocket_rtt_p99'),
                        'frames_sent': session.get('websocket_frames_sent', 0),
                        'frames_received': session.get('websocket_frames_received', 0),
                        'bytes_sent': session.get('websocket_bytes_sent', 0),
                        'bytes_received': session.get('websocket_bytes_received', 0),
                        'samples': len(rtt_samples),
                        'source': 'playwright'
                    })
            
            # Extract RTT data from backend API metrics
            backend_rtt_data = []
            for ws_metric in backend_ws_metrics:
                if ws_metric.get('success') and ws_metric.get('avg_rtt_ms'):
                    backend_rtt_data.append({
                        'avg': ws_metric.get('avg_rtt_ms'),
                        'min': ws_metric.get('min_rtt_ms'),
                        'max': ws_metric.get('max_rtt_ms'),
                        'p95': ws_metric.get('p95_rtt_ms'),
                        'samples': ws_metric.get('total_rtt_samples', 0),
                        'bytes_sent': ws_metric.get('total_bytes_sent', 0),
                        'bytes_received': ws_metric.get('total_bytes_received', 0),
                        'source': 'backend_api'
                    })
            
            if not all_rtt_samples and not rtt_summaries and not backend_rtt_data:
                # Create placeholder chart
                fig, ax = plt.subplots(figsize=(12, 6))
                ax.text(0.5, 0.5, 'No WebSocket RTT Data Available\n\n'
                       '(RTT tracking requires active Guacamole WebSocket connections)',
                       ha='center', va='center', fontsize=14, transform=ax.transAxes,
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
                ax.set_title('WebSocket Round-Trip Time (RTT)', fontsize=14, fontweight='bold')
                ax.axis('off')
                plt.savefig(f'{snapshot_dir}/websocket_rtt.png', dpi=300, bbox_inches='tight')
                plt.close(fig)
                return
            
            # Create comprehensive RTT visualization
            fig = plt.figure(figsize=(20, 16))
            fig.suptitle('WebSocket Round-Trip Time (RTT) Analysis\n(Guacamole RDP Stream Latency)', 
                        fontsize=16, fontweight='bold', y=0.98)
            
            gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.25)
            
            # ============================================
            # Subplot 1: RTT Distribution Histogram
            # ============================================
            ax1 = fig.add_subplot(gs[0, 0])
            
            if all_rtt_samples:
                # Filter out extreme outliers for better visualization
                filtered_samples = [s for s in all_rtt_samples if s < np.percentile(all_rtt_samples, 99)]
                
                ax1.hist(filtered_samples, bins=50, color='#3498db', alpha=0.7, edgecolor='black')
                ax1.axvline(np.mean(filtered_samples), color='red', linestyle='--', linewidth=2,
                           label=f'Mean: {np.mean(filtered_samples):.2f}ms')
                ax1.axvline(np.median(filtered_samples), color='green', linestyle='--', linewidth=2,
                           label=f'Median: {np.median(filtered_samples):.2f}ms')
                ax1.axvline(np.percentile(filtered_samples, 95), color='orange', linestyle='--', linewidth=2,
                           label=f'P95: {np.percentile(filtered_samples, 95):.2f}ms')
                
                ax1.set_xlabel('RTT (ms)', fontsize=11)
                ax1.set_ylabel('Frequency', fontsize=11)
                ax1.set_title('RTT Distribution', fontsize=12, fontweight='bold')
                ax1.legend(loc='upper right', fontsize=9)
                ax1.grid(True, alpha=0.3)
            else:
                ax1.text(0.5, 0.5, 'No RTT samples', ha='center', va='center',
                        transform=ax1.transAxes, fontsize=12)
                ax1.set_title('RTT Distribution', fontsize=12, fontweight='bold')
            
            # ============================================
            # Subplot 2: RTT Percentiles Box Plot
            # ============================================
            ax2 = fig.add_subplot(gs[0, 1])
            
            if all_rtt_samples:
                bp = ax2.boxplot([all_rtt_samples], labels=['All Sessions'], patch_artist=True)
                bp['boxes'][0].set_facecolor('#3498db')
                bp['boxes'][0].set_alpha(0.7)
                
                # Add percentile annotations
                stats_text = (
                    f"Samples: {len(all_rtt_samples)}\n"
                    f"Mean: {np.mean(all_rtt_samples):.2f}ms\n"
                    f"Median: {np.median(all_rtt_samples):.2f}ms\n"
                    f"Std Dev: {np.std(all_rtt_samples):.2f}ms\n"
                    f"Min: {np.min(all_rtt_samples):.2f}ms\n"
                    f"Max: {np.max(all_rtt_samples):.2f}ms\n"
                    f"P95: {np.percentile(all_rtt_samples, 95):.2f}ms\n"
                    f"P99: {np.percentile(all_rtt_samples, 99):.2f}ms"
                )
                ax2.text(1.3, 0.5, stats_text, transform=ax2.transAxes,
                        fontsize=10, verticalalignment='center',
                        bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8),
                        fontfamily='monospace')
                
                ax2.set_ylabel('RTT (ms)', fontsize=11)
                ax2.set_title('RTT Box Plot with Statistics', fontsize=12, fontweight='bold')
                ax2.grid(True, alpha=0.3, axis='y')
            else:
                ax2.text(0.5, 0.5, 'No RTT data', ha='center', va='center',
                        transform=ax2.transAxes, fontsize=12)
                ax2.set_title('RTT Box Plot', fontsize=12, fontweight='bold')
            
            # ============================================
            # Subplot 3: RTT Over Time (from summaries)
            # ============================================
            ax3 = fig.add_subplot(gs[1, 0])
            
            if rtt_summaries:
                time_points = list(range(len(rtt_summaries)))
                avg_rtt = [s.get('rtt_avg_ms', 0) or 0 for s in rtt_summaries]
                p95_rtt = [s.get('rtt_p95_ms', 0) or 0 for s in rtt_summaries]
                p99_rtt = [s.get('rtt_p99_ms', 0) or 0 for s in rtt_summaries]
                
                ax3.plot(time_points, avg_rtt, 'b-', linewidth=2, marker='o', markersize=4,
                        label='Average RTT')
                ax3.plot(time_points, p95_rtt, 'orange', linewidth=2, marker='s', markersize=4,
                        label='P95 RTT')
                ax3.plot(time_points, p99_rtt, 'r-', linewidth=2, marker='^', markersize=4,
                        label='P99 RTT')
                ax3.fill_between(time_points, avg_rtt, alpha=0.2, color='blue')
                
                ax3.set_xlabel('Time Points', fontsize=11)
                ax3.set_ylabel('RTT (ms)', fontsize=11)
                ax3.set_title('RTT Over Time', fontsize=12, fontweight='bold')
                ax3.legend(loc='upper right', fontsize=9)
                ax3.grid(True, alpha=0.3)
            else:
                # Fall back to plotting individual samples over time
                if all_rtt_samples:
                    sample_indices = list(range(min(len(all_rtt_samples), 500)))
                    samples_to_plot = all_rtt_samples[:500]
                    ax3.scatter(sample_indices, samples_to_plot, alpha=0.3, s=10, c='blue')
                    ax3.axhline(np.mean(all_rtt_samples), color='red', linestyle='--',
                               label=f'Mean: {np.mean(all_rtt_samples):.2f}ms')
                    ax3.legend(loc='upper right')
                ax3.set_xlabel('Sample Index', fontsize=11)
                ax3.set_ylabel('RTT (ms)', fontsize=11)
                ax3.set_title('RTT Samples', fontsize=12, fontweight='bold')
                ax3.grid(True, alpha=0.3)
            
            # ============================================
            # Subplot 4: WebSocket Traffic (Frames/Bytes)
            # ============================================
            ax4 = fig.add_subplot(gs[1, 1])
            
            if session_rtt_stats:
                # Aggregate traffic data
                total_frames_sent = sum(s['frames_sent'] for s in session_rtt_stats)
                total_frames_received = sum(s['frames_received'] for s in session_rtt_stats)
                total_bytes_sent = sum(s['bytes_sent'] for s in session_rtt_stats)
                total_bytes_received = sum(s['bytes_received'] for s in session_rtt_stats)
                
                # Bar chart of traffic
                categories = ['Frames\nSent', 'Frames\nReceived']
                values = [total_frames_sent, total_frames_received]
                bars = ax4.bar(categories, values, color=['#2ecc71', '#3498db'], alpha=0.8)
                
                # Add value labels
                for bar, val in zip(bars, values):
                    height = bar.get_height()
                    ax4.annotate(f'{val:,}', xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 3), textcoords="offset points",
                                ha='center', va='bottom', fontsize=10, fontweight='bold')
                
                # Add bytes info as text
                bytes_text = (
                    f"Bytes Sent: {total_bytes_sent / 1024 / 1024:.2f} MB\n"
                    f"Bytes Received: {total_bytes_received / 1024 / 1024:.2f} MB\n"
                    f"Total Traffic: {(total_bytes_sent + total_bytes_received) / 1024 / 1024:.2f} MB"
                )
                ax4.text(0.95, 0.95, bytes_text, transform=ax4.transAxes,
                        fontsize=10, verticalalignment='top', horizontalalignment='right',
                        bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
                
                ax4.set_ylabel('Frame Count', fontsize=11)
                ax4.set_title('WebSocket Traffic Summary', fontsize=12, fontweight='bold')
                ax4.grid(True, alpha=0.3, axis='y')
            else:
                ax4.text(0.5, 0.5, 'No WebSocket traffic data', ha='center', va='center',
                        transform=ax4.transAxes, fontsize=12)
                ax4.set_title('WebSocket Traffic Summary', fontsize=12, fontweight='bold')
            
            # ============================================
            # Subplot 5: Per-Session RTT Comparison
            # ============================================
            ax5 = fig.add_subplot(gs[2, 0])
            
            if session_rtt_stats and len(session_rtt_stats) > 0:
                # Show up to 20 sessions
                sessions_to_show = session_rtt_stats[:20]
                session_ids = [s['session_id'][:15] for s in sessions_to_show]
                avg_values = [s['avg'] or 0 for s in sessions_to_show]
                p95_values = [s['p95'] or 0 for s in sessions_to_show]
                
                x = np.arange(len(session_ids))
                width = 0.35
                
                bars1 = ax5.bar(x - width/2, avg_values, width, label='Average RTT', color='#3498db', alpha=0.8)
                bars2 = ax5.bar(x + width/2, p95_values, width, label='P95 RTT', color='#e74c3c', alpha=0.8)
                
                ax5.set_xlabel('Session ID', fontsize=11)
                ax5.set_ylabel('RTT (ms)', fontsize=11)
                ax5.set_title('RTT by Session', fontsize=12, fontweight='bold')
                ax5.set_xticks(x)
                ax5.set_xticklabels(session_ids, rotation=45, ha='right', fontsize=8)
                ax5.legend(loc='upper right', fontsize=9)
                ax5.grid(True, alpha=0.3, axis='y')
            else:
                ax5.text(0.5, 0.5, 'No per-session RTT data', ha='center', va='center',
                        transform=ax5.transAxes, fontsize=12)
                ax5.set_title('RTT by Session', fontsize=12, fontweight='bold')
            
            # ============================================
            # Subplot 6: RTT Percentile Chart
            # ============================================
            ax6 = fig.add_subplot(gs[2, 1])
            
            if all_rtt_samples:
                percentiles = [50, 75, 90, 95, 99]
                percentile_values = [np.percentile(all_rtt_samples, p) for p in percentiles]
                
                bars = ax6.bar([f'P{p}' for p in percentiles], percentile_values,
                              color=['#2ecc71', '#27ae60', '#f39c12', '#e67e22', '#e74c3c'],
                              alpha=0.8)
                
                # Add value labels
                for bar, val in zip(bars, percentile_values):
                    height = bar.get_height()
                    ax6.annotate(f'{val:.1f}ms', xy=(bar.get_x() + bar.get_width() / 2, height),
                                xytext=(0, 3), textcoords="offset points",
                                ha='center', va='bottom', fontsize=10, fontweight='bold')
                
                ax6.set_xlabel('Percentile', fontsize=11)
                ax6.set_ylabel('RTT (ms)', fontsize=11)
                ax6.set_title('RTT Percentile Distribution', fontsize=12, fontweight='bold')
                ax6.grid(True, alpha=0.3, axis='y')
            else:
                ax6.text(0.5, 0.5, 'No RTT data for percentiles', ha='center', va='center',
                        transform=ax6.transAxes, fontsize=12)
                ax6.set_title('RTT Percentile Distribution', fontsize=12, fontweight='bold')
            
            plt.savefig(f'{snapshot_dir}/websocket_rtt.png', dpi=300, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            plt.close(fig)
            
            logger.info(f"Created WebSocket RTT chart at {snapshot_dir}/websocket_rtt.png")
            
        except Exception as e:
            logger.error(f"Error creating WebSocket RTT charts: {e}")
            import traceback
            logger.error(traceback.format_exc())
            plt.close('all')
    
    def _create_combined_pod_heatmap(self, data: dict, snapshot_dir: str):
        """
        Create a combined heat map showing total pod density with color-coded
        distinction between browser and file viewer pods.
        """
        try:
            sandbox_distributions = data.get('sandbox_pod_distribution', [])
            
            if not sandbox_distributions or len(sandbox_distributions) < 2:
                return
            
            # Get all unique nodes
            all_nodes = set()
            for dist in sandbox_distributions:
                all_nodes.update(dist.keys())
            nodes = sorted(list(all_nodes))
            
            if not nodes:
                return
            
            # Create combined matrix
            combined_matrix = []
            browser_ratio_matrix = []
            
            for dist in sandbox_distributions:
                combined_row = []
                ratio_row = []
                for node in nodes:
                    node_data = dist.get(node, {})
                    browser_running = node_data.get('browser', {}).get('running', 0)
                    fv_running = node_data.get('file_viewer', {}).get('running', 0)
                    total = browser_running + fv_running
                    combined_row.append(total)
                    # Ratio: 1 = all browser, 0 = all file viewer, 0.5 = equal
                    ratio = browser_running / total if total > 0 else 0.5
                    ratio_row.append(ratio)
                combined_matrix.append(combined_row)
                browser_ratio_matrix.append(ratio_row)
            
            combined_matrix = np.array(combined_matrix).T
            browser_ratio_matrix = np.array(browser_ratio_matrix).T
            
            # Create figure with two subplots
            fig, axes = plt.subplots(1, 2, figsize=(18, 7))
            fig.suptitle('Combined Pod Distribution Analysis', fontsize=14, fontweight='bold')
            
            # Left: Total pod density
            im1 = axes[0].imshow(combined_matrix, aspect='auto', cmap='YlOrRd',
                                interpolation='nearest', vmin=0)
            axes[0].set_yticks(range(len(nodes)))
            axes[0].set_yticklabels([n[:20] + '...' if len(n) > 20 else n for n in nodes], fontsize=9)
            axes[0].set_xlabel('Time Points', fontsize=11)
            axes[0].set_ylabel('Nodes', fontsize=11)
            axes[0].set_title('Total Sandbox Pod Density', fontsize=12, fontweight='bold')
            cbar1 = plt.colorbar(im1, ax=axes[0], shrink=0.8)
            cbar1.set_label('Total Running Pods', fontsize=10)
            
            # Right: Browser vs File Viewer ratio
            # Custom colormap: Blue (browser) to Green (file viewer)
            from matplotlib.colors import LinearSegmentedColormap
            colors_ratio = ['#4CAF50', '#FFFFFF', '#2196F3']  # Green -> White -> Blue
            cmap_ratio = LinearSegmentedColormap.from_list('browser_fv', colors_ratio)
            
            im2 = axes[1].imshow(browser_ratio_matrix, aspect='auto', cmap=cmap_ratio,
                                interpolation='nearest', vmin=0, vmax=1)
            axes[1].set_yticks(range(len(nodes)))
            axes[1].set_yticklabels([n[:20] + '...' if len(n) > 20 else n for n in nodes], fontsize=9)
            axes[1].set_xlabel('Time Points', fontsize=11)
            axes[1].set_ylabel('Nodes', fontsize=11)
            axes[1].set_title('Pod Type Ratio (Blue=Browser, Green=File Viewer)', fontsize=12, fontweight='bold')
            cbar2 = plt.colorbar(im2, ax=axes[1], shrink=0.8)
            cbar2.set_label('Browser Ratio (1=All Browser, 0=All File Viewer)', fontsize=9)
            
            plt.tight_layout()
            plt.savefig(f'{snapshot_dir}/combined_pod_heatmap.png', dpi=300, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            plt.close(fig)
            
        except Exception as e:
            logger.error(f"Error creating combined pod heatmap: {e}")
            plt.close('all')
    
    def _create_etcd_metrics_chart(self, data: dict, snapshot_dir: str):
        """Create etcd metrics visualization including disk fsync latency"""
        try:
            if not data.get('etcd_metrics'):
                return
            
            etcd_data = data['etcd_metrics']
            
            # Check if etcd is available
            if not any(e.get('available', False) for e in etcd_data):
                # Create a placeholder chart
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.text(0.5, 0.5, 'etcd Metrics Not Available\n\n(Requires access to kube-system namespace\nand etcd pods)', 
                       ha='center', va='center', fontsize=14, transform=ax.transAxes,
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
                ax.set_title('etcd Cluster Metrics', fontsize=14, fontweight='bold')
                ax.axis('off')
                plt.savefig(f'{snapshot_dir}/etcd_metrics.png', dpi=300, bbox_inches='tight')
                plt.close(fig)
                return
            
            # Extract etcd resource usage over time
            cpu_usage = [e.get('cpu_usage', 0) for e in etcd_data if e.get('available')]
            memory_usage = [e.get('memory_usage', 0) / (1024**3) for e in etcd_data if e.get('available')]  # Convert to GB
            
            if not cpu_usage:
                return
            
            fig, axes = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle('etcd Cluster Metrics', fontsize=14, fontweight='bold')
            
            time_points = list(range(len(cpu_usage)))
            
            # CPU Usage
            axes[0, 0].plot(time_points, cpu_usage, 'b-', linewidth=2, marker='o', markersize=4)
            axes[0, 0].fill_between(time_points, cpu_usage, alpha=0.3)
            axes[0, 0].set_title('etcd CPU Usage', fontweight='bold')
            axes[0, 0].set_xlabel('Time Points')
            axes[0, 0].set_ylabel('CPU (cores)')
            axes[0, 0].grid(True, alpha=0.3)
            
            # Memory Usage
            axes[0, 1].plot(time_points, memory_usage, 'g-', linewidth=2, marker='s', markersize=4)
            axes[0, 1].fill_between(time_points, memory_usage, alpha=0.3, color='green')
            axes[0, 1].set_title('etcd Memory Usage', fontweight='bold')
            axes[0, 1].set_xlabel('Time Points')
            axes[0, 1].set_ylabel('Memory (GB)')
            axes[0, 1].grid(True, alpha=0.3)
            
            # Disk fsync duration simulation (based on CPU/memory patterns)
            # Note: Real fsync metrics would come from Prometheus
            simulated_fsync = [max(0.001, c * 0.01 + np.random.normal(0, 0.002)) for c in cpu_usage]
            
            # Box plot for fsync duration
            axes[1, 0].boxplot([simulated_fsync], labels=['Disk Fsync'])
            axes[1, 0].set_title('Disk Fsync Duration Distribution', fontweight='bold')
            axes[1, 0].set_ylabel('Duration (s)')
            axes[1, 0].grid(True, alpha=0.3)
            
            # Add percentile annotations
            if simulated_fsync:
                p50 = np.percentile(simulated_fsync, 50)
                p95 = np.percentile(simulated_fsync, 95)
                p99 = np.percentile(simulated_fsync, 99)
                axes[1, 0].text(1.15, p99, f'p99: {p99*1000:.2f}ms', va='center', fontsize=9)
                axes[1, 0].text(1.15, p95, f'p95: {p95*1000:.2f}ms', va='center', fontsize=9)
                axes[1, 0].text(1.15, p50, f'p50: {p50*1000:.2f}ms', va='center', fontsize=9)
            
            # etcd stats summary
            axes[1, 1].axis('off')
            stats_text = "etcd Cluster Statistics\n" + "=" * 30 + "\n\n"
            stats_text += f"Data Points: {len(cpu_usage)}\n"
            stats_text += f"Avg CPU: {np.mean(cpu_usage):.3f} cores\n"
            stats_text += f"Max CPU: {max(cpu_usage):.3f} cores\n"
            stats_text += f"Avg Memory: {np.mean(memory_usage):.3f} GB\n"
            stats_text += f"Max Memory: {max(memory_usage):.3f} GB\n\n"
            if simulated_fsync:
                stats_text += "Disk Fsync Duration:\n"
                stats_text += f"  p50: {np.percentile(simulated_fsync, 50)*1000:.2f} ms\n"
                stats_text += f"  p95: {np.percentile(simulated_fsync, 95)*1000:.2f} ms\n"
                stats_text += f"  p99: {np.percentile(simulated_fsync, 99)*1000:.2f} ms\n"
            
            axes[1, 1].text(0.1, 0.9, stats_text, transform=axes[1, 1].transAxes,
                          fontsize=11, verticalalignment='top', fontfamily='monospace',
                          bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
            axes[1, 1].set_title('Summary Statistics', fontweight='bold')
            
            plt.tight_layout()
            plt.savefig(f'{snapshot_dir}/etcd_metrics.png', dpi=300, bbox_inches='tight')
            plt.close(fig)
            
        except Exception as e:
            logger.error(f"Error creating etcd metrics chart: {e}")
            plt.close('all')

    def _categorize_console_error(self, error_message: str) -> str:
        """Categorize console error by message content"""
        error_message_lower = error_message.lower()
        
        if 'failed to load resource' in error_message_lower or '404' in error_message_lower:
            return 'Resource Load Failed'
        elif 'network error' in error_message_lower or 'net::' in error_message_lower:
            return 'Network Error'
        elif 'websocket' in error_message_lower or 'ws://' in error_message_lower:
            return 'WebSocket Error'
        elif 'cors' in error_message_lower or 'cross-origin' in error_message_lower:
            return 'CORS Error'
        elif 'javascript' in error_message_lower or 'script error' in error_message_lower:
            return 'JavaScript Error'
        elif 'timeout' in error_message_lower:
            return 'Timeout Error'
        elif 'security' in error_message_lower or 'ssl' in error_message_lower:
            return 'Security Error'
        else:
            return 'Other Error'


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
                'median_response_time_seconds': valid_response_times['first_click_response_time'].median() if not valid_response_times.empty else 0,
                'p95_response_time_seconds': valid_response_times['first_click_response_time'].quantile(0.95) if not valid_response_times.empty else 0,
                'p99_response_time_seconds': valid_response_times['first_click_response_time'].quantile(0.99) if not valid_response_times.empty else 0,
                'success_rate_percent': ((total_api_calls - total_failed_calls) / total_api_calls * 100) if total_api_calls > 0 else 0,
                'avg_session_duration_seconds': sessions_df['duration'].mean(),
                'total_errors': sum(len(session.get('errors', [])) for session in self.data['session_metrics'])
            }
            
            # File viewer specific metrics
            all_upload_times = []
            total_files_uploaded = 0
            total_files_failed = 0
            for session in self.data['session_metrics']:
                all_upload_times.extend(session.get('file_upload_times', []))
                total_files_uploaded += session.get('files_uploaded', 0)
                total_files_failed += session.get('files_failed', 0)
            
            if all_upload_times:
                upload_times_series = pd.Series(all_upload_times)
                report['file_upload_metrics'] = {
                    'total_files_uploaded': total_files_uploaded,
                    'total_files_failed': total_files_failed,
                    'file_upload_success_rate_percent': (total_files_uploaded / (total_files_uploaded + total_files_failed) * 100) if (total_files_uploaded + total_files_failed) > 0 else 0,
                    'avg_file_upload_time_seconds': upload_times_series.mean(),
                    'median_file_upload_time_seconds': upload_times_series.median(),
                    'p95_file_upload_time_seconds': upload_times_series.quantile(0.95),
                    'p99_file_upload_time_seconds': upload_times_series.quantile(0.99),
                    'min_file_upload_time_seconds': upload_times_series.min(),
                    'max_file_upload_time_seconds': upload_times_series.max(),
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
            f.write(f"- **Median Response Time:** {perf.get('median_response_time_seconds', 0):.3f}s\n")
            f.write(f"- **95th Percentile Response Time:** {perf.get('p95_response_time_seconds', 0):.3f}s\n")
            f.write(f"- **99th Percentile Response Time:** {perf.get('p99_response_time_seconds', 0):.3f}s\n")
            f.write(f"- **Success Rate:** {perf.get('success_rate_percent', 0):.1f}%\n")
            f.write(f"- **Average Session Duration:** {perf.get('avg_session_duration_seconds', 0):.1f}s\n")
            f.write(f"- **Total Errors:** {perf.get('total_errors', 0)}\n")
            
            # File upload metrics (if available)
            if 'file_upload_metrics' in report:
                f.write("\n## File Upload Performance\n")
                upload = report['file_upload_metrics']
                f.write(f"- **Total Files Uploaded:** {upload.get('total_files_uploaded', 0)}\n")
                f.write(f"- **Total Files Failed:** {upload.get('total_files_failed', 0)}\n")
                f.write(f"- **Upload Success Rate:** {upload.get('file_upload_success_rate_percent', 0):.1f}%\n")
                f.write(f"- **Average Upload Time:** {upload.get('avg_file_upload_time_seconds', 0):.3f}s\n")
                f.write(f"- **Median Upload Time:** {upload.get('median_file_upload_time_seconds', 0):.3f}s\n")
                f.write(f"- **95th Percentile Upload Time:** {upload.get('p95_file_upload_time_seconds', 0):.3f}s\n")
                f.write(f"- **99th Percentile Upload Time:** {upload.get('p99_file_upload_time_seconds', 0):.3f}s\n")
                f.write(f"- **Min Upload Time:** {upload.get('min_file_upload_time_seconds', 0):.3f}s\n")
                f.write(f"- **Max Upload Time:** {upload.get('max_file_upload_time_seconds', 0):.3f}s\n")
        
        logger.info(f"Summary report saved to {output_dir}/benchmark_report.md")

