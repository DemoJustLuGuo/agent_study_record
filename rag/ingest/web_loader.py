from __future__ import annotations

import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class HTMLTextExtractor(HTMLParser):
    _BLOCK_TAGS = {
        "p",
        "div",
        "br",
        "li",
        "tr",
        "td",
        "th",
        "section",
        "article",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "blockquote",
        "pre",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "svg"}
    _CONSERVATIVE_NOISE_TAGS = {
        "aside",
        "footer",
        "nav",
        "form",
        "button",
        "iframe",
        "canvas",
        "dialog",
    }
    _CONSERVATIVE_NOISE_ROLES = {
        "navigation",
        "contentinfo",
        "complementary",
        "banner",
        "dialog",
    }
    _DEFAULT_NOISE_KEYWORDS = [
        "ad",
        "ads",
        "advert",
        "banner",
        "popup",
        "modal",
        "cookie",
        "consent",
        "sidebar",
        "footer",
        "toolbar",
        "recommend",
        "related",
        "comment",
        "social",
        "share",
        "sponsor",
        "widget",
    ]

    def __init__(self, cleaning_conf: dict[str, object] | None = None):
        super().__init__()
        self._parts: list[str] = []
        self._skip_tag_stack: list[str] = []
        self._noise_block_hits = 0
        self._dropped_short_lines = 0
        conf = cleaning_conf or {}
        self._cleaning_enabled = bool(conf.get("enabled", True))
        self._cleaning_mode = str(conf.get("mode", "conservative")).strip().lower()
        self._drop_short_line_length = int(conf.get("drop_short_line_length", 0))
        configured_keywords = conf.get("noise_keywords", [])
        if isinstance(configured_keywords, list) and configured_keywords:
            self._noise_keywords = [
                str(item).strip().lower()
                for item in configured_keywords
                if str(item).strip()
            ]
        else:
            self._noise_keywords = list(self._DEFAULT_NOISE_KEYWORDS)

    def _normalize_attrs(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for key, value in attrs:
            normalized[str(key or "").strip().lower()] = (
                str(value or "").strip().lower()
            )
        return normalized

    def _contains_noise_keyword(self, text: str) -> bool:
        if not text:
            return False
        tokens = [
            token for token in re.split(r"[^a-z0-9]+", text.lower()) if token.strip()
        ]
        if not tokens:
            return False
        token_set = set(tokens)
        for keyword in self._noise_keywords:
            if len(keyword) <= 2:
                if keyword in token_set:
                    return True
                continue
            if keyword in token_set or any(
                token.startswith(keyword) for token in tokens
            ):
                return True
        return False

    def _is_noise_container(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> bool:
        if tag in self._SKIP_TAGS:
            return True
        if not self._cleaning_enabled:
            return False
        if (
            self._cleaning_mode == "conservative"
            and tag in self._CONSERVATIVE_NOISE_TAGS
        ):
            return True

        attr_map = self._normalize_attrs(attrs)
        class_or_id = " ".join(
            [
                attr_map.get("class", ""),
                attr_map.get("id", ""),
                attr_map.get("role", ""),
                attr_map.get("aria-label", ""),
                attr_map.get("data-testid", ""),
            ]
        )
        role_value = attr_map.get("role", "")
        if (
            self._cleaning_mode == "conservative"
            and role_value in self._CONSERVATIVE_NOISE_ROLES
        ):
            return True
        return self._contains_noise_keyword(class_or_id)

    def handle_starttag(self, tag, attrs):
        if self._is_noise_container(tag, attrs):
            self._skip_tag_stack.append(tag)
            if tag not in self._SKIP_TAGS:
                self._noise_block_hits += 1
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if self._skip_tag_stack and tag == self._skip_tag_stack[-1]:
            self._skip_tag_stack.pop()
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip_tag_stack:
            return
        text = (data or "").strip()
        if text:
            self._parts.append(text)

    def get_text(self) -> str:
        raw = " ".join(self._parts)
        lines = [" ".join(line.split()) for line in raw.splitlines()]
        filtered_lines: list[str] = []
        for line in lines:
            if not line:
                continue
            if (
                self._drop_short_line_length > 0
                and len(line) < self._drop_short_line_length
            ):
                self._dropped_short_lines += 1
                continue
            filtered_lines.append(line)
        return "\n".join(filtered_lines).strip()

    def get_cleaning_stats(self, raw_chars: int) -> dict[str, object]:
        return {
            "cleaning_mode": self._cleaning_mode,
            "noise_block_hits": self._noise_block_hits,
            "dropped_short_lines": self._dropped_short_lines,
            "raw_chars": int(raw_chars),
        }


def normalize_web_url(url: str) -> str:
    text = (url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return parsed.geturl()


def _is_private_or_local_address(hostname: str) -> bool:
    host = (hostname or "").strip().strip("[]").lower()
    if not host:
        return True
    if host in {"localhost", "localhost.localdomain"}:
        return True

    addresses: set[str] = set()
    try:
        ipaddress.ip_address(host)
        addresses.add(host)
    except ValueError:
        try:
            for result in socket.getaddrinfo(host, None):
                addresses.add(str(result[4][0]))
        except socket.gaierror:
            return False

    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
        if str(ip) == "169.254.169.254":
            return True
    return False


def validate_web_url_allowed(url: str, security_conf: dict[str, object] | None = None) -> None:
    conf = security_conf or {}
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise RuntimeError("invalid_url")

    reject_private = bool(conf.get("reject_private_ips", True))
    reject_localhost = bool(conf.get("reject_localhost", True))
    if (reject_private or reject_localhost) and _is_private_or_local_address(
        parsed.hostname or ""
    ):
        raise RuntimeError("blocked_private_or_local_address")


def fetch_web_text(
    *,
    url: str,
    timeout_seconds: float,
    user_agent: str,
    max_content_chars: int,
    cleaning_conf: dict[str, object] | None = None,
    security_conf: dict[str, object] | None = None,
) -> tuple[str, dict[str, object]]:
    validate_web_url_allowed(url, security_conf=security_conf)
    request = Request(url, headers={"User-Agent": user_agent})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            final_url = response.geturl()
            validate_web_url_allowed(final_url, security_conf=security_conf)
            raw = response.read(max(max_content_chars * 2, 4096))
            charset = response.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
            content_type = str(response.headers.get("Content-Type", "")).lower()
    except URLError as error:
        raise RuntimeError(f"网络请求失败: {error}") from error

    allowed_content_types = (security_conf or {}).get("allowed_content_types", [])
    if isinstance(allowed_content_types, list) and allowed_content_types:
        if not any(str(item).lower() in content_type for item in allowed_content_types):
            raise RuntimeError(f"blocked_content_type:{content_type or 'unknown'}")

    if "html" in content_type or "<html" in text.lower():
        parser = HTMLTextExtractor(cleaning_conf=cleaning_conf)
        parser.feed(text)
        parsed_text = parser.get_text()
        stats = parser.get_cleaning_stats(raw_chars=len(text))
    else:
        parsed_text = "\n".join(
            line.strip() for line in text.splitlines() if line.strip()
        )
        stats = {
            "cleaning_mode": "plain_text",
            "noise_block_hits": 0,
            "dropped_short_lines": 0,
            "raw_chars": len(text),
        }

    if len(parsed_text) > max_content_chars:
        parsed_text = parsed_text[:max_content_chars]
    stats["cleaned_chars"] = len(parsed_text)
    return parsed_text, stats
