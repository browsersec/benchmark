"""
Load test controller functionality.
"""

import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, List

from tqdm import tqdm

from .config import BenchmarkConfig, SessionMetrics, BenchmarkMode
from .browser_simulator import BrowserSimulator
from .file_viewer_simulator import FileViewerSimulator
from .metrics_collector import MetricsCollector
from .visualization import PeriodicVisualizationSaver

logger = logging.getLogger(__name__)


class LoadTestController:
    """Control the load testing process"""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.metrics_collector = MetricsCollector(config)
        self.visualization_saver = PeriodicVisualizationSaver(self.metrics_collector, config) if config.save_visualizations else None
        self.active_sessions: Dict[str, asyncio.Task] = {}
        self.completed_sessions = []
        self.running = False
        self.last_session_start_time = 0  # Track last session start time
        
    async def run_benchmark(self):
        """Run the complete benchmark test"""
        logger.info("Starting KubeBrowse benchmark...")
        
        # Start metrics collection
        self.metrics_collector.start_collection()
        
        # Start periodic visualization saving
        if self.visualization_saver:
            self.visualization_saver.start_saving()
        
        self.running = True
        tasks = []
        
        # Calculate total test time for progress bar
        total_time = (self.config.ramp_up_duration + 
                     self.config.test_duration + 
                     self.config.ramp_down_duration)
        
        # Create main progress bar for overall benchmark
        main_pbar = tqdm(
            total=total_time,
            desc="🚀 Benchmark Progress",
            unit="s",
            bar_format="{l_bar}{bar}| {n:.0f}/{total:.0f}s [{elapsed}<{remaining}]",
            colour="green"
        )
        
        # Create status bar for sessions
        session_pbar = tqdm(
            total=self.config.max_concurrent_users,
            desc="👥 Active Sessions",
            unit="sessions",
            bar_format="{desc}: {n}/{total} | Completed: {postfix}",
            colour="blue",
            position=1,
            leave=True
        )
        session_pbar.set_postfix_str("0")
        
        try:
            user_schedule = self._calculate_user_schedule()
            
            start_time = time.time()
            last_progress_update = start_time
            
            for schedule_time, user_count in user_schedule:
                # Wait until schedule time with progress updates
                while time.time() - start_time < schedule_time and self.running:
                    await asyncio.sleep(0.1)
                    
                    # Update progress bar every 0.5 seconds
                    current_time = time.time()
                    if current_time - last_progress_update >= 0.5:
                        elapsed = current_time - start_time
                        main_pbar.n = min(elapsed, total_time)
                        main_pbar.refresh()
                        
                        # Update phase description
                        if elapsed < self.config.ramp_up_duration:
                            main_pbar.set_description("📈 Ramp Up")
                        elif elapsed < self.config.ramp_up_duration + self.config.test_duration:
                            main_pbar.set_description("⚡ Steady State")
                        else:
                            main_pbar.set_description("📉 Ramp Down")
                        
                        last_progress_update = current_time
                
                if not self.running:
                    break
                    
                # Start new sessions to reach target user count with controlled intervals
                current_active = len(self.active_sessions)
                if user_count > current_active:
                    new_sessions = user_count - current_active
                    logger.info(f"Starting {new_sessions} new sessions with {self.config.session_start_interval}s interval")
                    
                    # Progress bar for spawning sessions
                    spawn_pbar = tqdm(
                        total=new_sessions,
                        desc="  🌐 Spawning",
                        unit="session",
                        leave=False,
                        position=2,
                        colour="cyan"
                    )
                    
                    for i in range(new_sessions):
                        # Enforce session start interval
                        current_time = time.time()
                        time_since_last_start = current_time - self.last_session_start_time
                        
                        if time_since_last_start < self.config.session_start_interval:
                            wait_time = self.config.session_start_interval - time_since_last_start
                            logger.debug(f"Waiting {wait_time:.2f}s before starting next session")
                            await asyncio.sleep(wait_time)
                        
                        session_id = f"user_{len(self.completed_sessions) + len(self.active_sessions) + i + 1}"
                        
                        # Create appropriate simulator based on benchmark mode
                        simulator = self._create_simulator(session_id)
                        
                        task = asyncio.create_task(self._run_session(simulator))
                        tasks.append(task)
                        self.active_sessions[session_id] = task
                        self.last_session_start_time = time.time()
                        
                        spawn_pbar.update(1)
                        logger.debug(f"Started session {session_id} at {datetime.now().strftime('%H:%M:%S')}")
                    
                    spawn_pbar.close()
                
                # Clean up completed sessions
                self._cleanup_completed_sessions()
                
                # Update session progress bar
                session_pbar.n = len(self.active_sessions)
                session_pbar.set_postfix_str(str(len(self.completed_sessions)))
                session_pbar.refresh()
                
                logger.debug(f"Active sessions: {len(self.active_sessions)}, "
                           f"Completed: {len(self.completed_sessions)}")
            
            # Final progress update
            main_pbar.n = total_time
            main_pbar.set_description("✅ Test Complete")
            main_pbar.refresh()
            
            # Wait for all sessions to complete
            main_pbar.set_description("⏳ Waiting for sessions")
            logger.info("Waiting for all sessions to complete...")
            
            if tasks:
                # Create completion progress bar
                completion_pbar = tqdm(
                    total=len(tasks),
                    desc="🏁 Completing",
                    unit="session",
                    position=2,
                    colour="yellow"
                )
                
                for coro in asyncio.as_completed(tasks):
                    try:
                        result = await coro
                        if isinstance(result, SessionMetrics):
                            self.completed_sessions.append(result)
                            self.metrics_collector.add_session_metrics(result)
                        completion_pbar.update(1)
                        session_pbar.set_postfix_str(str(len(self.completed_sessions)))
                        session_pbar.refresh()
                    except Exception as e:
                        logger.error(f"Session failed: {e}")
                        completion_pbar.update(1)
                
                completion_pbar.close()
                        
        except KeyboardInterrupt:
            logger.info("Benchmark interrupted by user")
        finally:
            self.running = False
            self.metrics_collector.stop_collection()
            
            # Stop visualization saving
            if self.visualization_saver:
                self.visualization_saver.stop_saving()
            
            # Close progress bars
            main_pbar.set_description("✅ Benchmark Done")
            main_pbar.close()
            session_pbar.close()
            
        logger.info(f"Benchmark completed. Total sessions: {len(self.completed_sessions)}")
        return self.metrics_collector.save_metrics()
    
    def _calculate_user_schedule(self) -> List[tuple]:
        """Calculate when to start/stop users during test"""
        schedule = []
        
        # Ramp up phase - more frequent scheduling to respect session intervals
        ramp_up_steps = max(10, self.config.ramp_up_duration // 30)  # At least every 30 seconds
        for i in range(ramp_up_steps):
            time_point = i * (self.config.ramp_up_duration / ramp_up_steps)
            user_count = int((i + 1) * self.config.max_concurrent_users / ramp_up_steps)
            schedule.append((time_point, user_count))
        
        # Steady state phase
        steady_start = self.config.ramp_up_duration
        for i in range(self.config.test_duration // 60):  # Every minute during steady state
            time_point = steady_start + i * 60
            schedule.append((time_point, self.config.max_concurrent_users))
        
        # Ramp down phase
        ramp_down_start = self.config.ramp_up_duration + self.config.test_duration
        ramp_down_steps = max(10, self.config.ramp_down_duration // 30)
        for i in range(ramp_down_steps):
            time_point = ramp_down_start + i * (self.config.ramp_down_duration / ramp_down_steps)
            user_count = int(self.config.max_concurrent_users * 
                           (1 - (i + 1) / ramp_down_steps))
            schedule.append((time_point, max(0, user_count)))
        
        return schedule
    
    async def _run_session(self, simulator: BrowserSimulator) -> SessionMetrics:
        """Run a single browser session"""
        try:
            return await simulator.run_session()
        except Exception as e:
            logger.error(f"Session {simulator.session_id} failed: {e}")
            simulator.metrics.errors.append(f"Session failed: {e}")
            simulator.metrics.end_time = datetime.now()
            return simulator.metrics
        # Note: Browser is intentionally not closed here to keep windows open
    
    def _create_simulator(self, session_id: str):
        """Create appropriate simulator based on benchmark mode"""
        if self.config.benchmark_mode == BenchmarkMode.FILE_VIEWER:
            return FileViewerSimulator(self.config, session_id)
        else:
            return BrowserSimulator(self.config, session_id)
    
    def _cleanup_completed_sessions(self):
        """Remove completed sessions from active tracking"""
        completed_keys = []
        for session_id, task in self.active_sessions.items():
            if task.done():
                completed_keys.append(session_id)
                
        for key in completed_keys:
            del self.active_sessions[key]

