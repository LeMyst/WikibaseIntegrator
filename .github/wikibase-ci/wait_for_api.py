import os
import time
from urllib.parse import urlencode

import requests

API_URL = os.getenv('WBI_MEDIAWIKI_API_URL', 'http://127.0.0.1:8181/w/api.php')
TIMEOUT_SECONDS = int(os.getenv('WBI_API_WAIT_TIMEOUT', '180'))


def is_ready() -> bool:
    query = urlencode({'action': 'query', 'meta': 'siteinfo', 'format': 'json'})
    response = requests.get(f'{API_URL}?{query}', timeout=10)
    if response.status_code != 200:
        return False

    try:
        payload = response.json()
    except ValueError:
        # MediaWiki may briefly return non-JSON (e.g. HTML) while starting.
        return False

    return 'query' in payload and 'general' in payload['query']


def main() -> None:
    deadline = time.time() + TIMEOUT_SECONDS
    while time.time() < deadline:
        try:
            if is_ready():
                print(f'MediaWiki API is ready at {API_URL}')
                return
        except requests.RequestException:
            pass
        time.sleep(2)

    raise TimeoutError(f'MediaWiki API did not become ready within {TIMEOUT_SECONDS} seconds: {API_URL}')


if __name__ == '__main__':
    main()
