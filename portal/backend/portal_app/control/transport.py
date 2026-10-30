"""Fixed configuration destinations, verified server name/CA and client certificate."""

import ssl

import httpx


class DeliveryError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class Transport:
    def __init__(self, settings):
        self.settings = settings

    def request(self, backend, method, path, body=None):
        if backend not in self.settings.control_targets:
            raise DeliveryError("unknown_target")
        try:
            context = ssl.create_default_context(cafile=self.settings.control_ca)
            context.load_cert_chain(self.settings.control_cert, self.settings.control_key)
            with httpx.Client(
                verify=context,
                trust_env=False,
                follow_redirects=False,
                timeout=httpx.Timeout(3),
                limits=httpx.Limits(max_connections=2),
            ) as client:
                response = client.request(
                    method, self.settings.control_targets[backend] + path, json=body
                )
                if response.status_code == 404:
                    return None
                if not response.is_success:
                    raise DeliveryError(
                        "remote_conflict" if response.status_code == 409 else "remote_refused"
                    )
                if len(response.content) > 131072:
                    raise DeliveryError("invalid_receipt")
                return response.json()
        except (OSError, httpx.HTTPError, ValueError):
            raise DeliveryError("control_unavailable") from None
