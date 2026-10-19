# retrywise

Retry flaky calls with exponential backoff and jitter. One decorator, works on both regular and `async` functions, zero dependencies.

```bash
pip install git+https://github.com/xacking/retrywise
```

```python
import requests
from retrywise import retry

@retry(5, on=(requests.ConnectionError, requests.Timeout))
def fetch(url):
    return requests.get(url, timeout=5).json()
```

```python
import httpx
from retrywise import retry

def is_server_error(exc):
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500

@retry(4, on=httpx.HTTPError, retry_if=is_server_error, max_delay=10)
async def get_user(client, uid):
    r = await client.get(f"/users/{uid}")
    r.raise_for_status()
    return r.json()
```

## Options

| Argument | Default | Meaning |
|---|---|---|
| `attempts` | `3` | total tries, including the first |
| `on` | `Exception` | exception type(s) that trigger a retry |
| `retry_if` | `None` | extra check on the exception |
| `base`, `factor`, `max_delay` | `0.5`, `2.0`, `30` | delay = `min(max_delay, base * factor**n)` |
| `jitter` | `True` | "full jitter": random delay in `[0, delay]` to avoid thundering herds |
| `on_retry` | `None` | `callback(attempt, exc, delay)` — handy for logging/metrics |
| `reraise` | `False` | raise the original exception instead of `RetryError` |

When every attempt fails you get a `RetryError` with `.attempts` and `.last` (the final exception).

## License

MIT
