"""Generic cloud REST content-filter provider - video in, filtered video
out. Same sync/async job-polling shapes as
core/providers/enhancer/cloud_rest.py; see that file for the rationale on
why this is "custom"-configured rather than a named vendor preset.
"""

from core.providers.base import FilterProvider
from core.providers.cloud_rest_common import asset_headers, poll_until_done, request, resolve_credential
from core.http_media import write_media


class FilterCloudRestProvider(FilterProvider):
    def __init__(self, api_base_url, credential_ref, extra=None):
        self.api_base_url = api_base_url.rstrip("/")
        self.credential_ref = credential_ref
        self.extra = extra or {}

    def scan_and_blur(self, video_path, output_path):
        api_key = resolve_credential(self.credential_ref) if self.credential_ref else None
        extra = self.extra
        headers = {}
        if api_key:
            auth_header = extra.get("auth_header", "Authorization")
            auth_prefix = extra.get("auth_prefix", "Bearer ")
            headers[auth_header] = f"{auth_prefix}{api_key}"

        submit_path = extra.get("submit_path", "/filter")
        with open(video_path, "rb") as f:
            files = {"file": (video_path, f, "video/mp4")}
            resp = request("POST", f"{self.api_base_url}{submit_path}", headers=headers, files=files)

        if extra.get("mode", "sync") == "sync":
            return write_media(resp, output_path, {'video'})

        payload = resp.json()
        status_url = payload[extra.get("status_url_field", "status_url")]
        result_url = poll_until_done(
            status_url,
            headers,
            done_field=extra.get("done_field", "status"),
            done_value=extra.get("done_value", "succeeded"),
            result_field=extra.get("result_field", "output_url"),
            service_url=self.api_base_url,
        )
        download = request("GET", result_url, headers=asset_headers(self.api_base_url, result_url, headers))
        return write_media(download, output_path, {'video'})
