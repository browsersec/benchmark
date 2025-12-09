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
                
                # Create enhanced summary file with console errors
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
                    
                    # Add console errors summary
                    if data['session_metrics']:
                        total_console_errors = sum(len(s.get('console_errors', [])) for s in data['session_metrics'])
                        total_severe_errors = sum(
                            sum(1 for err in s.get('console_errors', []) if err.get('level') == 'SEVERE')
                            for s in data['session_metrics']
                        )
                        f.write(f"Total console errors: {total_console_errors}\n")
                        f.write(f"Severe console errors: {total_severe_errors}\n")
                        
                        if total_console_errors > 0:
                            f.write(f"Avg console errors per session: {total_console_errors / len(data['session_metrics']):.1f}\n")
                
                logger.info(f"Saved visualization snapshot {self.save_counter} to {snapshot_dir}")
                
            except Exception as e:
                logger.error(f"Error saving visualization snapshot: {e}")
                # Clean up any matplotlib state on error
                try:
                    plt.close('all')
                    plt.clf()
                except:
                    pass

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

