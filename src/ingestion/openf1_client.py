import time

import requests


class OpenF1ClientError(RuntimeError):
    pass


class OpenF1Client:
    retryable_status_codes = {429, 500, 502, 503, 504}

    def __init__(
        self,
        base_url,
        timeout=30.0,
        max_retries=3,
        min_request_interval=2.1,
        http_session=None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_request_interval = min_request_interval
        self.http_session = http_session or requests.Session()
        self.last_request_at = 0.0

    def _wait_for_rate_limit(self):
        elapsed = time.monotonic() - self.last_request_at
        remaining = self.min_request_interval - elapsed

        if remaining > 0:
            time.sleep(remaining)

        self.last_request_at = time.monotonic()

    def _retry_delay(self, response, attempt):
        if response is not None:
            retry_after = response.headers.get("Retry-After")

            if retry_after:
                try:
                    return min(float(retry_after), 60.0)
                except ValueError:
                    pass

        return min(2 ** (attempt - 1), 30.0)

    def get_json(self, endpoint, params=None):
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        request_params = dict(params or {})
        attempts = self.max_retries + 1

        for attempt in range(1, attempts + 1):
            response = None

            try:
                self._wait_for_rate_limit()
                response = self.http_session.get(
                    url,
                    params=request_params,
                    headers={"Accept": "application/json"},
                    timeout=self.timeout,
                )

                if response.status_code in self.retryable_status_codes:
                    if attempt == attempts:
                        response.raise_for_status()

                    time.sleep(self._retry_delay(response, attempt))
                    continue

                response.raise_for_status()
                payload = response.json()

                if not isinstance(payload, (list, dict)):
                    raise OpenF1ClientError(
                        f"Resposta inválida para {endpoint}: "
                        f"tipo {type(payload).__name__}"
                    )

                return payload

            except OpenF1ClientError:
                raise
            except requests.RequestException as error:
                status_code = getattr(response, "status_code", None)
                can_retry = (
                    status_code is None
                    or status_code in self.retryable_status_codes
                )

                if not can_retry or attempt == attempts:
                    raise OpenF1ClientError(
                        f"Falha ao consultar {endpoint} com "
                        f"parâmetros {request_params}: {error}"
                    ) from error

                time.sleep(self._retry_delay(response, attempt))
            except ValueError as error:
                if attempt == attempts:
                    raise OpenF1ClientError(
                        f"Resposta não JSON para {endpoint} com "
                        f"parâmetros {request_params}"
                    ) from error

                time.sleep(self._retry_delay(response, attempt))

        raise OpenF1ClientError(
            f"Não foi possível consultar {endpoint} após {attempts} tentativas"
        )
