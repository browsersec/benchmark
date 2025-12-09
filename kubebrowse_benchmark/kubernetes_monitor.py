"""
Kubernetes cluster monitoring functionality.
"""

import logging
from typing import Dict, Any, Optional

from kubernetes import client, config

logger = logging.getLogger(__name__)


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

