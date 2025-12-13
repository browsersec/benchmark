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

from .config import BenchmarkConfig, BenchmarkMode
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
  # Browser Session mode (default) - video streaming test
  %(prog)s --kubeconfig ~/.kube/config-prod --max-users 50
  %(prog)s --namespace my-namespace --save-interval 30
  %(prog)s --target-url http://example.com --test-duration 3600
  %(prog)s --sessions-api-url https://172.18.120.152:30006/sessions/ --sessions-api-insecure
  %(prog)s --browser-init-wait 5 --max-users 10 --session-start-interval 2
  
  # File Viewer mode - Office Session file upload/viewing test
  %(prog)s --mode file_viewer --temp-files-dir ./temp_files --max-users 10
  %(prog)s -m file_viewer --file-upload-interval 3 --office-session-init-wait 10
  %(prog)s --mode file_viewer --test-files sample1.pdf sample2.docx --max-users 5
  
  # Both modes - Run browser then file_viewer consecutively
  %(prog)s --mode both --max-users 20 --test-duration 900
  %(prog)s -m both --run-name my_full_test --output-dir ./results
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
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode (no visible window)'
    )
    parser.add_argument(
        '--no-headless',
        action='store_true',
        help='Run browser with visible window (default)'
    )
    parser.add_argument(
        '--session-duration',
        type=int,
        default=3600,
        help='How long each browser session stays open after interactions, in seconds (default: 3600 = 1 hour)'
    )
    
    # Benchmark mode selection
    parser.add_argument(
        '--mode', '-m',
        choices=['browser', 'file_viewer', 'both'],
        default='browser',
        help='Benchmark mode: "browser" for Browser Session (video streaming), "file_viewer" for Office Session (file upload/viewing), "both" to run both modes consecutively (default: browser)'
    )
    
    # File Viewer / Office Session specific settings
    parser.add_argument(
        '--temp-files-dir',
        type=str,
        default='temp_files',
        help='Directory containing test files for file viewer benchmark (default: temp_files)'
    )
    parser.add_argument(
        '--test-files',
        type=str,
        nargs='+',
        help='Specific files to upload in file viewer mode (space-separated list of filenames)'
    )
    parser.add_argument(
        '--file-upload-wait',
        type=float,
        default=2.0,
        help='Wait time after each file upload in seconds (default: 2.0)'
    )
    parser.add_argument(
        '--file-upload-interval',
        type=float,
        default=6.0,
        help='Delay between starting each file upload in seconds (default: 6.0)'
    )
    parser.add_argument(
        '--office-session-init-wait',
        type=float,
        default=5.0,
        help='Wait time for office session to initialize in seconds (default: 5.0)'
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
        default='benchmark_runs',
        help='Base output directory for benchmark runs (default: benchmark_runs)'
    )
    parser.add_argument(
        '--run-name',
        type=str,
        default=None,
        help='Custom name for this benchmark run (default: auto-generated with timestamp and number)'
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


def generate_run_folder(base_dir: str, run_name: str = None, benchmark_mode: str = "browser") -> str:
    """
    Generate a unique run folder path with run number and timestamp.
    
    Args:
        base_dir: Base directory for benchmark runs
        run_name: Optional custom run name
        benchmark_mode: 'browser' or 'file_viewer'
    
    Returns:
        Full path to the unique run folder
    
    Example folder names:
        benchmark_runs/run_001_browser_20251212_143000/
        benchmark_runs/run_002_file_viewer_20251212_144500/
        benchmark_runs/my_custom_run_browser_20251212_145000/
    """
    import re
    from datetime import datetime
    
    # Create base directory if it doesn't exist
    os.makedirs(base_dir, exist_ok=True)
    
    # Get current timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Mode suffix for folder naming
    mode_suffix = "browser" if benchmark_mode == "browser" else "file_viewer"
    
    if run_name:
        # Use custom run name with mode and timestamp
        # Sanitize the custom name (remove invalid chars)
        safe_name = re.sub(r'[^\w\-]', '_', run_name)
        run_folder_name = f"{safe_name}_{mode_suffix}_{timestamp}"
    else:
        # Auto-generate with run number
        # Find existing run folders to determine next run number
        existing_runs = []
        if os.path.exists(base_dir):
            for item in os.listdir(base_dir):
                if os.path.isdir(os.path.join(base_dir, item)):
                    # Match pattern: run_XXX_*
                    match = re.match(r'run_(\d{3})_', item)
                    if match:
                        existing_runs.append(int(match.group(1)))
        
        # Get next run number
        next_run_num = max(existing_runs) + 1 if existing_runs else 1
        
        # Create folder name with mode indicator
        mode_suffix = "browser" if benchmark_mode == "browser" else "file_viewer"
        run_folder_name = f"run_{next_run_num:03d}_{mode_suffix}_{timestamp}"
    
    run_folder_path = os.path.join(base_dir, run_folder_name)
    
    # Create the run folder
    os.makedirs(run_folder_path, exist_ok=True)
    
    return run_folder_path


def _create_run_info(config: BenchmarkConfig, args) -> None:
    """Create a run_info.json file with benchmark configuration and metadata"""
    import json
    from datetime import datetime
    
    run_info = {
        'run_start_time': datetime.now().isoformat(),
        'run_folder': config.output_dir,
        'benchmark_mode': 'file_viewer' if config.benchmark_mode == BenchmarkMode.FILE_VIEWER else 'browser',
        'configuration': {
            'target_url': config.target_url,
            'namespace': config.namespace,
            'max_concurrent_users': config.max_concurrent_users,
            'ramp_up_duration': config.ramp_up_duration,
            'test_duration': config.test_duration,
            'ramp_down_duration': config.ramp_down_duration,
            'polling_interval': config.polling_interval,
            'save_interval': config.save_interval,
            'browser_init_wait': config.browser_init_wait,
            'session_start_interval': config.session_start_interval,
            'session_duration': config.session_duration,
            'viewport': f"{config.viewport_width}x{config.viewport_height}",
            'headless': config.headless,
        },
        'kubernetes': {
            'kubeconfig_path': config.kubeconfig_path,
            'sessions_api_url': config.sessions_api_url,
            'sessions_monitoring_enabled': config.enable_sessions_monitoring,
        },
        'file_viewer_settings': {
            'temp_files_dir': config.temp_files_dir,
            'file_upload_interval': config.file_upload_interval,
            'office_session_init_wait': config.office_session_init_wait,
        } if config.benchmark_mode == BenchmarkMode.FILE_VIEWER else None,
        'command_line_args': vars(args) if hasattr(args, '__dict__') else str(args),
    }
    
    run_info_path = os.path.join(config.output_dir, 'run_info.json')
    with open(run_info_path, 'w') as f:
        json.dump(run_info, f, indent=2, default=str)
    
    logger.info(f"Created run info file: {run_info_path}")


def create_config_from_args(args, mode_override: str = None) -> BenchmarkConfig:
    """
    Create BenchmarkConfig from parsed arguments.
    
    Args:
        args: Parsed command line arguments
        mode_override: Optional mode override for running both modes consecutively
    
    Returns:
        BenchmarkConfig object
    """
    # Auto-enable sessions monitoring if API URL is provided
    enable_sessions = args.enable_sessions_monitoring or bool(args.sessions_api_url)
    
    # Determine the effective mode (use override if provided)
    effective_mode = mode_override if mode_override else args.mode
    
    # Parse benchmark mode (don't handle 'both' here - that's handled at a higher level)
    if effective_mode == 'file_viewer':
        benchmark_mode = BenchmarkMode.FILE_VIEWER
        mode_str = "file_viewer"
    else:
        benchmark_mode = BenchmarkMode.BROWSER_SESSION
        mode_str = "browser"
    
    # Generate unique run folder for this benchmark execution
    run_folder = generate_run_folder(
        base_dir=args.output_dir,
        run_name=args.run_name,
        benchmark_mode=mode_str
    )
    
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
        output_dir=run_folder,  # Use the generated unique run folder
        kubeconfig_path=args.kubeconfig,
        sessions_api_url=args.sessions_api_url,
        sessions_api_insecure=args.sessions_api_insecure,
        enable_sessions_monitoring=enable_sessions,
        browser_init_wait=args.browser_init_wait,
        session_start_interval=args.session_start_interval,
        viewport_width=args.viewport_width,
        viewport_height=args.viewport_height,
        headless=args.headless and not args.no_headless,
        session_duration=args.session_duration,
        # Benchmark mode
        benchmark_mode=benchmark_mode,
        # File viewer settings
        temp_files_dir=args.temp_files_dir,
        test_files=args.test_files,
        file_upload_wait=args.file_upload_wait,
        file_upload_interval=args.file_upload_interval,
        office_session_init_wait=args.office_session_init_wait
    )


async def run_single_benchmark(args, mode: str) -> str:
    """
    Run a single benchmark with the specified mode.
    
    Args:
        args: Parsed command line arguments
        mode: Benchmark mode ('browser' or 'file_viewer')
    
    Returns:
        Path to the metrics file
    """
    # Create configuration with mode override
    config = create_config_from_args(args, mode_override=mode)
    
    # Create run info file at the start of the benchmark
    _create_run_info(config, args)
    
    # Log benchmark mode - use WARNING level so it shows with --quiet
    mode_name = "Browser Session (video streaming)" if config.benchmark_mode == BenchmarkMode.BROWSER_SESSION else "Office Session (file viewer)"
    logger.warning(f"Benchmark mode: {mode_name}")
    logger.warning(f"Run folder: {config.output_dir}")
    
    if config.benchmark_mode == BenchmarkMode.FILE_VIEWER:
        logger.info(f"Test files directory: {config.temp_files_dir}")
        logger.info(f"File upload interval: {config.file_upload_interval} seconds")
        logger.info(f"Office session init wait: {config.office_session_init_wait} seconds")
    
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
    
    if config.save_visualizations:
        logger.info(f"Enhanced visualizations will be saved every {config.save_interval} seconds to {config.output_dir}/")
    
    # Run benchmark
    controller = LoadTestController(config)
    metrics_file = await controller.run_benchmark()
    
    # Generate final visualizations
    visualizer = BenchmarkVisualizer(metrics_file)
    visualizer.create_comprehensive_dashboard()
    
    logger.warning(f"{mode_name} benchmark completed successfully!")
    logger.warning(f"Results saved to: {config.output_dir}")
    
    return metrics_file


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
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting KubeBrowse comprehensive benchmark suite...")
    logger.info("Using non-interactive matplotlib backend for thread safety")
    logger.info("Using Playwright for browser automation")
    
    try:
        # Check if we need to run both modes
        if args.mode == 'both':
            # Use WARNING level so messages show even with --quiet
            logger.warning("=" * 60)
            logger.warning("Running BOTH benchmark modes consecutively")
            logger.warning("=" * 60)
            
            results = []
            
            # Run browser mode first
            logger.warning("")
            logger.warning("=" * 60)
            logger.warning("PHASE 1: Browser Session (video streaming) benchmark")
            logger.warning("=" * 60)
            browser_metrics = await run_single_benchmark(args, 'browser')
            results.append(('browser', browser_metrics))
            
            # Small pause between modes
            logger.warning("")
            logger.warning("=" * 60)
            logger.warning("Pausing 10 seconds before starting file viewer benchmark...")
            logger.warning("=" * 60)
            await asyncio.sleep(10)
            
            # Run file_viewer mode second
            logger.warning("")
            logger.warning("=" * 60)
            logger.warning("PHASE 2: Office Session (file viewer) benchmark")
            logger.warning("=" * 60)
            file_viewer_metrics = await run_single_benchmark(args, 'file_viewer')
            results.append(('file_viewer', file_viewer_metrics))
            
            # Summary
            logger.warning("")
            logger.warning("=" * 60)
            logger.warning("BOTH MODES COMPLETED SUCCESSFULLY!")
            logger.warning("=" * 60)
            for mode, metrics_file in results:
                logger.warning(f"  {mode}: {os.path.dirname(metrics_file)}")
            logger.warning("=" * 60)
            
        else:
            # Run single mode benchmark
            config = create_config_from_args(args)
            
            logger.info(f"Run folder: {config.output_dir}")
            logger.info(f"Configuration: {config}")
            
            # Create run info file at the start of the benchmark
            _create_run_info(config, args)
            
            # Log benchmark mode
            mode_name = "Browser Session (video streaming)" if config.benchmark_mode == BenchmarkMode.BROWSER_SESSION else "Office Session (file viewer)"
            logger.info(f"Benchmark mode: {mode_name}")
            
            if config.benchmark_mode == BenchmarkMode.FILE_VIEWER:
                logger.info(f"Test files directory: {config.temp_files_dir}")
                logger.info(f"File upload interval: {config.file_upload_interval} seconds")
                logger.info(f"Office session init wait: {config.office_session_init_wait} seconds")
            
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
            
            if config.save_visualizations:
                logger.info(f"Enhanced visualizations will be saved every {config.save_interval} seconds to {config.output_dir}/")
            
            # Run benchmark
            controller = LoadTestController(config)
            metrics_file = await controller.run_benchmark()
            
            # Generate final visualizations
            visualizer = BenchmarkVisualizer(metrics_file)
            visualizer.create_comprehensive_dashboard()
            
            logger.info("Benchmark completed successfully!")
            logger.info(f"All results saved to: {config.output_dir}")
            if config.save_visualizations:
                logger.info(f"Periodic snapshots are in: {config.output_dir}/snapshot_*/")
            logger.info("Check 'benchmark_results' directory for final comprehensive report")
        
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

