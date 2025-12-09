#!/usr/bin/env python3
"""
KubeBrowse Comprehensive Benchmarking Suite
===========================================
This file is a backwards-compatible wrapper for the kubebrowse_benchmark package.

For development, the code has been split into multiple modules in the 
kubebrowse_benchmark/ directory:
  - config.py          : BenchmarkConfig, MetricPoint, SessionMetrics
  - kubernetes_monitor.py : KubernetesMonitor
  - websocket_tester.py   : WebSocketTester
  - browser_simulator.py  : BrowserSimulator
  - sessions_monitor.py   : SessionsAPIMonitor
  - metrics_collector.py  : MetricsCollector
  - visualization.py      : PeriodicVisualizationSaver, BenchmarkVisualizer
  - controller.py         : LoadTestController
  - cli.py                : CLI functions and main entry point

Usage:
  python kubebrowse_benchmark.py [options]
  python -m kubebrowse_benchmark [options]
"""

# Re-export all classes and functions from the package for backwards compatibility
from kubebrowse_benchmark import (
    BenchmarkConfig,
    MetricPoint,
    SessionMetrics,
    KubernetesMonitor,
    WebSocketTester,
    BrowserSimulator,
    SessionsAPIMonitor,
    MetricsCollector,
    PeriodicVisualizationSaver,
    BenchmarkVisualizer,
    LoadTestController,
)

from kubebrowse_benchmark.cli import (
    main,
    async_main,
    parse_arguments,
    setup_logging,
    validate_kubeconfig,
    create_config_from_args,
    signal_handler,
)

__all__ = [
    'BenchmarkConfig',
    'MetricPoint',
    'SessionMetrics',
    'KubernetesMonitor',
    'WebSocketTester',
    'BrowserSimulator',
    'SessionsAPIMonitor',
    'MetricsCollector',
    'PeriodicVisualizationSaver',
    'BenchmarkVisualizer',
    'LoadTestController',
    'main',
    'async_main',
    'parse_arguments',
    'setup_logging',
    'validate_kubeconfig',
    'create_config_from_args',
    'signal_handler',
]

if __name__ == "__main__":
    main()
