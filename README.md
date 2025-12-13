# benchmark
benchmarking for kubebrowse


```
uv pip install asyncio aiohttp websockets matplotlib pandas numpy requests pyyaml webdriver-manager selenium
```

TEST

```
python kubebrowse_benchmark.py \
    --namespace browser-sandbox \
    --max-users 50 \
    --test-duration 3600 \
    --save-interval 30 \
    --target-url http://4.4.4.4/ \
    --browser-init-wait 20 \
    --sessions-api-url "https://172.18.120.152:30006/sessions/" \
    --sessions-api-insecure
```

TEST 2

```
python kubebrowse_benchmark.py \
    --kubeconfig ~/benchmark/proxmox.yml \
    --namespace browser-sandbox \
    --max-users 50 \
    --test-duration 3600 \
    --save-interval 30 \
    --target-url http://172.18.120.162/ \
    --browser-init-wait 40 \
    --sessions-api-url "https://172.18.120.152:30006/sessions/" \
    --sessions-api-insecure \
    --session-start-interval 10 \
    --test-duration 600
```

TEST3 

```python
uv run kubebrowse_benchmark.py \
    --namespace browser-sandbox \
    --max-users 5 \
    --ramp-up-duration 10 \
    --ramp-down-duration 10 \
    --target-url http://localhost:5173/ \
    --browser-init-wait 40 \
    --sessions-api-url "https://localhost:4567/sessions/" \
    --sessions-api-insecure \
    --session-start-interval 10 \
    --test-duration 600 \
    --save-interval 30 \ 
    --quiet
```
TEST4

```
uv run kubebrowse_benchmark.py \
    --namespace browser-sandbox \
    --max-users 500 \
    --ramp-up-duration 10 \
    --ramp-down-duration 10 \
    --target-url http://192.168.122.2/ \
    --browser-init-wait 40 \
    --sessions-api-url "https://192.168.122.1/sessions/" \
    --sessions-api-insecure \
    --session-start-interval 10 \
    --test-duration 600 \
    --save-interval 30 \ 
    --quiet
    --headless
```

TEST5

```
uv run kubebrowse_benchmark.py \
    --namespace browser-sandbox \
    --max-users 500 \
    --ramp-up-duration 30000 \
    --ramp-down-duration 60 \
    --target-url http://192.168.122.2/ \
    --browser-init-wait 40 \
    --sessions-api-url "https://192.168.122.3:4567/sessions/" \
    --sessions-api-insecure \
    --session-start-interval 20 \
    --test-duration 600 \
    --save-interval 30 \
    --quiet \
    --headless
```
TEST6
```
uv run kubebrowse_benchmark.py \
    --namespace browser-sandbox \
    --max-users 500 \
    --ramp-up-duration 3000 \
    --ramp-down-duration 30 \
    --target-url http://192.168.122.2/ \
    --browser-init-wait 40 \
    --sessions-api-url "https://192.168.122.3:4567/sessions/" \
    --sessions-api-insecure \
    --session-start-interval 6 \
    --session-duration 1200 \
    --test-duration 60 \
    --save-interval 30 \
    --quiet \
    --headless
```

---
```
uv run kubebrowse_benchmark.py  --mode browser   --namespace browser-sandbox     --max-users 500     --ramp-up-duration 3000     --ramp-down-duration 30     --target-url http://192.168.122.221/     --browser-init-wait 40     --sessions-api-url "https://192.168.122.220:80/sessions/"     --sessions-api-insecure     --session-start-interval 20    --session-duration 1200     --test-duration 60     --save-interval 30     --quiet    --headless  --run-name browser-test-v1

```

---

File viewer tests 

```python
uv run kubebrowse_benchmark.py \
    --mode file_viewer \
    --namespace browser-sandbox \
    --max-users 500 \
    --ramp-up-duration 3000 \
    --ramp-down-duration 30 \
    --target-url http://192.168.122.221/ \
    --browser-init-wait 40 \
    --sessions-api-url "https://192.168.122.220:80/sessions/" \
    --sessions-api-insecure \
    --session-start-interval 20 \
    --session-duration 3600 \
    --test-duration 60 \
    --save-interval 30 \
    --quiet \
    --headless \
    --temp-files-dir ./temp_files \
    --file-upload-interval 6 \
    --office-session-init-wait 12 \
    --run-name file-test-v1
```


both mode 

```python
uv run kubebrowse_benchmark.py \
    --mode both \
    --quiet \
    --run-name both-test-v1 \
    --namespace browser-sandbox \
    --max-users 500 \
    --ramp-up-duration 3000 \
    --ramp-down-duration 30 \
    --target-url http://192.168.122.221/ \
    --browser-init-wait 40 \
    --sessions-api-url "https://192.168.122.220:80/sessions/" \
    --sessions-api-insecure \
    --session-start-interval 20 \
    --session-duration 1200 \
    --test-duration 60 \
    --save-interval 30 \
    --headless \
    --temp-files-dir ./temp_files \
    --file-upload-interval 6 \
    --office-session-init-wait 12 
```
---

## Pod Distribution Heat Map

The benchmark now includes comprehensive pod distribution heat maps that distinguish between:

### Pod Types (based on container names)
- **Browser Pods** (`rdp-chromium`): Created by `CreateBrowserSandboxPod` in `internal/k8s/browser.go`
- **File Viewer Pods** (`rdp-onlyoffice`): Created by `CreateOfficeSandboxPod` in `internal/k8s/office.go`

Both pod types use the label `app=browser-sandbox-test` as defined in `deployments/manifest.yml`.

### Generated Visualizations

The benchmark generates the following pod distribution visualizations in each snapshot:

1. **`sandbox_pod_type_heatmap.png`** - Comprehensive heat map with:
   - Pod type counts over time (Browser vs File Viewer)
   - Separate heat maps for browser pods (blue) and file viewer pods (green)
   - Current pod distribution bar chart by node
   - Pie chart of pod type distribution

2. **`pod_distribution.png`** - Enhanced with:
   - All pods status by node (running/pending/failed)
   - Sandbox pod types by node (Browser vs File Viewer)
   - Overall pod status pie chart
   - Sandbox pod type distribution pie chart

3. **`combined_pod_heatmap.png`** - Shows:
   - Total sandbox pod density across nodes over time
   - Pod type ratio heat map (Blue=Browser, Green=File Viewer)

4. **`pod_density_heatmap.png`** - Pod density across nodes over time

### Summary Report

The summary text file now includes pod type breakdown:
```
Pod Type Breakdown:
  Browser Pods (rdp-chromium):
    Current: X
    Max: Y
    Avg: Z
  File Viewer Pods (rdp-onlyoffice):
    Current: X
    Max: Y
    Avg: Z
```

---

## WebSocket RTT (Round-Trip Time) Metrics

The benchmark now tracks WebSocket round-trip time (RTT) for Guacamole RDP stream connections. This measures the actual latency of the remote desktop streaming.

### How RTT is Measured

RTT is measured from **two sources** for comprehensive coverage:

#### 1. Playwright Frame Interception (Benchmark Tool)
- Playwright intercepts WebSocket frames during Guacamole sessions
- Timestamps are recorded for each frame send/receive
- RTT is calculated from frame send/receive timing patterns

#### 2. Frontend Metrics Reporting (Production Sessions)
- Frontend `useWebSocketMetrics` hook tracks RTT in real-time
- Metrics are reported to backend API endpoint
- Backend aggregates RTT across all active sessions

### Backend API Endpoints

The Go backend provides these endpoints for WebSocket metrics:

```
POST /sessions/:connectionID/metrics  - Report metrics from frontend
GET  /sessions/:connectionID/metrics  - Get metrics for a session
GET  /sessions/:connectionID/metrics/history - Get historical metrics
GET  /metrics/websocket              - Get all sessions' metrics
GET  /metrics/websocket/summary      - Get aggregated summary
```

### Frontend Integration

The frontend uses `useWebSocketMetrics` hook in `useGuacWebSocket.js`:

```javascript
// RTT metrics are automatically tracked and exposed globally
window.guacWebSocketMetrics.getMetrics()  // Get current metrics
window.guacWebSocketMetrics.getRttSamples()  // Get raw RTT samples
```

### RTT Data Captured

For each session:
- `websocket_rtt_samples`: Individual RTT measurements (ms)
- `websocket_rtt_avg`: Average RTT (ms)
- `websocket_rtt_min`: Minimum RTT (ms)
- `websocket_rtt_max`: Maximum RTT (ms)
- `websocket_rtt_p50`: Median RTT (ms)
- `websocket_rtt_p95`: 95th percentile RTT (ms)
- `websocket_rtt_p99`: 99th percentile RTT (ms)
- `websocket_frames_sent`: Total WebSocket frames sent
- `websocket_frames_received`: Total WebSocket frames received
- `websocket_bytes_sent`: Total bytes sent
- `websocket_bytes_received`: Total bytes received

### Generated Visualizations

**`websocket_rtt.png`** - Comprehensive RTT analysis with:
- RTT Distribution Histogram with mean, median, P95 markers
- RTT Box Plot with statistical summary
- RTT Over Time (average, P95, P99)
- WebSocket Traffic Summary (frames and bytes)
- Per-Session RTT Comparison (up to 20 sessions)
- RTT Percentile Distribution Bar Chart

### Summary Report Output

```
WEBSOCKET RTT METRICS
========================================
Sessions with RTT data: 50
Total RTT samples: 12500

RTT Statistics:
  Average:  45.23 ms
  Median:   42.15 ms
  Std Dev:  18.67 ms
  Min:      8.32 ms
  Max:      215.44 ms

RTT Percentiles:
  P50:  42.15 ms
  P75:  55.82 ms
  P90:  68.44 ms
  P95:  78.91 ms
  P99:  112.33 ms

WebSocket Traffic:
  Frames Sent:     125,000
  Frames Received: 842,000
  Bytes Sent:      2.45 MB
  Bytes Received:  156.78 MB
  Total Traffic:   159.23 MB
```

---

Visualization Instructions:
==========================

## Benchmark Run Folder Structure

Each benchmark run creates a unique folder with timestamp and run number:

```
benchmark_runs/
├── run_001_browser_20251212_143000/
│   ├── run_info.json              # Run configuration and metadata
│   ├── snapshot_001_20251212_143030/
│   │   ├── dashboard.png
│   │   ├── metrics_snapshot.json
│   │   ├── summary.txt
│   │   ├── pod_distribution.png
│   │   ├── sandbox_pod_type_heatmap.png
│   │   ├── websocket_rtt.png
│   │   └── ...
│   ├── snapshot_002_20251212_143100/
│   │   └── ...
│   └── ...
├── run_002_file_viewer_20251212_144500/
│   ├── run_info.json
│   └── ...
└── my_custom_run_20251212_145000/   # Custom named run
    └── ...
```

### Command Line Options

```bash
# Default: Creates folder like benchmark_runs/run_001_browser_TIMESTAMP/
uv run kubebrowse_benchmark.py --max-users 10

# Custom base directory
uv run kubebrowse_benchmark.py --output-dir my_benchmarks --max-users 10

# Custom run name (instead of auto-numbered)
uv run kubebrowse_benchmark.py --run-name stress_test_v1 --max-users 50
# Creates: benchmark_runs/stress_test_v1_20251212_143000/

# File viewer mode (auto-detected in folder name)
uv run kubebrowse_benchmark.py --mode file_viewer --max-users 10
# Creates: benchmark_runs/run_001_file_viewer_TIMESTAMP/

# Both modes - Run browser then file_viewer consecutively
uv run kubebrowse_benchmark.py --mode both --max-users 20 --test-duration 900
# Creates two separate run folders:
#   benchmark_runs/run_001_browser_TIMESTAMP/
#   benchmark_runs/run_002_file_viewer_TIMESTAMP/
```

## Benchmark Modes

The benchmark supports four modes:

### 1. Browser Mode (default)
Tests browser/RDP streaming sessions with video playback:
```bash
uv run kubebrowse_benchmark.py --mode browser --max-users 50
```

### 2. File Viewer Mode
Tests Office Session with file upload and viewing:
```bash
uv run kubebrowse_benchmark.py --mode file_viewer --max-users 10
```

### 3. Both Modes (Consecutive)
Runs browser mode first, then file viewer mode with a 10-second pause between:
```bash
uv run kubebrowse_benchmark.py --mode both --max-users 20 --test-duration 600
```

This creates separate run folders for each mode, allowing you to compare performance
across different workload types in a single benchmark session.

### 4. Mixed Mode (Simultaneous)
Runs both browser and file viewer sessions **simultaneously** with configurable ratio:
```bash
# 50% browser, 50% file viewer (default)
uv run kubebrowse_benchmark.py --mode mixed --max-users 20

# 70% browser, 30% file viewer
uv run kubebrowse_benchmark.py --mode mixed --mixed-ratio 0.7 --max-users 30

# 30% browser, 70% file viewer
uv run kubebrowse_benchmark.py --mode mixed --mixed-ratio 0.3 --max-users 20
```

The `--mixed-ratio` parameter controls the proportion of browser sessions:
- `0.5` = 50% browser, 50% file viewer (default)
- `0.7` = 70% browser, 30% file viewer
- `0.3` = 30% browser, 70% file viewer

**Visual timeline (mixed mode):**
```
Browser pods:      ████  ████  ████  ████  ████  ████  (60% with ratio=0.6)
File viewer pods:    ████    ████    ████    ████      (40% with ratio=0.6)
                  └──────────── Time ─────────────────→
```

All pod types run concurrently throughout the entire test duration.

---

To generate plots from a snapshot, use the standalone plotting script:

1. Basic dashboard:
   python3 /home/sanjay7178/benchmark/plot_metrics_snapshot.py metrics_snapshot.jsonS

2. All visualizations:
   python3 /home/sanjay7178/benchmark/plot_metrics_snapshot.py metrics_snapshot.json --all

3. Individual detailed plots:
   python3 /home/sanjay7178/benchmark/plot_metrics_snapshot.py metrics_snapshot.json --individual-plots

4. Interactive dashboard:
   python3 /home/sanjay7178/benchmark/plot_metrics_snapshot.py metrics_snapshot.json --interactive

5. Summary report:
   python3 /home/sanjay7178/benchmark/plot_metrics_snapshot.py metrics_snapshot.json --summary-report

6. Custom output directory:
   python3 /home/sanjay7178/benchmark/plot_metrics_snapshot.py metrics_snapshot.json --output-dir /path/to/output --all
