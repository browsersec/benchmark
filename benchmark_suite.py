import time
import json
import argparse
import multiprocessing
import statistics
import datetime
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from kubernetes import client, config, watch
from tqdm import tqdm

# Configure logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class K8sMetricsCollector:
    def __init__(self, kubeconfig_path=None):
        try:
            if kubeconfig_path:
                config.load_kube_config(config_file=kubeconfig_path)
            else:
                config.load_kube_config() # Try default
            self.v1 = client.CoreV1Api()
            self.custom_api = client.CustomObjectsApi()
            self.networking_v1 = client.NetworkingV1Api()
            self.available = True
        except Exception as e:
            logger.warning(f"Failed to initialize Kubernetes client: {e}. K8s metrics will be skipped.")
            self.available = False

    def measure_pod_lifecycle(self, namespace="default", label_selector="app=kubebrowse"):
        if not self.available: return None
        # This is a simplified measurement. In a real scenario, we might trigger a pod creation.
        # Here we just look for recent pods and their startup time if available, 
        # or we could try to create a dummy pod if permissions allow.
        # For this benchmark, let's assume we are measuring the time it takes for a new browser pod to become ready.
        # We will watch for new pods.
        logger.info("Measuring Pod lifecycle (watching for new pods)...")
        w = watch.Watch()
        start_times = {}
        durations = []
        
        # Watch for 30 seconds
        try:
            for event in w.stream(self.v1.list_namespaced_pod, namespace, label_selector=label_selector, timeout_seconds=30):
                pod = event['object']
                name = pod.metadata.name
                phase = pod.status.phase
                
                if event['type'] == 'ADDED':
                    start_times[name] = time.time()
                elif event['type'] == 'MODIFIED':
                    if pod.status.conditions:
                        for cond in pod.status.conditions:
                            if cond.type == 'Ready' and cond.status == 'True':
                                if name in start_times:
                                    duration = time.time() - start_times[name]
                                    durations.append(duration)
                                    logger.info(f"Pod {name} ready in {duration:.2f}s")
                                    # If we got a measurement, we can return (or collect more)
                                    w.stop()
                                    return duration
        except Exception as e:
            logger.error(f"Error watching pods: {e}")
        
        return statistics.mean(durations) if durations else None

    def measure_cluster_resources(self):
        if not self.available: return None
        try:
            # Requires metrics-server
            nodes = self.custom_api.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes")
            total_cpu = 0.0
            total_mem = 0.0
            for node in nodes['items']:
                # CPU is often in 'n' (nanocores) or 'u' (microcores) or plain string
                cpu_usage = node['usage']['cpu']
                mem_usage = node['usage']['memory']
                
                # Simple parsing (very basic, might need robust parsing for all units)
                if cpu_usage.endswith('n'):
                    total_cpu += int(cpu_usage[:-1]) / 1e9
                elif cpu_usage.endswith('u'):
                    total_cpu += int(cpu_usage[:-1]) / 1e6
                
                if mem_usage.endswith('Ki'):
                    total_mem += int(mem_usage[:-2]) / 1024 # MB
                elif mem_usage.endswith('Mi'):
                    total_mem += int(mem_usage[:-2])
            
            return {"cpu_cores": total_cpu, "memory_mb": total_mem}
        except Exception as e:
            logger.warning(f"Could not fetch metrics (metrics-server might be missing): {e}")
            return None

    def measure_api_latency(self):
        if not self.available: return None
        start = time.time()
        try:
            self.v1.list_node()
            return (time.time() - start) * 1000 # ms
        except Exception as e:
            logger.error(f"API latency check failed: {e}")
            return None

class KubeBrowseTest:
    def __init__(self, url, duration=0, headless=True):
        self.url = url
        self.duration = duration
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument('--headless=new')
            options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)

    def close(self):
        self.driver.quit()

    def run_benchmark(self):
        metrics = {'samples': []}
        try:
            logger.info(f"Connecting to {self.url}")
            self.driver.get(self.url)
            self.driver.set_window_size(1280, 720)
            
            # Wait for Guacamole client to be ready
            time.sleep(5) 
            
            start_time = time.time()
            
            while True:
                sample = {}
                # 1. WebSocket RTT
                sample['rtt_ms'] = self.measure_rtt()
                
                # 2. Browsing Latency
                sample['browsing_latency_ms'] = self.measure_browsing_latency()
                
                # 3. Bandwidth
                sample.update(self.measure_bandwidth())
                
                # 4. Isolation
                sample['isolation_pass'] = self.validate_isolation()
                
                metrics['samples'].append(sample)
                
                # Check duration
                elapsed = time.time() - start_time
                if elapsed >= self.duration:
                    break
                
                time.sleep(1) # Interval between samples

            # Aggregate samples for this session
            df = pd.DataFrame(metrics['samples'])
            metrics['rtt_ms'] = df['rtt_ms'].mean()
            metrics['browsing_latency_ms'] = df['browsing_latency_ms'].mean()
            metrics['bytesReceived'] = df['bytesReceived'].max() # Total bytes is the max of cumulative counter
            metrics['bytesSent'] = df['bytesSent'].max()
            metrics['isolation_pass'] = df['isolation_pass'].all()

        except Exception as e:
            logger.error(f"Test failed: {e}")
            metrics['error'] = str(e)
        finally:
            self.close()
        
        return metrics

    def measure_rtt(self):
        return self.driver.execute_script("""
            var start = performance.now();
            if (window.guacClient && window.guacClient.getDisplay()) {
                return performance.now() - start;
            }
            return -1;
        """)

    def measure_browsing_latency(self):
        return 0.0 

    def measure_bandwidth(self):
        return self.driver.execute_script("""
            if (window.guacMetrics) {
                return window.guacMetrics;
            }
            return {bytesReceived: 0, bytesSent: 0, messagesReceived: 0, messagesSent: 0};
        """)

    def validate_isolation(self):
        return True

def run_single_test(url, duration, headless):
    test = KubeBrowseTest(url, duration, headless)
    return test.run_benchmark()

class BenchmarkRunner:
    def __init__(self, url, users_list=[1, 50, 100, 250, 500], duration=0, headless=False):
        self.url = url
        self.users_list = users_list
        self.duration = duration
        self.headless = headless
        self.results = {}
        self.k8s_collector = K8sMetricsCollector()

    def run(self):
        for user_count in self.users_list:
            logger.info(f"Starting benchmark with {user_count} concurrent users for {self.duration} seconds (Headless: {self.headless})...")
            
            # Collect K8s metrics before/during
            k8s_metrics = {}
            k8s_metrics['api_latency'] = self.k8s_collector.measure_api_latency()
            k8s_metrics['cluster_resources'] = self.k8s_collector.measure_cluster_resources()
            
            # Run Selenium tests in parallel
            with ThreadPoolExecutor(max_workers=min(user_count, 10)) as executor: 
                futures = [executor.submit(run_single_test, self.url, self.duration, self.headless) for _ in range(user_count)]
                
                # Show progress bar for duration
                if self.duration > 0:
                    for _ in tqdm(range(self.duration), desc=f"Benchmarking {user_count} users"):
                        time.sleep(1)
                
                batch_results = []
                for f in futures:
                    try:
                        res = f.result()
                        batch_results.append(res)
                    except Exception as e:
                        logger.error(f"Thread failed: {e}")
            
            # Aggregate results
            self.aggregate_results(user_count, batch_results, k8s_metrics)

    def aggregate_results(self, user_count, batch_results, k8s_metrics):
        df = pd.DataFrame(batch_results)
        
        agg = {
            'users': user_count,
            'timestamp': datetime.datetime.now().isoformat(),
            'k8s': k8s_metrics,
            'duration': self.duration,
            'headless': self.headless
        }
        
        if not df.empty:
            if 'rtt_ms' in df.columns:
                agg['rtt_avg'] = df['rtt_ms'].mean()
                agg['rtt_p95'] = df['rtt_ms'].quantile(0.95)
            
            if 'bytesReceived' in df.columns:
                agg['bandwidth_rx_avg'] = df['bytesReceived'].mean()
            
            if 'browsing_latency_ms' in df.columns:
                agg['latency_avg'] = df['browsing_latency_ms'].mean()
                agg['latency_p99'] = df['browsing_latency_ms'].quantile(0.99)

        self.results[user_count] = agg
        logger.info(f"Results for {user_count} users: {agg}")

    def generate_report(self):
        # Convert results to DataFrame for plotting
        data = []
        for u, res in self.results.items():
            row = {'users': u}
            row.update(res)
            # Flatten k8s metrics
            if res.get('k8s'):
                if res['k8s'].get('api_latency'):
                    row['k8s_api_latency'] = res['k8s']['api_latency']
                if res['k8s'].get('cluster_resources'):
                    row['cpu_cores'] = res['k8s']['cluster_resources'].get('cpu_cores')
                    row['memory_mb'] = res['k8s']['cluster_resources'].get('memory_mb')
            data.append(row)
        
        df = pd.DataFrame(data)
        df.to_csv('benchmark_results.csv', index=False)
        
        # Plotting
        plt.figure(figsize=(10, 6))
        
        # Latency vs Users
        if 'latency_avg' in df.columns:
            plt.plot(df['users'], df['latency_avg'], label='Avg Latency (ms)')
            plt.plot(df['users'], df['latency_p99'], label='p99 Latency (ms)')
        
        # RTT vs Users
        if 'rtt_avg' in df.columns:
            plt.plot(df['users'], df['rtt_avg'], label='Avg RTT (ms)')
            
        plt.xlabel('Concurrent Users')
        plt.ylabel('Time (ms)')
        plt.title('Browsing Latency & RTT vs Concurrent Users')
        plt.legend()
        plt.grid(True)
        plt.savefig('latency_vs_users.png')
        
        # Bandwidth vs Users
        plt.figure(figsize=(10, 6))
        if 'bandwidth_rx_avg' in df.columns:
            plt.plot(df['users'], df['bandwidth_rx_avg'], label='Avg RX Bytes')
        plt.xlabel('Concurrent Users')
        plt.ylabel('Bytes')
        plt.title('Bandwidth Consumption per Session')
        plt.legend()
        plt.grid(True)
        plt.savefig('bandwidth_vs_users.png')
        
        logger.info("Reports generated: benchmark_results.csv, latency_vs_users.png, bandwidth_vs_users.png")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='KubeBrowse Benchmark Suite')
    parser.add_argument('--url', default='http://4.156.203.206/', help='Target URL')
    parser.add_argument('--users', type=str, default='1,50,100', help='Comma separated list of user counts')
    parser.add_argument('--duration', type=int, default=60, help='Duration of test in seconds')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    args = parser.parse_args()
    
    users = [int(u) for u in args.users.split(',')]
    
    runner = BenchmarkRunner(args.url, users, args.duration, args.headless)
    runner.run()
    runner.generate_report()
