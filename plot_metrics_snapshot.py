#!/usr/bin/env python3
"""
Standalone Metrics Snapshot Visualizer
======================================
Generate visualizations from saved metrics snapshot JSON files.
"""

import json
import os
import sys
import argparse
from datetime import datetime
from typing import Dict, Any

# Core libraries
import pandas as pd
import numpy as np
# Set matplotlib backend before importing pyplot to avoid GUI issues
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px

import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SnapshotVisualizer:
    """Create visualizations from metrics snapshot JSON files"""
    
    def __init__(self, json_file: str):
        self.json_file = json_file
        with open(json_file, 'r') as f:
            self.data = json.load(f)
        
        # Convert timestamps
        self.timestamps = [datetime.fromisoformat(ts) for ts in self.data['timestamps']]
        
        # Ensure we're using non-interactive backend
        matplotlib.use('Agg')
        plt.ioff()
        
        logger.info(f"Loaded metrics snapshot with {len(self.timestamps)} data points")
    
    def create_comprehensive_dashboard(self, output_dir: str = None):
        """Create enhanced dashboard visualization with console errors"""
        if output_dir is None:
            output_dir = os.path.dirname(self.json_file)
        
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            fig, axes = plt.subplots(3, 3, figsize=(20, 15))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            fig.suptitle(f'KubeBrowse Comprehensive Performance Dashboard - {timestamp}', fontsize=16, fontweight='bold')
            
            # Node CPU Usage
            self._plot_node_cpu_usage(axes[0, 0])
            
            # Node Memory Usage
            self._plot_node_memory_usage(axes[0, 1])
            
            # Running Pods
            self._plot_running_pods(axes[0, 2])
            
            # API Active Sessions
            self._plot_api_sessions(axes[1, 0])
            
            # Session Summary
            self._plot_session_summary(axes[1, 1])
            
            # Response Times
            self._plot_response_times(axes[1, 2])
            
            # HPA Replica Counts
            self._plot_hpa_replicas(axes[2, 0])
            
            # API vs Browser Sessions Correlation
            self._plot_sessions_correlation(axes[2, 1])
            
            # Success Rate Over Time
            self._plot_success_rate(axes[2, 2])
            
            plt.tight_layout()
            
            # Save the dashboard
            dashboard_file = f"{output_dir}/comprehensive_dashboard.png"
            plt.savefig(dashboard_file, dpi=300, bbox_inches='tight', facecolor='white', edgecolor='none')
            logger.info(f"Dashboard saved to {dashboard_file}")
            
            # Properly close the figure to free memory
            plt.close(fig)
            plt.clf()
            
        except Exception as plot_error:
            logger.error(f"Error creating dashboard plot: {plot_error}")
            try:
                plt.close('all')
                plt.clf()
            except:
                pass
    
    def _plot_node_cpu_usage(self, ax):
        """Plot node CPU usage"""
        ax.set_title('Node CPU Usage (%)')
        ax.set_xlabel('Time Points')
        ax.set_ylabel('CPU %')
        ax.grid(True, alpha=0.3)
        
        if self.data['node_metrics']:
            total_timestamps = len(self.timestamps)
            for node_name, metrics in self.data['node_metrics'].items():
                if metrics['cpu_percent']:
                    # Ensure data length matches timestamps
                    cpu_data = metrics['cpu_percent']
                    data_length = min(len(cpu_data), total_timestamps)
                    time_points = list(range(data_length))
                    ax.plot(time_points, cpu_data[:data_length], 
                           label=f'{node_name}', marker='o', markersize=3)
            ax.legend()
    
    def _plot_node_memory_usage(self, ax):
        """Plot node memory usage"""
        ax.set_title('Node Memory Usage (%)')
        ax.set_xlabel('Time Points')
        ax.set_ylabel('Memory %')
        ax.grid(True, alpha=0.3)
        
        if self.data['node_metrics']:
            total_timestamps = len(self.timestamps)
            for node_name, metrics in self.data['node_metrics'].items():
                if metrics['memory_percent']:
                    # Ensure data length matches timestamps
                    memory_data = metrics['memory_percent']
                    data_length = min(len(memory_data), total_timestamps)
                    time_points = list(range(data_length))
                    ax.plot(time_points, memory_data[:data_length], 
                           label=f'{node_name}', marker='s', markersize=3)
            ax.legend()
    
    def _plot_running_pods(self, ax):
        """Plot running pods"""
        ax.set_title('Running Pods')
        ax.set_xlabel('Time Points')
        ax.set_ylabel('Pod Count')
        ax.grid(True, alpha=0.3)
        
        if self.data['pod_counts']:
            # Ensure pod_counts length matches timestamps
            total_timestamps = len(self.timestamps)
            pod_data = self.data['pod_counts']
            data_length = min(len(pod_data), total_timestamps)
            time_points = list(range(data_length))
            ax.plot(time_points, pod_data[:data_length], 
                   color='blue', marker='o', markersize=4)
            ax.fill_between(time_points, pod_data[:data_length], alpha=0.3)
    
    def _plot_api_sessions(self, ax):
        """Plot API active sessions"""
        ax.set_title('API Active Sessions')
        ax.set_xlabel('Time Points')
        ax.set_ylabel('Active Sessions')
        ax.grid(True, alpha=0.3)
        
        if self.data['api_sessions']:
            total_timestamps = len(self.timestamps)
            api_data = self.data['api_sessions']
            data_length = min(len(api_data), total_timestamps)
            time_points = list(range(data_length))
            
            active_sessions = [api_data[i].get('active_sessions', 0) for i in range(data_length)]
            total_connections = [api_data[i].get('total_connections', 0) for i in range(data_length)]
            
            ax.plot(time_points, active_sessions, 
                   color='green', marker='o', markersize=4, label='Active Sessions')
            ax.plot(time_points, total_connections, 
                   color='orange', marker='s', markersize=4, label='Total Connections')
            ax.legend()
            ax.fill_between(time_points, active_sessions, alpha=0.3, color='green')
    
    def _plot_session_summary(self, ax):
        """Plot session summary"""
        ax.set_title('Session Summary')
        ax.set_xlabel('Status')
        ax.set_ylabel('Count')
        ax.grid(True, alpha=0.3)
        
        if self.data['session_metrics']:
            total_sessions = len(self.data['session_metrics'])
            successful_sessions = sum(1 for s in self.data['session_metrics'] 
                                    if s.get('failed_api_calls', 0) == 0)
            failed_sessions = total_sessions - successful_sessions
            
            ax.bar(['Successful', 'Failed'], 
                  [successful_sessions, failed_sessions],
                  color=['green', 'red'], alpha=0.7)
    
    def _plot_response_times(self, ax):
        """Plot response times"""
        ax.set_title('Recent Response Times')
        ax.set_xlabel('Recent Sessions')
        ax.set_ylabel('Response Time (s)')
        ax.grid(True, alpha=0.3)
        
        if self.data['session_metrics']:
            recent_sessions = self.data['session_metrics'][-20:]
            response_times = [s.get('first_click_response_time', 0) 
                            for s in recent_sessions 
                            if s.get('first_click_response_time') is not None]
            
            if response_times:
                ax.plot(range(len(response_times)), response_times, 
                       'go-', markersize=4)
                ax.axhline(y=np.mean(response_times), 
                          color='red', linestyle='--', 
                          label=f'Avg: {np.mean(response_times):.2f}s')
                ax.legend()
    
    def _plot_hpa_replicas(self, ax):
        """Plot HPA replica counts"""
        ax.set_title('HPA Replica Counts')
        ax.set_xlabel('Time Points')
        ax.set_ylabel('Replicas')
        ax.grid(True, alpha=0.3)
        
        if self.data['hpa_metrics']:
            total_timestamps = len(self.timestamps)
            for hpa_name, metrics in self.data['hpa_metrics'].items():
                if metrics['current_replicas']:
                    # Ensure data length matches timestamps
                    current_data = metrics['current_replicas']
                    desired_data = metrics['desired_replicas']
                    data_length = min(len(current_data), len(desired_data), total_timestamps)
                    time_points = list(range(data_length))
                    
                    ax.plot(time_points, current_data[:data_length], 
                           label=f'{hpa_name} Current', marker='o', markersize=3)
                    ax.plot(time_points, desired_data[:data_length], 
                           label=f'{hpa_name} Desired', marker='s', markersize=3, linestyle='--')
            ax.legend()
    
    def _plot_sessions_correlation(self, ax):
        """Plot API vs Browser sessions correlation"""
        ax.set_title('API vs Browser Sessions')
        ax.set_xlabel('Time Points')
        ax.set_ylabel('Session Count')
        ax.grid(True, alpha=0.3)
        
        if self.data['api_sessions'] and self.data['session_metrics']:
            total_timestamps = len(self.timestamps)
            api_data = self.data['api_sessions']
            data_length = min(len(api_data), total_timestamps)
            time_points = list(range(data_length))
            
            api_sessions = [api_data[i].get('active_sessions', 0) for i in range(data_length)]
            
            # Calculate browser sessions over time (cumulative)
            browser_sessions_count = []
            for i in range(data_length):
                if i < len(self.timestamps):
                    current_time = self.timestamps[i]
                    active_browser_sessions = sum(1 for s in self.data['session_metrics'] 
                                                if datetime.fromisoformat(s['start_time']) <= current_time and 
                                                   (s.get('end_time') is None or datetime.fromisoformat(s['end_time']) >= current_time))
                    browser_sessions_count.append(active_browser_sessions)
                else:
                    browser_sessions_count.append(0)
            
            ax.plot(time_points, api_sessions, 
                   color='green', marker='o', markersize=4, label='API Active Sessions')
            ax.plot(time_points, browser_sessions_count, 
                   color='blue', marker='s', markersize=4, label='Browser Sessions')
            ax.legend()
    
    def _plot_success_rate(self, ax):
        """Plot success rate over time"""
        ax.set_title('Success Rate Over Time')
        ax.set_xlabel('Time Buckets')
        ax.set_ylabel('Success Rate (%)')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 105)
        
        if self.data['session_metrics'] and len(self.data['session_metrics']) > 5:
            bucket_size = max(1, len(self.data['session_metrics']) // 10)
            success_rates = []
            
            for i in range(0, len(self.data['session_metrics']), bucket_size):
                bucket = self.data['session_metrics'][i:i+bucket_size]
                total_calls = sum(s.get('total_api_calls', 0) for s in bucket)
                failed_calls = sum(s.get('failed_api_calls', 0) for s in bucket)
                
                if total_calls > 0:
                    success_rate = ((total_calls - failed_calls) / total_calls) * 100
                    success_rates.append(success_rate)
            
            if success_rates:
                ax.plot(range(len(success_rates)), success_rates, 
                       'b-o', markersize=4)
                ax.axhline(y=np.mean(success_rates), 
                          color='green', linestyle='--', 
                          label=f'Avg: {np.mean(success_rates):.1f}%')
                ax.legend()
    
    def create_individual_plots(self, output_dir: str = None):
        """Create individual detailed plots"""
        if output_dir is None:
            output_dir = os.path.dirname(self.json_file)
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Node metrics plot
        self._create_node_metrics_plot(output_dir)
        
        # Pod scaling plot
        self._create_pod_scaling_plot(output_dir)
        
        # HPA metrics plot
        self._create_hpa_metrics_plot(output_dir)
        
        # Performance metrics plot
        self._create_performance_metrics_plot(output_dir)
        
        # Session analysis plot
        self._create_session_analysis_plot(output_dir)

    def _create_node_metrics_plot(self, output_dir: str):
        """Create detailed node metrics plot as two separate plots"""
        if not self.data['node_metrics']:
            return

        total_timestamps = len(self.timestamps)

        # First plot: CPU Usage
        plt.figure(figsize=(12, 8))
        plt.suptitle('Kubernetes Node CPU Usage', fontsize=16, fontweight='bold')

        for node_name, metrics in self.data['node_metrics'].items():
            # Ensure all metric arrays are aligned with timestamps
            cpu_usage_data = metrics['cpu_usage'][:total_timestamps]

            # Use the minimum length to avoid index errors
            data_length = min(len(cpu_usage_data), total_timestamps)
            aligned_timestamps = self.timestamps[:data_length]

            # CPU Usage (Cores)
            plt.plot(aligned_timestamps, cpu_usage_data[:data_length], 
                    label=f'{node_name}', linewidth=2, marker='o', markersize=3)
            
        # Add statistic
        if cpu_usage_data:
            avg_cpu_usage = np.mean(cpu_usage_data)
            plt.axhline(y=avg_cpu_usage, color='green', linestyle='--', 
                        label=f'Avg: {avg_cpu_usage:.1f} Cores')
            max_cpu_usage = np.max(cpu_usage_data)
            plt.text(0.02, 0.98, f'Max CPU Usage: {max_cpu_usage:.1f} Cores\nAvg CPU Usage: {avg_cpu_usage:.1f} Cores',
                    transform=plt.gca().transAxes, fontsize=11, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        plt.title('CPU Usage (Cores)', fontweight='bold')
        plt.ylabel('CPU Cores')
        plt.xlabel('Time')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f'{output_dir}/node_cpu_usage.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Node CPU usage plot saved to {output_dir}/node_cpu_usage.png")

        # Second plot: Memory Usage
        plt.figure(figsize=(12, 8))
        plt.suptitle('Kubernetes Node Memory Usage', fontsize=16, fontweight='bold')

        for node_name, metrics in self.data['node_metrics'].items():
            # Ensure all metric arrays are aligned with timestamps
            memory_usage_data = metrics['memory_usage'][:total_timestamps]

            # Use the minimum length to avoid index errors
            data_length = min(len(memory_usage_data), total_timestamps)
            aligned_timestamps = self.timestamps[:data_length]

            # Memory Usage (GB)
            plt.plot(aligned_timestamps, memory_usage_data[:data_length], 
                    label=f'{node_name}', linewidth=2, marker='s', markersize=3)
        
        # Add statistic
        if memory_usage_data:
            avg_memory_usage = np.mean(memory_usage_data)
            plt.axhline(y=avg_memory_usage, color='green', linestyle='--', 
                        label=f'Avg: {avg_memory_usage:.1f} GB')
            max_memory_usage = np.max(memory_usage_data)
            plt.text(0.02, 0.98, f'Max Memory Usage: {max_memory_usage:.1f} GB\nAvg Memory Usage: {avg_memory_usage:.1f} GB',
                    transform=plt.gca().transAxes, fontsize=11, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        plt.title('Memory Usage (GB)', fontweight='bold')
        plt.ylabel('Memory (GB)')
        plt.xlabel('Time')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f'{output_dir}/node_memory_usage.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Node Memory usage plot saved to {output_dir}/node_memory_usage.png")

    # def _create_node_metrics_plot(self, output_dir: str):
    #     """Create detailed node metrics plot"""
    #     if not self.data['node_metrics']:
    #         return
            
    #     fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    #     fig.suptitle('Kubernetes Node Resource Usage', fontsize=16, fontweight='bold')
        
    #     total_timestamps = len(self.timestamps)
        
    #     for node_name, metrics in self.data['node_metrics'].items():
    #         # Ensure all metric arrays are aligned with timestamps
    #         cpu_usage_data = metrics['cpu_usage'][:total_timestamps]
    #         memory_usage_data = metrics['memory_usage'][:total_timestamps]
    #         cpu_percent_data = metrics['cpu_percent'][:total_timestamps]
    #         memory_percent_data = metrics['memory_percent'][:total_timestamps]
            
    #         # Use the minimum length to avoid index errors
    #         data_length = min(len(cpu_usage_data), len(memory_usage_data), 
    #                         len(cpu_percent_data), len(memory_percent_data), total_timestamps)
    #         aligned_timestamps = self.timestamps[:data_length]
            
    #         # CPU Usage (Cores)
    #         axes[0, 0].plot(aligned_timestamps, cpu_usage_data[:data_length], 
    #                       label=f'{node_name}', linewidth=2, marker='o', markersize=3)
            
    #         # Memory Usage (GB)
    #         axes[0, 1].plot(aligned_timestamps, memory_usage_data[:data_length], 
    #                       label=f'{node_name}', linewidth=2, marker='s', markersize=3)
            
    #         # CPU Usage (%)
    #         axes[1, 0].plot(aligned_timestamps, cpu_percent_data[:data_length], 
    #                       label=f'{node_name}', linewidth=2, marker='^', markersize=3)
            
    #         # Memory Usage (%)
    #         axes[1, 1].plot(aligned_timestamps, memory_percent_data[:data_length], 
    #                       label=f'{node_name}', linewidth=2, marker='d', markersize=3)
        
    #     # Customize subplots
    #     axes[0, 0].set_title('CPU Usage (Cores)', fontweight='bold')
    #     axes[0, 0].set_ylabel('CPU Cores')
    #     axes[0, 0].legend()
    #     axes[0, 0].grid(True, alpha=0.3)
        
    #     axes[0, 1].set_title('Memory Usage (GB)', fontweight='bold')
    #     axes[0, 1].set_ylabel('Memory (GB)')
    #     axes[0, 1].legend()
    #     axes[0, 1].grid(True, alpha=0.3)
        
    #     axes[1, 0].set_title('CPU Usage (%)', fontweight='bold')
    #     axes[1, 0].set_ylabel('CPU Utilization (%)')
    #     axes[1, 0].set_xlabel('Time')
    #     axes[1, 0].legend()
    #     axes[1, 0].grid(True, alpha=0.3)
        
    #     axes[1, 1].set_title('Memory Usage (%)', fontweight='bold')
    #     axes[1, 1].set_ylabel('Memory Utilization (%)')
    #     axes[1, 1].set_xlabel('Time')
    #     axes[1, 1].legend()
    #     axes[1, 1].grid(True, alpha=0.3)
        
    #     # Format x-axis
    #     for ax in axes.flat:
    #         ax.tick_params(axis='x', rotation=45)
        
    #     plt.tight_layout()
    #     plt.savefig(f'{output_dir}/node_metrics_detailed.png', dpi=300, bbox_inches='tight')
    #     plt.close()
    #     logger.info(f"Node metrics plot saved to {output_dir}/node_metrics_detailed.png")
    
    def _create_pod_scaling_plot(self, output_dir: str):
        """Create detailed pod scaling plot"""
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Ensure pod counts are aligned with timestamps
        total_timestamps = len(self.timestamps)
        pod_data = self.data['pod_counts']
        data_length = min(len(pod_data), total_timestamps)
        aligned_timestamps = self.timestamps[:data_length]
        aligned_pod_counts = pod_data[:data_length]
        
        # Plot browser sandbox pods
        ax.plot(aligned_timestamps, aligned_pod_counts, 
               linewidth=3, marker='o', markersize=6, color='#2E86AB',
               label='Browser Sandbox Pods')
        
        # Add fill area
        ax.fill_between(aligned_timestamps, aligned_pod_counts, 
                       alpha=0.3, color='#2E86AB')
        
        ax.set_title('Browser Sandbox Pod Scaling Over Time', 
                    fontsize=16, fontweight='bold', pad=20)
        ax.set_xlabel('Time', fontsize=12)
        ax.set_ylabel('Number of Running Pods', fontsize=12)
        ax.legend(fontsize=12)
        ax.grid(True, alpha=0.3)
        
        # Add statistics
        max_pods = max(aligned_pod_counts)
        avg_pods = np.mean(aligned_pod_counts)
        ax.axhline(y=avg_pods, color='red', linestyle='--', alpha=0.7, 
                  label=f'Average: {avg_pods:.1f}')
        ax.text(0.02, 0.98, f'Max Pods: {max_pods}\nAvg Pods: {avg_pods:.1f}', 
               transform=ax.transAxes, fontsize=11, verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(f'{output_dir}/pod_scaling_detailed.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Pod scaling plot saved to {output_dir}/pod_scaling_detailed.png")
    
    # TODO: need to make changes here
    # def _create_hpa_metrics_plot(self, output_dir: str):
    #     """Create detailed HPA metrics plot"""
    #     if not self.data['hpa_metrics']:
    #         logger.warning("No HPA metrics available")
    #         return
            
    #     n_hpas = len(self.data['hpa_metrics'])
    #     fig, axes = plt.subplots(n_hpas, 2, figsize=(16, 6 * n_hpas))
    #     if n_hpas == 1:
    #         axes = axes.reshape(1, -1)
        
    #     fig.suptitle('HPA Scaling Metrics', fontsize=16, fontweight='bold')
        
    #     total_timestamps = len(self.timestamps)
        
    #     for i, (hpa_name, metrics) in enumerate(self.data['hpa_metrics'].items()):
    #         # Ensure all HPA metric arrays are aligned with timestamps
    #         current_replicas = metrics['current_replicas']
    #         desired_replicas = metrics['desired_replicas']
    #         cpu_utilization = metrics['cpu_utilization']
    #         memory_utilization = metrics['memory_utilization']
            
    #         data_length = min(len(current_replicas), len(desired_replicas), 
    #                         len(cpu_utilization), len(memory_utilization), total_timestamps)
    #         aligned_timestamps = self.timestamps[:data_length]
            
    #         # Replica counts
    #         axes[i, 0].plot(aligned_timestamps, current_replicas[:data_length], 
    #                       label='Current Replicas', linewidth=2, marker='o', color='#1f77b4')
    #         axes[i, 0].plot(aligned_timestamps, desired_replicas[:data_length], 
    #                       label='Desired Replicas', linewidth=2, marker='s', color='#ff7f0e')
    #         axes[i, 0].set_title(f'{hpa_name} - Replica Scaling', fontweight='bold')
    #         axes[i, 0].set_ylabel('Replicas')
    #         axes[i, 0].legend()
    #         axes[i, 0].grid(True, alpha=0.3)
            
    #         # Resource utilization
    #         axes[i, 1].plot(aligned_timestamps, cpu_utilization[:data_length], 
    #                       label='CPU Utilization %', linewidth=2, marker='^', color='#2ca02c')
    #         axes[i, 1].plot(aligned_timestamps, memory_utilization[:data_length], 
    #                       label='Memory Utilization %', linewidth=2, marker='d', color='#d62728')
    #         axes[i, 1].axhline(y=50, color='red', linestyle='--', alpha=0.5, label='Target (50%)')
    #         axes[i, 1].set_title(f'{hpa_name} - Resource Utilization', fontweight='bold')
    #         axes[i, 1].set_ylabel('Utilization (%)')
    #         axes[i, 1].legend()
    #         axes[i, 1].grid(True, alpha=0.3)
            
    #         # Format x-axis
    #         axes[i, 0].tick_params(axis='x', rotation=45)
    #         axes[i, 1].tick_params(axis='x', rotation=45)
        
    #     plt.tight_layout()
    #     plt.savefig(f'{output_dir}/hpa_metrics_detailed.png', dpi=300, bbox_inches='tight')
    #     plt.close()
    #     logger.info(f"HPA metrics plot saved to {output_dir}/hpa_metrics_detailed.png")

    def _create_hpa_metrics_plot(self, output_dir: str):
        """Create detailed HPA metrics plot as separate plots"""
        if not self.data['hpa_metrics']:
            logger.warning("No HPA metrics available")
            return

        total_timestamps = len(self.timestamps)

        for hpa_name, metrics in self.data['hpa_metrics'].items():
            # Ensure all HPA metric arrays are aligned with timestamps
            current_replicas = metrics['current_replicas']
            desired_replicas = metrics['desired_replicas']
            cpu_utilization = metrics['cpu_utilization']
            memory_utilization = metrics['memory_utilization']

            data_length = min(len(current_replicas), len(desired_replicas), 
                            len(cpu_utilization), len(memory_utilization), total_timestamps)
            aligned_timestamps = self.timestamps[:data_length]

            # First plot: Replica Scaling
            plt.figure(figsize=(12, 8))
            plt.suptitle(f'HPA Replica Scaling - {hpa_name}', fontsize=16, fontweight='bold')

            plt.plot(aligned_timestamps, current_replicas[:data_length], 
                    label='Current Replicas', linewidth=2, marker='o', color='#1f77b4')
            plt.plot(aligned_timestamps, desired_replicas[:data_length], 
                    label='Desired Replicas', linewidth=2, marker='s', color='#ff7f0e')

            plt.title(f'{hpa_name} - Replica Scaling', fontweight='bold')
            plt.ylabel('Replicas')
            plt.xlabel('Time')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()

            # Save replica scaling plot
            safe_hpa_name = hpa_name.replace('/', '_').replace(':', '_')
            plt.savefig(f'{output_dir}/hpa_replicas_{safe_hpa_name}.png', dpi=300, bbox_inches='tight')
            plt.close()
            logger.info(f"HPA replica scaling plot saved to {output_dir}/hpa_replicas_{safe_hpa_name}.png")

            # Second plot: Resource Utilization
            plt.figure(figsize=(12, 8))
            plt.suptitle(f'HPA Resource Utilization - {hpa_name}', fontsize=16, fontweight='bold')

            plt.plot(aligned_timestamps, cpu_utilization[:data_length], 
                    label='CPU Utilization %', linewidth=2, marker='^', color='#2ca02c')
            plt.plot(aligned_timestamps, memory_utilization[:data_length], 
                    label='Memory Utilization %', linewidth=2, marker='d', color='#d62728')
            plt.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='Target (50%)')

            plt.title(f'{hpa_name} - Resource Utilization', fontweight='bold')
            plt.ylabel('Utilization (%)')
            plt.xlabel('Time')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()

            # Save resource utilization plot
            plt.savefig(f'{output_dir}/hpa_utilization_{safe_hpa_name}.png', dpi=300, bbox_inches='tight')
            plt.close()
            logger.info(f"HPA resource utilization plot saved to {output_dir}/hpa_utilization_{safe_hpa_name}.png")

        # Create a combined overview plot for all HPAs (optional)
        if len(self.data['hpa_metrics']) > 1:
            # Combined Replica Overview
            plt.figure(figsize=(14, 8))
            plt.suptitle('All HPAs - Replica Scaling Overview', fontsize=16, fontweight='bold')

            for hpa_name, metrics in self.data['hpa_metrics'].items():
                current_replicas = metrics['current_replicas']
                data_length = min(len(current_replicas), total_timestamps)
                aligned_timestamps = self.timestamps[:data_length]

                plt.plot(aligned_timestamps, current_replicas[:data_length], 
                        label=f'{hpa_name} - Current', linewidth=2, marker='o')

            plt.title('Current Replicas - All HPAs', fontweight='bold')
            plt.ylabel('Replicas')
            plt.xlabel('Time')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(f'{output_dir}/hpa_overview_replicas.png', dpi=300, bbox_inches='tight')
            plt.close()
            logger.info(f"HPA overview plot saved to {output_dir}/hpa_overview_replicas.png")

            # Combined Utilization Overview
            plt.figure(figsize=(14, 8))
            plt.suptitle('All HPAs - CPU Utilization Overview', fontsize=16, fontweight='bold')

            for hpa_name, metrics in self.data['hpa_metrics'].items():
                cpu_utilization = metrics['cpu_utilization']
                data_length = min(len(cpu_utilization), total_timestamps)
                aligned_timestamps = self.timestamps[:data_length]

                plt.plot(aligned_timestamps, cpu_utilization[:data_length], 
                        label=f'{hpa_name}', linewidth=2, marker='^')

            plt.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='Target (50%)')
            plt.title('CPU Utilization - All HPAs', fontweight='bold')
            plt.ylabel('CPU Utilization (%)')
            plt.xlabel('Time')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
            plt.tight_layout()
            plt.savefig(f'{output_dir}/hpa_overview_cpu.png', dpi=300, bbox_inches='tight')
            plt.close()
            logger.info(f"HPA CPU overview plot saved to {output_dir}/hpa_overview_cpu.png")

    def _create_performance_metrics_plot(self, output_dir: str):
        """Create detailed performance metrics plot"""
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
        plt.savefig(f'{output_dir}/performance_metrics_detailed.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Performance metrics plot saved to {output_dir}/performance_metrics_detailed.png")
    
    def _create_session_analysis_plot(self, output_dir: str):
        """Create detailed session analysis plot"""
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
        plt.savefig(f'{output_dir}/session_analysis_detailed.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info(f"Session analysis plot saved to {output_dir}/session_analysis_detailed.png")
    
    def create_interactive_dashboard(self, output_dir: str = None):
        """Create interactive Plotly dashboard"""
        if output_dir is None:
            output_dir = os.path.dirname(self.json_file)
        
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
        
        interactive_file = f'{output_dir}/interactive_dashboard.html'
        fig.write_html(interactive_file)
        logger.info(f"Interactive dashboard saved to {interactive_file}")
    
    def generate_summary_report(self, output_dir: str = None):
        """Generate summary report with key metrics"""
        if output_dir is None:
            output_dir = os.path.dirname(self.json_file)
        
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
        summary_file = f'{output_dir}/benchmark_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Create readable report
        markdown_file = f'{output_dir}/benchmark_report.md'
        with open(markdown_file, 'w') as f:
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
        
        logger.info(f"Summary report saved to {summary_file}")
        logger.info(f"Markdown report saved to {markdown_file}")

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Generate visualizations from metrics snapshot JSON files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s metrics_snapshot.json
  %(prog)s /path/to/snapshot_001_20250615_235444/metrics_snapshot.json --output-dir results
  %(prog)s metrics_snapshot.json --dashboard-only
  %(prog)s metrics_snapshot.json --individual-plots --interactive
        """
    )
    
    parser.add_argument(
        'json_file',
        type=str,
        help='Path to metrics snapshot JSON file'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        help='Output directory for generated plots (default: same directory as JSON file)'
    )
    
    parser.add_argument(
        '--dashboard-only',
        action='store_true',
        help='Generate only the comprehensive dashboard (default: generate all plots)'
    )
    
    parser.add_argument(
        '--individual-plots',
        action='store_true',
        help='Generate individual detailed plots'
    )
    
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Generate interactive Plotly dashboard'
    )
    
    parser.add_argument(
        '--summary-report',
        action='store_true',
        help='Generate summary report'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Generate all types of visualizations and reports'
    )
    
    return parser.parse_args()

def main():
    """Main function"""
    args = parse_arguments()
    
    # Validate input file
    if not os.path.exists(args.json_file):
        logger.error(f"JSON file not found: {args.json_file}")
        sys.exit(1)
    
    # Create visualizer
    try:
        visualizer = SnapshotVisualizer(args.json_file)
    except Exception as e:
        logger.error(f"Failed to load metrics snapshot: {e}")
        sys.exit(1)
    
    # Determine output directory
    output_dir = args.output_dir or os.path.dirname(args.json_file)
    
    # Generate visualizations based on arguments
    try:
        if args.all:
            logger.info("Generating all visualizations and reports...")
            visualizer.create_comprehensive_dashboard(output_dir)
            visualizer.create_individual_plots(output_dir)
            visualizer.create_interactive_dashboard(output_dir)
            visualizer.generate_summary_report(output_dir)
        else:
            if args.dashboard_only or (not args.individual_plots and not args.interactive and not args.summary_report):
                logger.info("Generating comprehensive dashboard...")
                visualizer.create_comprehensive_dashboard(output_dir)
            
            if args.individual_plots:
                logger.info("Generating individual detailed plots...")
                visualizer.create_individual_plots(output_dir)
            
            if args.interactive:
                logger.info("Generating interactive dashboard...")
                visualizer.create_interactive_dashboard(output_dir)
            
            if args.summary_report:
                logger.info("Generating summary report...")
                visualizer.generate_summary_report(output_dir)
        
        logger.info(f"All visualizations saved to: {output_dir}")
        
    except Exception as e:
        logger.error(f"Failed to generate visualizations: {e}")
        sys.exit(1)
    finally:
        # Clean up matplotlib state
        try:
            plt.close('all')
            plt.clf()
        except:
            pass

if __name__ == "__main__":
    main()
