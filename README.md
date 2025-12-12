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
uv run kubebrowse_benchmark.py     --namespace browser-sandbox     --max-users 500     --ramp-up-duration 3000     --ramp-down-duration 30     --target-url http://192.168.122.221/     --browser-init-wait 40     --sessions-api-url "https://192.168.122.220:80/sessions/"     --sessions-api-insecure     --session-start-interval 20    --session-duration 1200     --test-duration 60     --save-interval 30     --quiet    --headless
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
    --session-duration 1200 \
    --test-duration 60 \
    --save-interval 30 \
    --quiet \
    --headless \
    --temp-files-dir ./temp_files \
    --file-upload-interval 6 \
    --office-session-init-wait 5
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

1. **Frame Capture**: Playwright intercepts WebSocket frames sent/received during Guacamole sessions
2. **Timing**: Timestamps are recorded for each frame
3. **RTT Calculation**: RTT is calculated from frame send/receive timing patterns
4. **Statistics**: Aggregated statistics are computed (mean, median, percentiles)

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

To generate plots from this snapshot, use the standalone plotting script:

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
