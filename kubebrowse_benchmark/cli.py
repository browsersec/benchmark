"""
Command line interface and argument parsing.
"""

import os
import sys
import signal
import logging
import argparse
import asyncio

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from .config import BenchmarkConfig
from .controller import LoadTestController
from .visualization import BenchmarkVisualizer

logger = logging.getLogger(__name__)


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
        default='http://localhost:5173/',
        help='Target URL for load testing (default: http://localhost:5173/)'
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
    parser.add_argument(
        '--viewport-width',
        type=int,
        default=1280,
        help='Browser viewport width in pixels (default: 1280)'
    )
    parser.add_argument(
        '--viewport-height',
        type=int,
        default=720,
        help='Browser viewport height in pixels (default: 720)'
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
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output (sets log level to DEBUG)'
    )
    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Suppress most output (sets log level to WARNING)'
    )
    parser.add_argument(
        '--log-file',
        type=str,
        default='kubebrowse_benchmark.log',
        help='Log file path (default: kubebrowse_benchmark.log)'
    )
    parser.add_argument(
        '--no-log-file',
        action='store_true',
        help='Disable logging to file (console only)'
    )
    
    return parser.parse_args()


def setup_logging(log_level: str, log_file: str, no_log_file: bool = False):
    """Setup logging configuration"""
    # Clear existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # Setup handlers
    handlers = [logging.StreamHandler()]
    if not no_log_file and log_file:
        handlers.append(logging.FileHandler(log_file))
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=handlers
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
        session_start_interval=args.session_start_interval,
        viewport_width=args.viewport_width,
        viewport_height=args.viewport_height
    )


async def async_main():
    """Async main function to run the benchmark"""
    # Set matplotlib backend at the very beginning
    matplotlib.use('Agg')
    plt.ioff()
    
    # Parse command line arguments
    args = parse_arguments()
    
    # Determine log level (verbose and quiet override --log-level)
    if args.verbose:
        log_level = 'DEBUG'
    elif args.quiet:
        log_level = 'WARNING'
    else:
        log_level = args.log_level
    
    # Setup logging
    setup_logging(log_level, args.log_file, args.no_log_file)
    
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
    logger.info("Using Playwright for browser automation")
    
    if config.save_visualizations:
        logger.info(f"Enhanced visualizations will be saved every {config.save_interval} seconds to {config.output_dir}/")
    
    try:
        # Run benchmark
        controller = LoadTestController(config)
        metrics_file = await controller.run_benchmark()
        
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
        except Exception:
            pass


def main():
    """Entry point that runs the async main function"""
    asyncio.run(async_main())

