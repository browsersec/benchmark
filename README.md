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
    --target-url http://192.168.122.202/ \
    --browser-init-wait 40 \
    --sessions-api-url "http://192.168.122.203/sessions/" \
    --sessions-api-insecure \
    --session-start-interval 10 \
    --test-duration 600
```




Visualization Instructions:
==========================

To generate plots from this snapshot, use the standalone plotting script:

1. Basic dashboard:
   python3 /home/sanjay7178/benchmark/plot_metrics_snapshot.py metrics_snapshot.json

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
