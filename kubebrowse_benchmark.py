#!/usr/bin/env python3
"""
KubeBrowse Benchmarking System
Monitors and visualizes performance metrics for the KubeBrowse application
"""

import asyncio
import os
import aiohttp
import websockets
import ssl
import time
import json
import threading
import requests
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.animation import FuncAnimation
import pandas as pd
import numpy as np
from collections import defaultdict, deque
import subprocess
import yaml
import logging
from concurrent.futures import ThreadPoolExecutor
import queue
import warnings
warnings.filterwarnings('ignore')

os.environ['KUBECONFIG'] = '/home/sanjay7178/kube/proxmox.yml'  
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KubeBrowseBenchmark:
    def __init__(self, api_base_url="https://172.18.120.152:30006", namespace="browser-sandbox"):
        self.api_base_url = api_base_url
        self.namespace = namespace
        self.start_time = datetime.now()
        
        # Create plots directory
        self.plots_dir = f'/home/sanjay7178/benchmark/plots_{self.start_time.strftime("%Y%m%d_%H%M%S")}'
        os.makedirs(self.plots_dir, exist_ok=True)
        
        # Data storage
        self.metrics_data = {
            'timestamps': deque(maxlen=1000),
            'cpu_usage': deque(maxlen=1000),
            'memory_usage': deque(maxlen=1000),
            'pod_counts': deque(maxlen=1000),
            'api_latency': deque(maxlen=1000),
            'websocket_connections': deque(maxlen=1000),
            'active_sessions': deque(maxlen=1000),
            'hpa_replicas': {
                'api': deque(maxlen=1000),
                'frontend': deque(maxlen=1000),
                'guacd': deque(maxlen=1000)
            }
        }
        
        # Connection tracking
        self.active_connections = {}
        self.connection_queue = queue.Queue()
        self.websocket_processes = []  # Track websocat processes instead of tasks
        
        # SSL context for insecure connections
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        
        # Performance tracking
        self.api_response_times = deque(maxlen=1000)
        self.websocket_connection_times = deque(maxlen=1000)
        
        # Plot save tracking
        self.last_plot_save = datetime.now()
        self.plot_save_interval = 60  # Save plots every 60 seconds
        
    def get_kubernetes_metrics(self):
        """Get Kubernetes cluster metrics using kubectl"""
        try:
            # Get node metrics
            node_cmd = ["kubectl", "top", "nodes", "--no-headers"]
            node_result = subprocess.run(node_cmd, capture_output=True, text=True)
            
            cpu_usage = 0
            memory_usage = 0
            
            if node_result.returncode == 0:
                for line in node_result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        cpu_str = parts[1].replace('m', '').replace('%', '')
                        memory_str = parts[2].replace('Mi', '').replace('Gi', '').replace('%', '')
                        
                        try:
                            cpu_usage += float(cpu_str) if 'm' not in parts[1] else float(cpu_str) / 1000
                            if 'Gi' in parts[2]:
                                memory_usage += float(memory_str) * 1024
                            else:
                                memory_usage += float(memory_str)
                        except ValueError:
                            continue
            
            # Get browser pod count
            pod_cmd = ["kubectl", "get", "pods", "-n", self.namespace, "-l", "app=browser-sandbox-browser", "--no-headers"]
            pod_result = subprocess.run(pod_cmd, capture_output=True, text=True)
            
            pod_count = 0
            if pod_result.returncode == 0:
                pod_count = len([line for line in pod_result.stdout.strip().split('\n') if line])
            
            # Get HPA metrics
            hpa_metrics = self.get_hpa_metrics()
            
            return {
                'cpu_usage': cpu_usage,
                'memory_usage': memory_usage,
                'pod_count': pod_count,
                'hpa_metrics': hpa_metrics
            }
            
        except Exception as e:
            logger.error(f"Error getting Kubernetes metrics: {e}")
            return {
                'cpu_usage': 0,
                'memory_usage': 0,
                'pod_count': 0,
                'hpa_metrics': {'api': 0, 'frontend': 0, 'guacd': 0}
            }
    
    def get_hpa_metrics(self):
        """Get HPA replica counts"""
        hpa_metrics = {'api': 0, 'frontend': 0, 'guacd': 0}
        
        try:
            hpa_cmd = ["kubectl", "get", "hpa", "-n", self.namespace, "-o", "json"]
            result = subprocess.run(hpa_cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                hpa_data = json.loads(result.stdout)
                for item in hpa_data.get('items', []):
                    name = item['metadata']['name']
                    replicas = item.get('status', {}).get('currentReplicas', 0)
                    
                    if 'api' in name:
                        hpa_metrics['api'] = replicas
                    elif 'frontend' in name:
                        hpa_metrics['frontend'] = replicas
                    elif 'guacd' in name:
                        hpa_metrics['guacd'] = replicas
                        
        except Exception as e:
            logger.error(f"Error getting HPA metrics: {e}")
            
        return hpa_metrics
    
    async def deploy_browser_session(self, session):
        """Deploy a browser session and measure API latency"""
        start_time = time.time()
        
        try:
            payload = {"width": "1024", "height": "768"}
            
            async with session.post(
                f"{self.api_base_url}/test/deploy-browser",
                json=payload,
                ssl=self.ssl_context,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                response_data = await response.json()
                api_latency = time.time() - start_time
                
                if response.status == 200:
                    connection_id = response_data.get('connection_id')
                    if connection_id:
                        self.active_connections[connection_id] = {
                            'created_at': datetime.now(),
                            'pod_name': response_data.get('podName'),
                            'status': response_data.get('status', 'unknown')
                        }
                        logger.info(f"Deployed browser session: {connection_id}")
                        return connection_id, api_latency
                
                return None, api_latency
                
        except Exception as e:
            api_latency = time.time() - start_time
            logger.error(f"Error deploying browser session: {e}")
            return None, api_latency
    
    async def get_websocket_info(self, session, connection_id):
        """Get websocket connection information"""
        start_time = time.time()
        
        try:
            async with session.get(
                f"{self.api_base_url}/test/connect/{connection_id}",
                ssl=self.ssl_context,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                api_latency = time.time() - start_time
                
                if response.status == 200:
                    response_data = await response.json()
                    if response_data.get('status') == 'ready':
                        websocket_url = response_data.get('websocket_url')
                        return websocket_url, api_latency
                
                return None, api_latency
                
        except Exception as e:
            api_latency = time.time() - start_time
            logger.error(f"Error getting websocket info for {connection_id}: {e}")
            return None, api_latency
    
    async def connect_websocket_websocat(self, websocket_url, connection_id):
        """Connect to websocket using websocat subprocess"""
        ws_start_time = time.time()
        
        try:
            uri = f"wss://172.18.120.152:30006{websocket_url}"
            
            # Construct websocat command
            websocat_cmd = [
                "websocat",
                "--insecure",
                uri,
                "-H", "Sec-WebSocket-Protocol: guacamole"
            ]
            
            logger.info(f"Starting websocat for connection {connection_id}: {' '.join(websocat_cmd)}")
            
            # Start websocat process
            process = await asyncio.create_subprocess_exec(
                *websocat_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            connection_time = time.time() - ws_start_time
            self.websocket_connection_times.append(connection_time)
            
            # Store process info
            process_info = {
                'process': process,
                'connection_id': connection_id,
                'start_time': datetime.now(),
                'connection_time': connection_time
            }
            self.websocket_processes.append(process_info)
            
            logger.info(f"WebSocket connected via websocat in {connection_time:.2f}s for {connection_id}")
            
            # Monitor the process
            asyncio.create_task(self.monitor_websocat_process(process_info))
            
            return connection_time
                    
        except Exception as e:
            connection_time = time.time() - ws_start_time
            logger.error(f"WebSocket connection error for {connection_id}: {e}")
            return connection_time
    
    async def monitor_websocat_process(self, process_info):
        """Monitor websocat process and handle its lifecycle"""
        process = process_info['process']
        connection_id = process_info['connection_id']
        
        try:
            # Wait for process to complete or timeout
            await asyncio.wait_for(process.wait(), timeout=300)  # 5 minute timeout
            
            if process.returncode == 0:
                logger.info(f"WebSocket process completed successfully for {connection_id}")
            else:
                stderr_output = await process.stderr.read()
                logger.warning(f"WebSocket process failed for {connection_id}: {stderr_output.decode()}")
                
        except asyncio.TimeoutError:
            logger.info(f"WebSocket process timeout for {connection_id}, terminating")
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=10)
            except:
                process.kill()
        except Exception as e:
            logger.error(f"Error monitoring websocat process for {connection_id}: {e}")
        finally:
            # Remove from active processes
            self.websocket_processes = [p for p in self.websocket_processes if p['connection_id'] != connection_id]
    
    async def create_concurrent_sessions(self, num_sessions=5):
        """Create multiple concurrent browser sessions with websocat connections"""
        async with aiohttp.ClientSession() as session:
            # First, deploy all browser sessions
            deploy_tasks = []
            for i in range(num_sessions):
                task = asyncio.create_task(self.deploy_browser_session(session))
                deploy_tasks.append(task)
                await asyncio.sleep(0.1)  # Small delay between deployments
            
            # Wait for all deployments to complete
            deploy_results = await asyncio.gather(*deploy_tasks, return_exceptions=True)
            
            # Filter successful deployments
            successful_deployments = []
            for result in deploy_results:
                if isinstance(result, tuple) and result[0] is not None:
                    connection_id, latency = result
                    successful_deployments.append(connection_id)
                    self.api_response_times.append(latency)
            
            logger.info(f"Successfully deployed {len(successful_deployments)}/{num_sessions} browser sessions")
            
            # Wait for pods to be ready and get websocket URLs
            websocket_info_tasks = []
            for connection_id in successful_deployments:
                task = asyncio.create_task(self.wait_for_websocket_ready(session, connection_id))
                websocket_info_tasks.append(task)
            
            websocket_results = await asyncio.gather(*websocket_info_tasks, return_exceptions=True)
            
            # Filter successful websocket info retrievals
            ready_connections = []
            for result in websocket_results:
                if isinstance(result, tuple) and result[0] is not None:
                    connection_id, websocket_url = result
                    ready_connections.append((connection_id, websocket_url))
            
            logger.info(f"Got websocket info for {len(ready_connections)}/{len(successful_deployments)} connections")
            
            # Now establish all websocket connections concurrently
            websocket_tasks = []
            for connection_id, websocket_url in ready_connections:
                task = asyncio.create_task(self.connect_websocket_websocat(websocket_url, connection_id))
                websocket_tasks.append(task)
            
            # Start all websocket connections
            websocket_connection_results = await asyncio.gather(*websocket_tasks, return_exceptions=True)
            
            successful_websockets = len([r for r in websocket_connection_results if not isinstance(r, Exception)])
            logger.info(f"Successfully established {successful_websockets}/{len(ready_connections)} websocket connections")
            
            return ready_connections
    
    async def wait_for_websocket_ready(self, session, connection_id, max_wait=60):
        """Wait for browser pod to be ready and return websocket URL"""
        wait_time = 0
        
        while wait_time < max_wait:
            await asyncio.sleep(2)
            wait_time += 2
            
            websocket_url, connect_latency = await self.get_websocket_info(session, connection_id)
            self.api_response_times.append(connect_latency)
            
            if websocket_url:
                return connection_id, websocket_url
        
        logger.error(f"Timeout waiting for websocket URL for {connection_id}")
        return connection_id, None
    
    async def deploy_and_connect(self, session, session_id):
        """Deploy browser session and establish websocket connection - DEPRECATED"""
        # This method is now replaced by the new concurrent approach
        logger.warning("deploy_and_connect is deprecated, use create_concurrent_sessions instead")
        return None
    
    def collect_metrics(self):
        """Collect all metrics periodically"""
        while True:
            try:
                current_time = datetime.now()
                
                # Get Kubernetes metrics
                k8s_metrics = self.get_kubernetes_metrics()
                
                # Get active sessions count
                try:
                    response = requests.get(
                        f"{self.api_base_url}/sessions/",
                        verify=False,
                        timeout=5
                    )
                    if response.status_code == 200:
                        session_data = response.json()
                        active_sessions = session_data.get('active_sessions', 0)
                    else:
                        active_sessions = 0
                except:
                    active_sessions = 0
                
                # Count active websocket processes
                active_websocket_count = len([p for p in self.websocket_processes if p['process'].returncode is None])
                
                # Store metrics
                self.metrics_data['timestamps'].append(current_time)
                self.metrics_data['cpu_usage'].append(k8s_metrics['cpu_usage'])
                self.metrics_data['memory_usage'].append(k8s_metrics['memory_usage'])
                self.metrics_data['pod_counts'].append(k8s_metrics['pod_count'])
                self.metrics_data['active_sessions'].append(active_sessions)
                self.metrics_data['websocket_connections'].append(active_websocket_count)
                
                # Store HPA metrics
                for component, replicas in k8s_metrics['hpa_metrics'].items():
                    self.metrics_data['hpa_replicas'][component].append(replicas)
                
                # Store API latency (average of recent measurements)
                if self.api_response_times:
                    avg_latency = np.mean(list(self.api_response_times)[-10:])  # Last 10 measurements
                    self.metrics_data['api_latency'].append(avg_latency)
                else:
                    self.metrics_data['api_latency'].append(0)
                
                logger.info(f"Metrics collected - CPU: {k8s_metrics['cpu_usage']:.2f}, "
                          f"Memory: {k8s_metrics['memory_usage']:.2f}MB, "
                          f"Pods: {k8s_metrics['pod_count']}, "
                          f"Sessions: {active_sessions}, "
                          f"WebSocket Processes: {active_websocket_count}")
                
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
            
            time.sleep(10)  # Collect metrics every 10 seconds
    
    def save_current_visualization(self, suffix=""):
        """Save current visualization to file"""
        try:
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'kubebrowse_metrics_{timestamp_str}{suffix}.png'
            filepath = os.path.join(self.plots_dir, filename)
            
            # Create a new figure for saving (to avoid interfering with live plot)
            save_fig, save_axes = plt.subplots(2, 3, figsize=(20, 12))
            save_fig.suptitle(f'KubeBrowse Performance Metrics - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', fontsize=16)
            
            if not self.metrics_data['timestamps']:
                save_fig.text(0.5, 0.5, 'No data available yet', ha='center', va='center', fontsize=16)
                save_fig.savefig(filepath, dpi=300, bbox_inches='tight')
                plt.close(save_fig)
                return filepath
            
            timestamps = list(self.metrics_data['timestamps'])
            
            # CPU Usage
            save_axes[0, 0].plot(timestamps, list(self.metrics_data['cpu_usage']), 'b-', linewidth=2)
            save_axes[0, 0].set_title('CPU Usage (Cores)')
            save_axes[0, 0].set_ylabel('CPU Cores')
            save_axes[0, 0].grid(True)
            save_axes[0, 0].tick_params(axis='x', rotation=45)
            
            # Memory Usage
            save_axes[0, 1].plot(timestamps, list(self.metrics_data['memory_usage']), 'g-', linewidth=2)
            save_axes[0, 1].set_title('Memory Usage (MB)')
            save_axes[0, 1].set_ylabel('Memory (MB)')
            save_axes[0, 1].grid(True)
            save_axes[0, 1].tick_params(axis='x', rotation=45)
            
            # Pod Counts
            save_axes[0, 2].plot(timestamps, list(self.metrics_data['pod_counts']), 'r-', linewidth=2, marker='o')
            save_axes[0, 2].set_title('Browser Pod Count')
            save_axes[0, 2].set_ylabel('Number of Pods')
            save_axes[0, 2].grid(True)
            save_axes[0, 2].tick_params(axis='x', rotation=45)
            
            # API Latency
            save_axes[1, 0].plot(timestamps, list(self.metrics_data['api_latency']), 'm-', linewidth=2)
            save_axes[1, 0].set_title('API Response Latency')
            save_axes[1, 0].set_ylabel('Latency (seconds)')
            save_axes[1, 0].grid(True)
            save_axes[1, 0].tick_params(axis='x', rotation=45)
            
            # HPA Replicas
            for component, data in self.metrics_data['hpa_replicas'].items():
                if data:
                    save_axes[1, 1].plot(timestamps, list(data), linewidth=2, marker='s', label=component)
            save_axes[1, 1].set_title('HPA Replica Counts')
            save_axes[1, 1].set_ylabel('Number of Replicas')
            save_axes[1, 1].legend()
            save_axes[1, 1].grid(True)
            save_axes[1, 1].tick_params(axis='x', rotation=45)
            
            # WebSocket Connections and Active Sessions
            save_axes[1, 2].plot(timestamps, list(self.metrics_data['websocket_connections']), 
                          'c-', linewidth=2, marker='^', label='WebSocket Connections')
            save_axes[1, 2].plot(timestamps, list(self.metrics_data['active_sessions']), 
                          'orange', linewidth=2, marker='v', label='Active Sessions')
            save_axes[1, 2].set_title('Connections & Sessions')
            save_axes[1, 2].set_ylabel('Count')
            save_axes[1, 2].legend()
            save_axes[1, 2].grid(True)
            save_axes[1, 2].tick_params(axis='x', rotation=45)
            
            # Format x-axis for all subplots
            for ax_row in save_axes:
                for ax in ax_row:
                    if timestamps:
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
            
            save_fig.tight_layout()
            save_fig.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close(save_fig)
            
            logger.info(f"Visualization saved to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving visualization: {e}")
            return None
    
    def create_final_comprehensive_report(self):
        """Create a comprehensive final report with multiple visualizations"""
        try:
            if not self.metrics_data['timestamps']:
                logger.warning("No data available for comprehensive report")
                return
            
            timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Create comprehensive dashboard
            fig = plt.figure(figsize=(24, 16))
            fig.suptitle(f'KubeBrowse Comprehensive Performance Report\n'
                        f'Test Duration: {datetime.now() - self.start_time}\n'
                        f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 
                        fontsize=20, y=0.98)
            
            timestamps = list(self.metrics_data['timestamps'])
            
            # Create subplots with custom layout
            gs = fig.add_gridspec(4, 3, hspace=0.3, wspace=0.3)
            
            # Resource Usage Over Time
            ax1 = fig.add_subplot(gs[0, 0])
            ax1.plot(timestamps, list(self.metrics_data['cpu_usage']), 'b-', linewidth=2, label='CPU (cores)')
            ax1.set_title('CPU Usage Over Time')
            ax1.set_ylabel('CPU Cores')
            ax1.grid(True)
            ax1.tick_params(axis='x', rotation=45)
            
            ax2 = fig.add_subplot(gs[0, 1])
            ax2.plot(timestamps, list(self.metrics_data['memory_usage']), 'g-', linewidth=2)
            ax2.set_title('Memory Usage Over Time')
            ax2.set_ylabel('Memory (MB)')
            ax2.grid(True)
            ax2.tick_params(axis='x', rotation=45)
            
            # Scaling Metrics
            ax3 = fig.add_subplot(gs[0, 2])
            ax3.plot(timestamps, list(self.metrics_data['pod_counts']), 'r-', linewidth=2, marker='o')
            ax3.set_title('Browser Pod Scaling')
            ax3.set_ylabel('Number of Pods')
            ax3.grid(True)
            ax3.tick_params(axis='x', rotation=45)
            
            # Performance Metrics
            ax4 = fig.add_subplot(gs[1, 0])
            ax4.plot(timestamps, list(self.metrics_data['api_latency']), 'm-', linewidth=2)
            ax4.set_title('API Response Latency')
            ax4.set_ylabel('Latency (seconds)')
            ax4.grid(True)
            ax4.tick_params(axis='x', rotation=45)
            
            # HPA Metrics
            ax5 = fig.add_subplot(gs[1, 1])
            colors = ['blue', 'red', 'green']
            for i, (component, data) in enumerate(self.metrics_data['hpa_replicas'].items()):
                if data:
                    ax5.plot(timestamps, list(data), linewidth=2, marker='s', 
                            label=f'{component.title()} HPA', color=colors[i])
            ax5.set_title('HPA Replica Counts')
            ax5.set_ylabel('Number of Replicas')
            ax5.legend()
            ax5.grid(True)
            ax5.tick_params(axis='x', rotation=45)
            
            # Connection Metrics
            ax6 = fig.add_subplot(gs[1, 2])
            ax6.plot(timestamps, list(self.metrics_data['websocket_connections']), 
                    'c-', linewidth=2, marker='^', label='WebSocket Connections')
            ax6.plot(timestamps, list(self.metrics_data['active_sessions']), 
                    'orange', linewidth=2, marker='v', label='Active Sessions')
            ax6.set_title('Connection & Session Metrics')
            ax6.set_ylabel('Count')
            ax6.legend()
            ax6.grid(True)
            ax6.tick_params(axis='x', rotation=45)
            
            # Performance Distribution Charts
            if self.api_response_times:
                ax7 = fig.add_subplot(gs[2, 0])
                ax7.hist(list(self.api_response_times), bins=30, alpha=0.7, color='purple')
                ax7.set_title('API Response Time Distribution')
                ax7.set_xlabel('Response Time (seconds)')
                ax7.set_ylabel('Frequency')
                ax7.grid(True, alpha=0.3)
            
            if self.websocket_connection_times:
                ax8 = fig.add_subplot(gs[2, 1])
                ax8.hist(list(self.websocket_connection_times), bins=20, alpha=0.7, color='teal')
                ax8.set_title('WebSocket Connection Time Distribution')
                ax8.set_xlabel('Connection Time (seconds)')
                ax8.set_ylabel('Frequency')
                ax8.grid(True, alpha=0.3)
            
            # Summary Statistics
            ax9 = fig.add_subplot(gs[2, 2])
            ax9.axis('off')
            
            # Calculate statistics
            cpu_data = list(self.metrics_data['cpu_usage'])
            memory_data = list(self.metrics_data['memory_usage'])
            pod_data = list(self.metrics_data['pod_counts'])
            latency_data = list(self.metrics_data['api_latency'])
            
            stats_text = f"""Performance Summary
            
CPU Usage:
  Average: {np.mean(cpu_data):.2f} cores
  Peak: {np.max(cpu_data):.2f} cores
  
Memory Usage:
  Average: {np.mean(memory_data):.1f} MB
  Peak: {np.max(memory_data):.1f} MB
  
Pod Scaling:
  Average: {np.mean(pod_data):.1f} pods
  Maximum: {np.max(pod_data)} pods
  
API Latency:
  Average: {np.mean(latency_data):.3f}s
  95th Percentile: {np.percentile(latency_data, 95):.3f}s
  
Test Duration: {datetime.now() - self.start_time}
Total Measurements: {len(timestamps)}
"""
            ax9.text(0.1, 0.9, stats_text, transform=ax9.transAxes, fontsize=12,
                    verticalalignment='top', fontfamily='monospace',
                    bbox=dict(boxstyle="round,pad=0.5", facecolor="lightgray", alpha=0.8))
            
            # Combined metrics correlation plot
            ax10 = fig.add_subplot(gs[3, :])
            ax10_twin1 = ax10.twinx()
            ax10_twin2 = ax10.twinx()
            ax10_twin2.spines['right'].set_position(('outward', 60))
            
            line1 = ax10.plot(timestamps, list(self.metrics_data['cpu_usage']), 'b-', linewidth=2, label='CPU Usage')
            line2 = ax10_twin1.plot(timestamps, list(self.metrics_data['pod_counts']), 'r-', linewidth=2, label='Pod Count')
            line3 = ax10_twin2.plot(timestamps, list(self.metrics_data['active_sessions']), 'g-', linewidth=2, label='Active Sessions')
            
            ax10.set_title('Correlation: CPU Usage vs Pod Scaling vs Active Sessions')
            ax10.set_xlabel('Time')
            ax10.set_ylabel('CPU Usage (cores)', color='b')
            ax10_twin1.set_ylabel('Pod Count', color='r')
            ax10_twin2.set_ylabel('Active Sessions', color='g')
            
            # Combine legends
            lines = line1 + line2 + line3
            labels = [l.get_label() for l in lines]
            ax10.legend(lines, labels, loc='upper left')
            
            ax10.grid(True)
            ax10.tick_params(axis='x', rotation=45)
            
            # Format x-axis for all subplots
            for ax in [ax1, ax2, ax3, ax4, ax5, ax6, ax10]:
                if timestamps:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=2))
            
            # Save comprehensive report
            comprehensive_path = os.path.join(self.plots_dir, f'comprehensive_report_{timestamp_str}.png')
            fig.savefig(comprehensive_path, dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            logger.info(f"Comprehensive report saved to {comprehensive_path}")
            return comprehensive_path
            
        except Exception as e:
            logger.error(f"Error creating comprehensive report: {e}")
            return None
    
    def create_visualizations(self):
        """Create real-time visualizations"""
        fig, axes = plt.subplots(2, 3, figsize=(20, 12))
        fig.suptitle('KubeBrowse Performance Metrics', fontsize=16)
        
        def update_plots(frame):
            # Check if it's time to save plots
            if (datetime.now() - self.last_plot_save).total_seconds() >= self.plot_save_interval:
                self.save_current_visualization(f"_interval_{frame}")
                self.last_plot_save = datetime.now()
            
            if not self.metrics_data['timestamps']:
                return
            
            # Clear all axes
            for ax_row in axes:
                for ax in ax_row:
                    ax.clear()
            
            timestamps = list(self.metrics_data['timestamps'])
            
            # CPU Usage
            axes[0, 0].plot(timestamps, list(self.metrics_data['cpu_usage']), 'b-', linewidth=2)
            axes[0, 0].set_title('CPU Usage (Cores)')
            axes[0, 0].set_ylabel('CPU Cores')
            axes[0, 0].grid(True)
            axes[0, 0].tick_params(axis='x', rotation=45)
            
            # Memory Usage
            axes[0, 1].plot(timestamps, list(self.metrics_data['memory_usage']), 'g-', linewidth=2)
            axes[0, 1].set_title('Memory Usage (MB)')
            axes[0, 1].set_ylabel('Memory (MB)')
            axes[0, 1].grid(True)
            axes[0, 1].tick_params(axis='x', rotation=45)
            
            # Pod Counts
            axes[0, 2].plot(timestamps, list(self.metrics_data['pod_counts']), 'r-', linewidth=2, marker='o')
            axes[0, 2].set_title('Browser Pod Count')
            axes[0, 2].set_ylabel('Number of Pods')
            axes[0, 2].grid(True)
            axes[0, 2].tick_params(axis='x', rotation=45)
            
            # API Latency
            axes[1, 0].plot(timestamps, list(self.metrics_data['api_latency']), 'm-', linewidth=2)
            axes[1, 0].set_title('API Response Latency')
            axes[1, 0].set_ylabel('Latency (seconds)')
            axes[1, 0].grid(True)
            axes[1, 0].tick_params(axis='x', rotation=45)
            
            # HPA Replicas
            for component, data in self.metrics_data['hpa_replicas'].items():
                if data:
                    axes[1, 1].plot(timestamps, list(data), linewidth=2, marker='s', label=component)
            axes[1, 1].set_title('HPA Replica Counts')
            axes[1, 1].set_ylabel('Number of Replicas')
            axes[1, 1].legend()
            axes[1, 1].grid(True)
            axes[1, 1].tick_params(axis='x', rotation=45)
            
            # WebSocket Connections and Active Sessions
            axes[1, 2].plot(timestamps, list(self.metrics_data['websocket_connections']), 
                          'c-', linewidth=2, marker='^', label='WebSocket Connections')
            axes[1, 2].plot(timestamps, list(self.metrics_data['active_sessions']), 
                          'orange', linewidth=2, marker='v', label='Active Sessions')
            axes[1, 2].set_title('Connections & Sessions')
            axes[1, 2].set_ylabel('Count')
            axes[1, 2].legend()
            axes[1, 2].grid(True)
            axes[1, 2].tick_params(axis='x', rotation=45)
            
            # Format x-axis for all subplots
            for ax_row in axes:
                for ax in ax_row:
                    if timestamps:
                        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
                        ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
            
            plt.tight_layout()
        
        # Create animation
        ani = FuncAnimation(fig, update_plots, interval=5000, cache_frame_data=False)
        
        # Save initial plot
        self.save_current_visualization("_initial")
        
        return fig, ani
    
    def save_metrics_report(self):
        """Save metrics to CSV and generate summary report"""
        if not self.metrics_data['timestamps']:
            logger.warning("No metrics data to save")
            return
        
        # Create DataFrame
        df_data = {
            'timestamp': list(self.metrics_data['timestamps']),
            'cpu_usage': list(self.metrics_data['cpu_usage']),
            'memory_usage': list(self.metrics_data['memory_usage']),
            'pod_count': list(self.metrics_data['pod_counts']),
            'api_latency': list(self.metrics_data['api_latency']),
            'websocket_connections': list(self.metrics_data['websocket_connections']),
            'active_sessions': list(self.metrics_data['active_sessions']),
            'api_replicas': list(self.metrics_data['hpa_replicas']['api']),
            'frontend_replicas': list(self.metrics_data['hpa_replicas']['frontend']),
            'guacd_replicas': list(self.metrics_data['hpa_replicas']['guacd'])
        }
        
        df = pd.DataFrame(df_data)
        
        # Save to CSV
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'kubebrowse_metrics_{timestamp_str}.csv'
        df.to_csv(filename, index=False)
        
        # Generate summary report
        report = f"""
KubeBrowse Performance Report
============================
Test Duration: {datetime.now() - self.start_time}
Report Generated: {datetime.now()}

Performance Summary:
-------------------
Average CPU Usage: {df['cpu_usage'].mean():.2f} cores
Peak CPU Usage: {df['cpu_usage'].max():.2f} cores
Average Memory Usage: {df['memory_usage'].mean():.2f} MB
Peak Memory Usage: {df['memory_usage'].max():.2f} MB

Scaling Metrics:
---------------
Average Browser Pods: {df['pod_count'].mean():.1f}
Maximum Browser Pods: {df['pod_count'].max()}
Average API Replicas: {df['api_replicas'].mean():.1f}
Average Frontend Replicas: {df['frontend_replicas'].mean():.1f}

Latency Metrics:
---------------
Average API Latency: {df['api_latency'].mean():.3f} seconds
95th Percentile API Latency: {df['api_latency'].quantile(0.95):.3f} seconds
Average WebSocket Connection Time: {np.mean(self.websocket_connection_times) if self.websocket_connection_times else 0:.3f} seconds

Connection Metrics:
------------------
Peak Concurrent WebSocket Connections: {df['websocket_connections'].max()}
Peak Active Sessions: {df['active_sessions'].max()}
Total API Response Times Recorded: {len(self.api_response_times)}
Total WebSocket Connection Times Recorded: {len(self.websocket_connection_times)}

Files Generated:
---------------
Data File: {filename}
Plots Directory: {self.plots_dir}
"""
        
        report_filename = f'kubebrowse_report_{timestamp_str}.txt'
        with open(report_filename, 'w') as f:
            f.write(report)
        
        logger.info(f"Metrics saved to {filename}")
        logger.info(f"Report saved to {report_filename}")
        print(report)
        
        # Create final comprehensive visualization
        comprehensive_report_path = self.create_final_comprehensive_report()
        if comprehensive_report_path:
            logger.info(f"Comprehensive report: {comprehensive_report_path}")
        
        # Save final plot
        final_plot_path = self.save_current_visualization("_final")
        if final_plot_path:
            logger.info(f"Final plot: {final_plot_path}")
    
    async def run_benchmark(self, duration_minutes=10, concurrent_sessions=5, session_interval=30):
        """Run the complete benchmark test"""
        logger.info(f"Starting KubeBrowse benchmark for {duration_minutes} minutes")
        logger.info(f"Concurrent sessions: {concurrent_sessions}, Session interval: {session_interval}s")
        
        # Check if websocat is available
        try:
            websocat_check = subprocess.run(["websocat", "--version"], capture_output=True, text=True)
            if websocat_check.returncode != 0:
                logger.error("websocat is not installed or not in PATH")
                return
            logger.info(f"Using websocat: {websocat_check.stdout.strip()}")
        except FileNotFoundError:
            logger.error("websocat is not installed. Please install it first.")
            return
        
        # Start metrics collection in background thread
        metrics_thread = threading.Thread(target=self.collect_metrics, daemon=True)
        metrics_thread.start()
        
        # Start visualization
        fig, ani = self.create_visualizations()
        
        # Show plots in non-blocking mode
        plt.ion()
        plt.show()
        
        end_time = datetime.now() + timedelta(minutes=duration_minutes)
        session_count = 0
        
        try:
            while datetime.now() < end_time:
                logger.info(f"Creating batch {session_count + 1} of {concurrent_sessions} sessions")
                
                # Create concurrent sessions with websocat connections
                results = await self.create_concurrent_sessions(concurrent_sessions)
                successful_sessions = len(results)
                
                logger.info(f"Successfully created and connected {successful_sessions}/{concurrent_sessions} sessions")
                session_count += 1
                
                # Log current active processes
                active_processes = len([p for p in self.websocket_processes if p['process'].returncode is None])
                logger.info(f"Current active WebSocket processes: {active_processes}")
                
                # Wait before next batch
                await asyncio.sleep(session_interval)
                
                # Update plot
                plt.pause(0.1)
                
        except KeyboardInterrupt:
            logger.info("Benchmark interrupted by user")
        
        finally:
            # Clean up websocket processes
            logger.info("Cleaning up WebSocket processes...")
            cleanup_tasks = []
            for process_info in self.websocket_processes:
                if process_info['process'].returncode is None:
                    try:
                        process_info['process'].terminate()
                        cleanup_tasks.append(asyncio.create_task(
                            asyncio.wait_for(process_info['process'].wait(), timeout=5)
                        ))
                    except:
                        process_info['process'].kill()
            
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            logger.info("WebSocket cleanup completed")
            
            # Generate final report
            self.save_metrics_report()
            
            # Keep plots open
            logger.info("Benchmark completed. Plots will remain open. Press Ctrl+C to exit.")
            try:
                plt.ioff()
                plt.show()
            except KeyboardInterrupt:
                pass

async def main():
    """Main function to run the benchmark"""
    benchmark = KubeBrowseBenchmark()
    
    # Configuration
    DURATION_MINUTES = 15  # Run for 15 minutes
    CONCURRENT_SESSIONS = 100  # Create 100 sessions at a time
    SESSION_INTERVAL = 20  # Wait 20 seconds between batches
    logger.info(f"Running benchmark for {DURATION_MINUTES} minutes with {CONCURRENT_SESSIONS} concurrent sessions.")
    await benchmark.run_benchmark(
        duration_minutes=DURATION_MINUTES,
        concurrent_sessions=CONCURRENT_SESSIONS,
        session_interval=SESSION_INTERVAL
    )

if __name__ == "__main__":
    print("KubeBrowse Benchmarking System")
    print("==============================")
    print("This tool will monitor and visualize:")
    print("- Kubernetes cluster CPU/Memory usage")
    print("- Browser pod scaling")
    print("- HPA replica counts")
    print("- API response latency")
    print("- WebSocket connection metrics")
    print("- Active session counts")
    print()
    print("Make sure you have kubectl configured and the cluster is accessible.")
    print("Starting benchmark...")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBenchmark stopped by user.")
    except Exception as e:
        print(f"Benchmark failed: {e}")
        logger.error(f"Benchmark failed: {e}", exc_info=True)