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
    --target-url http://4.156.203.206/ \
    --browser-init-wait 20 \
    --sessions-api-url "https://172.18.120.152:30006/sessions/" \
    --sessions-api-insecure
```

TEST 2

```
python kubebrowse_benchmark.py \
    --namespace browser-sandbox \
    --max-users 50 \
    --test-duration 3600 \
    --save-interval 30 \
    --target-url http://172.18.120.162/ \
    --browser-init-wait 40 \
    --sessions-api-url "https://172.18.120.152:30006/sessions/" \
    --session-start-interval 10 \
    --test-duration 600
```