#!/usr/bin/env python3
"""
F5 BIG-IP MCP Server - Streamable HTTP Transport
For Microsoft Copilot (Copilot Studio + VS Code GitHub Copilot)

Based on f5-mcp/f5_mcp.py (stdio transport), adapted for HTTP.
"""

import os
import subprocess
import re
import html
import hmac
import logging
import functools
import traceback
import posixpath
import atexit
from pathlib import Path
from urllib.request import urlopen, Request as URLRequest
from urllib.parse import quote_plus
from urllib.error import URLError, HTTPError

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

# =============================================================================
# Logging
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("f5-mcp")

# =============================================================================
# Load environment
# =============================================================================

load_dotenv(Path(__file__).parent / ".env")

# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = Path(__file__).parent
KNOWLEDGE_DIR = BASE_DIR / "Knowledge"

# Server config
SERVER_HOST = os.getenv("MCP_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("MCP_PORT", "8080"))
_raw_api_key = os.getenv("MCP_API_KEY", "").strip()
# Treat default placeholder values as "no key configured"
API_KEY = "" if _raw_api_key in ("", "generate-a-secure-random-key-here") else _raw_api_key

# =============================================================================
# In-Memory Device Registry (nothing written to disk)
# =============================================================================

_device_registry: dict = {}    # name -> device dict
_default_device: str = None    # name of default device


def _seed_from_env():
    """Seed registry from environment variables at startup.

    Loads the default device from F5_HOST/F5_USER/etc., plus any named
    devices defined with the F5_DEVICE_{NAME}_HOST convention.
    """
    global _default_device

    # --- Default device from legacy env vars ---
    host = os.getenv("F5_HOST", "")
    if host:
        _device_registry["default"] = {
            "host": host,
            "user": os.getenv("F5_USER", "admin"),
            "port": int(os.getenv("F5_PORT", "22")),
        }
        key = os.getenv("F5_SSH_KEY", "")
        password = os.getenv("F5_PASSWORD", "")
        if key:
            _device_registry["default"]["key"] = key
        elif password:
            _device_registry["default"]["password"] = password
        _default_device = "default"

    # --- Named devices from F5_DEVICE_{NAME}_HOST pattern ---
    seen_names = set()
    for var in os.environ:
        if var.startswith("F5_DEVICE_") and var.endswith("_HOST"):
            # Extract name: F5_DEVICE_PROD_HOST -> prod
            name = var[len("F5_DEVICE_"):-len("_HOST")].lower()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
            prefix = f"F5_DEVICE_{name.upper()}_"
            dev_host = os.getenv(var, "").strip()
            if not dev_host:
                continue
            device = {
                "host": dev_host,
                "user": os.getenv(f"{prefix}USER", "admin"),
                "port": int(os.getenv(f"{prefix}PORT", "22")),
            }
            dev_key = os.getenv(f"{prefix}SSH_KEY", "")
            dev_pass = os.getenv(f"{prefix}PASSWORD", "")
            if dev_key:
                device["key"] = dev_key
            elif dev_pass:
                device["password"] = dev_pass
            _device_registry[name] = device
            if not _default_device:
                _default_device = name


_seed_from_env()


def _validate_ssh_key(path: str) -> str:
    """Validate and expand SSH key path. Returns expanded path."""
    expanded = os.path.expanduser(path.strip())
    if not os.path.isfile(expanded):
        raise ValueError(f"SSH key not found: {expanded}")
    return expanded


def _auto_name(host: str) -> str:
    """Generate a short device name from host/IP if user didn't provide one."""
    # Strip domain, replace dots with dashes for IPs
    name = host.split(".")[0] if not host[0].isdigit() else host.replace(".", "-")
    # Deduplicate
    base, n = name, 1
    while name in _device_registry:
        n += 1
        name = f"{base}-{n}"
    return name


def get_device(name: str = None) -> dict:
    """Get device config by name or default device."""
    target = name or _default_device
    if not target or target not in _device_registry:
        return None
    return _device_registry[target]


def _device_summary(name: str, dev: dict) -> str:
    """One-line summary of a device for listings."""
    is_default = " (default)" if name == _default_device else ""
    auth = "ssh-key" if dev.get("key") else "password" if dev.get("password") else "no-auth"
    port = f":{dev['port']}" if dev.get("port", 22) != 22 else ""
    return f"  {name}{is_default}  {dev['user']}@{dev['host']}{port}  [{auth}]"


# =============================================================================
# SSH Execution
# =============================================================================

# Cache: device host -> True if default shell is TMSH (not bash)
_tmsh_shell_cache: dict[str, bool] = {}

# SSH ControlMaster socket directory for connection reuse
_SSH_CONTROL_DIR = Path("/tmp/f5-mcp-ssh")
_SSH_CONTROL_DIR.mkdir(mode=0o700, exist_ok=True)


def _cleanup_ssh_sockets():
    """Close all SSH ControlMaster connections and remove socket files."""
    if _SSH_CONTROL_DIR.exists():
        for sock in _SSH_CONTROL_DIR.iterdir():
            try:
                # Gracefully close the master connection
                subprocess.run(
                    ["ssh", "-O", "exit", "-o", f"ControlPath={sock}", "dummy"],
                    capture_output=True, timeout=3,
                )
            except Exception:
                pass
            try:
                sock.unlink()
            except OSError:
                pass
    log.info("SSH ControlMaster sockets cleaned up")


atexit.register(_cleanup_ssh_sockets)


def _ssh_run(device: dict, command: str, timeout: int = 30) -> dict:
    """Low-level SSH execution with connection multiplexing."""

    host = device["host"]
    port = device.get("port", 22)
    control_path = _SSH_CONTROL_DIR / f"{host}-{port}"

    ssh_opts = [
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", f"ConnectTimeout={min(timeout, 10)}",
        # Connection multiplexing — reuse SSH connection across calls
        "-o", f"ControlPath={control_path}",
        "-o", "ControlMaster=auto",
        "-o", "ControlPersist=300",  # keep connection alive 5 minutes
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
    ]

    if port != 22:
        ssh_opts.extend(["-p", str(port)])

    target = f"{device['user']}@{host}"

    if device.get("key"):
        ssh_cmd = ["ssh", "-o", "BatchMode=yes"] + ssh_opts
        ssh_cmd.extend(["-i", os.path.expanduser(device["key"])])
        ssh_cmd.extend([target, command])
        env = None
    elif device.get("password"):
        ssh_cmd = ["sshpass", "-e", "ssh"] + ssh_opts
        ssh_cmd.extend([target, command])
        env = os.environ.copy()
        env["SSHPASS"] = device["password"]
    else:
        return {"success": False, "output": "", "error": "No key or password configured", "code": -1}

    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL, env=env)
        return {
            "success": result.returncode == 0,
            "output": result.stdout,
            "error": result.stderr,
            "code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        log.warning("SSH timeout after %ds: %s -> %s", timeout, device["host"], command[:80])
        return {"success": False, "output": "", "error": f"SSH command timed out after {timeout}s. The device may be unreachable or the command is long-running.", "code": -1}
    except FileNotFoundError as e:
        if "sshpass" in str(e):
            return {"success": False, "output": "", "error": "sshpass not installed. Install with: brew install sshpass (macOS) or apt install sshpass (Linux)", "code": -1}
        return {"success": False, "output": "", "error": str(e), "code": -1}
    except Exception as e:
        log.error("SSH exception: %s -> %s: %s", device["host"], command[:80], e)
        return {"success": False, "output": "", "error": str(e), "code": -1}


def ssh_exec(device: dict, command: str, timeout: int = 15, context: str = "tmsh") -> dict:
    """Execute command on F5 via SSH with TMSH shell auto-detection.

    Handles two cases when default shell is TMSH (not bash):
    1. TMSH commands: strips redundant 'tmsh' prefix and retries
    2. Bash commands: wraps in 'bash -c "..."' to escape TMSH shell
    """
    host = device["host"]
    log.info("SSH exec [%s]: %s -> %s", context, host, command[:120])

    # If we already know this device uses TMSH shell, adjust command upfront
    if _tmsh_shell_cache.get(host):
        if context == "tmsh":
            # Strip tmsh prefix — shell is already TMSH
            command = re.sub(r'^tmsh\s+', '', command)
        elif context == "bash":
            # Wrap bash command so TMSH shell executes it via bash
            escaped = command.replace("'", "'\\''")
            command = f"bash -c '{escaped}'"
        log.info("Adjusted for TMSH shell: %s", command[:120])

    result = _ssh_run(device, command, timeout)

    # Auto-detect TMSH shell on first encounter
    if not result["success"] and "unexpected argument" in result.get("error", ""):
        error_msg = result["error"]
        if '"tmsh"' in error_msg:
            # TMSH command with redundant tmsh prefix
            log.info("Detected TMSH default shell on %s — retrying without 'tmsh' prefix", host)
            _tmsh_shell_cache[host] = True
            stripped = re.sub(r'^tmsh\s+', '', command)
            if stripped != command:
                result = _ssh_run(device, stripped, timeout)
        elif context == "bash":
            # Bash command sent to TMSH shell — wrap in bash -c
            log.info("Detected TMSH default shell on %s — retrying bash command via bash -c", host)
            _tmsh_shell_cache[host] = True
            escaped = command.replace("'", "'\\''")
            wrapped = f"bash -c '{escaped}'"
            result = _ssh_run(device, wrapped, timeout)

    if result["success"]:
        log.info("SSH OK: %s -> %s", host, command[:80])
    else:
        log.warning("SSH failed: %s -> %s: %s", host, command[:80], result["error"][:200])

    return result


def is_tmsh_shell(device: dict) -> bool:
    """Check if device's default shell is TMSH (cached after first detection)."""
    return _tmsh_shell_cache.get(device.get("host", ""), False)


# =============================================================================
# Knowledge Base
# =============================================================================


def search_knowledge(query: str) -> tuple:
    """Search knowledge files for relevant content.
    Returns (content_str, matched_specific_keyword: bool).
    matched=False means only the default fallback was returned.
    """
    if not KNOWLEDGE_DIR.exists():
        return ("", False)

    keywords = {
        "pool": ["ltm_fundamentals.md", "quick_reference.md"],
        "virtual": ["ltm_fundamentals.md", "quick_reference.md"],
        "member": ["ltm_fundamentals.md", "quick_reference.md"],
        "monitor": ["ltm_fundamentals.md"],
        "ssl": ["ssl_tls_configuration.md"],
        "tls": ["ssl_tls_configuration.md"],
        "cert": ["ssl_tls_configuration.md"],
        "irule": ["irules_reference.md"],
        "rule": ["irules_reference.md"],
        "ha": ["high_availability.md"],
        "failover": ["high_availability.md"],
        "sync": ["high_availability.md"],
        "route": ["network_configuration.md"],
        "vlan": ["network_configuration.md"],
        "snat": ["network_configuration.md"],
        "api": ["icontrol_rest_api.md"],
        "rest": ["icontrol_rest_api.md"],
        "troubleshoot": ["troubleshooting.md"],
        "debug": ["troubleshooting.md"],
        "log": ["troubleshooting.md"],
        "tmsh": ["tmsh_reference.md", "quick_reference.md"],
        "tcp": ["tcp_optimization.md"],
        "performance": ["tcp_optimization.md"],
        "as3": ["automation_toolkit.md"],
        "ansible": ["automation_toolkit.md"],
        "doc": ["external_references.md"],
        "url": ["external_references.md"],
        "k-article": ["external_references.md"],
        "reference": ["external_references.md"],
    }

    files = set()
    q = query.lower()
    for kw, flist in keywords.items():
        if kw in q:
            files.update(flist)

    matched = bool(files)
    if not files:
        files.add("quick_reference.md")

    content = []
    for f in files:
        path = KNOWLEDGE_DIR / f
        if path.exists():
            text = path.read_text()[:4000]
            content.append(f"## {f}\n{text}")

    return ("\n\n".join(content), matched)


# =============================================================================
# External Documentation Search
# =============================================================================

# Official F5 documentation sources
F5_SOURCES = {
    "devcentral": {
        "name": "F5 DevCentral (Community)",
        "search_url": "https://community.f5.com/t5/forums/searchpage/tab/message?q={query}",
        "base_url": "https://community.f5.com",
    },
    "clouddocs": {
        "name": "F5 CloudDocs",
        "search_url": "https://clouddocs.f5.com/search.html?q={query}",
        "base_url": "https://clouddocs.f5.com",
    },
    "askf5": {
        "name": "AskF5 Knowledge Base",
        "search_url": "https://my.f5.com/manage/s/global-search/%40uri#q={query}&t=All&sort=relevancy",
        "base_url": "https://my.f5.com",
    },
    "tmsh_ref": {
        "name": "TMSH Reference",
        "search_url": "https://clouddocs.f5.com/cli/tmsh-reference/latest/",
        "base_url": "https://clouddocs.f5.com/cli/tmsh-reference/latest/",
    },
}

# Map query topics to the most relevant CloudDocs pages for direct fetching
CLOUDDOCS_TOPIC_PAGES = {
    "as3": "https://clouddocs.f5.com/products/extensions/f5-appsvcs-extension/latest/",
    "declarative onboarding": "https://clouddocs.f5.com/products/extensions/f5-declarative-onboarding/latest/",
    "telemetry": "https://clouddocs.f5.com/products/extensions/f5-telemetry-streaming/latest/",
    "icontrol": "https://clouddocs.f5.com/api/icontrol-rest/",
    "rest api": "https://clouddocs.f5.com/api/icontrol-rest/",
    "bigiq": "https://clouddocs.f5.com/products/big-iq/mgmt-api/latest/",
    "waf": "https://clouddocs.f5.com/products/extensions/f5-appsvcs-extension/latest/declarations/waf.html",
    "asm": "https://clouddocs.f5.com/products/extensions/f5-appsvcs-extension/latest/declarations/waf.html",
}


def _http_get(url: str, timeout: int = 10) -> str:
    """Fetch URL content, return body text. Returns empty string on failure."""
    try:
        req = URLRequest(url, headers={
            "User-Agent": "F5-MCP-Server/1.0 (documentation-lookup)",
            "Accept": "text/html, application/json, text/plain",
        })
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except (URLError, HTTPError, OSError, ValueError):
        return ""


def _html_to_text(raw_html: str, max_len: int = 6000) -> str:
    """Rough HTML-to-text: strip tags, collapse whitespace, decode entities."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", raw_html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:max_len]


def _fetch_clouddocs_page(url: str) -> str:
    """Fetch a CloudDocs page and extract readable content."""
    body = _http_get(url)
    if not body:
        return ""
    return _html_to_text(body)


def _search_devcentral_scrape(query: str) -> str:
    """Search DevCentral and return formatted results from the search page."""
    encoded = quote_plus(query)
    url = f"https://community.f5.com/t5/forums/searchpage/tab/message?q={encoded}&collapse_discussion=true"
    body = _http_get(url, timeout=15)
    if not body:
        return ""

    # Extract result titles and links from search page
    results = []
    pattern = re.compile(
        r'<a[^>]*href="(/t5/[^"]+)"[^>]*class="[^"]*page-link[^"]*"[^>]*>([^<]+)</a>',
        re.I,
    )
    for match in pattern.finditer(body):
        path, title = match.group(1), match.group(2).strip()
        if title and path:
            results.append({"title": html.unescape(title), "url": f"https://community.f5.com{path}"})
        if len(results) >= 5:
            break

    if not results:
        # fallback: look for any plausible result links
        fallback = re.compile(r'<a[^>]*href="(https://community\.f5\.com/t5/[^"]+)"[^>]*>([^<]{10,})</a>', re.I)
        for match in fallback.finditer(body):
            url_match, title = match.group(1), match.group(2).strip()
            if title:
                results.append({"title": html.unescape(title), "url": url_match})
            if len(results) >= 5:
                break

    return results


def search_external_docs(query: str, sources: list = None) -> str:
    """
    Search official F5 documentation sources for a query.
    Returns combined results from multiple sources.
    """
    if sources is None:
        sources = ["clouddocs", "devcentral", "askf5"]

    sections = []
    q_lower = query.lower()

    # 1. Check if query maps to a known CloudDocs topic page - fetch it directly
    for topic, url in CLOUDDOCS_TOPIC_PAGES.items():
        if topic in q_lower:
            page_text = _fetch_clouddocs_page(url)
            if page_text:
                sections.append(f"## CloudDocs: {topic.upper()}\n**Source:** {url}\n\n{page_text[:3000]}")
            break

    # 2. Search DevCentral community
    if "devcentral" in sources:
        results = _search_devcentral_scrape(query)
        if results:
            lines = [f"## DevCentral Community Results\n"]
            for r in results:
                lines.append(f"- [{r['title']}]({r['url']})")
            sections.append("\n".join(lines))

            # Fetch top result content
            if results:
                top_content = _fetch_clouddocs_page(results[0]["url"])
                if top_content:
                    sections.append(f"### Top Result: {results[0]['title']}\n{top_content[:3000]}")

    # 3. Provide direct search URLs for sources that need browser/JS
    search_links = []
    if "askf5" in sources:
        encoded = quote_plus(query)
        search_links.append(
            f"- **AskF5 K-Articles:** https://my.f5.com/manage/s/global-search/%40uri#q={encoded}&t=All&sort=relevancy"
        )
    if "clouddocs" in sources:
        encoded = quote_plus(query)
        search_links.append(
            f"- **CloudDocs:** https://clouddocs.f5.com/search.html?q={encoded}"
        )
    search_links.append(
        f"- **TMSH Reference:** https://clouddocs.f5.com/cli/tmsh-reference/latest/"
    )
    search_links.append(
        f"- **DevCentral Search:** https://community.f5.com/t5/forums/searchpage/tab/message?q={quote_plus(query)}"
    )

    if search_links:
        sections.append("## Direct Search Links\n" + "\n".join(search_links))

    # 4. Suggest relevant K-articles based on keywords
    k_articles = _suggest_k_articles(query)
    if k_articles:
        sections.append(k_articles)

    return "\n\n---\n\n".join(sections) if sections else ""


def _suggest_k_articles(query: str) -> str:
    """Suggest well-known K-articles based on query keywords."""
    q = query.lower()
    suggestions = []

    k_map = {
        ("rst", "reset", "tcp reset"): ("K10052", "TCP RST causes and troubleshooting"),
        ("ssl handshake", "ssl fail", "tls handshake"): ("K15292", "SSL/TLS handshake failure troubleshooting"),
        ("pool flap", "member flap", "pool member down"): ("K14620", "Pool member flapping"),
        ("ha sync", "config sync", "sync fail"): ("K13946", "HA config sync issues"),
        ("memory", "oom", "out of memory"): ("K16419", "Memory troubleshooting"),
        ("connection limit", "connlimit", "max connections"): ("K7820", "Connection limits"),
        ("upgrade", "software install"): ("K13845", "BIG-IP software upgrade guide"),
        ("license", "reactivate"): ("K7727", "License activation and reactivation"),
        ("core dump", "core file", "crash"): ("K10062", "Core dump analysis"),
        ("certificate", "cert expir", "cert renew"): ("K15664", "SSL certificate management"),
        ("dns", "gtm", "wideip"): ("K13312", "GTM/DNS configuration"),
        ("persist", "persistence", "sticky"): ("K6869", "Persistence profiles"),
        ("snat", "source nat", "snat pool"): ("K7820", "SNAT configuration"),
        ("irule", "tcl"): ("K11210", "iRule development best practices"),
    }

    for keywords, (article_id, description) in k_map.items():
        if any(kw in q for kw in keywords):
            url = f"https://my.f5.com/manage/s/article/{article_id}"
            suggestions.append(f"- **{article_id}** - {description}: {url}")

    if suggestions:
        return "## Suggested K-Articles\n" + "\n".join(suggestions)
    return ""


# =============================================================================
# Security Guardrails
# =============================================================================


def _security_check(command: str, context: str) -> str | None:
    """Validate command before execution. Returns rejection message or None if safe."""
    checks = [
        _check_injection,
        _check_credentials,
        _check_network,
        _check_privilege_escalation,
        _check_exfiltration,
    ]
    if context == "bash":
        checks.append(_check_bash_allowlist)

    for check in checks:
        rejection = check(command, context)
        if rejection:
            return rejection
    return None


def _check_destructive(command: str) -> str | None:
    """Return warning banner for high-impact commands (does NOT block)."""
    cmd_lower = command.lower()
    destructive_patterns = [
        "delete ltm virtual", "delete ltm pool", "delete ltm node",
        "load sys config default", "modify sys global-settings hostname",
        "modify cm device-group", "delete net self", "delete net vlan",
    ]
    for pattern in destructive_patterns:
        if pattern in cmd_lower:
            return (
                "⚠ WARNING: This command modifies production configuration. "
                "Ensure you have a rollback plan before proceeding."
            )
    return None


def _check_injection(command: str, context: str) -> str | None:
    """Block shell metacharacters, chaining, encoded payloads."""
    # Shell chaining operators (but allow TMSH pipe for filtering)
    chain_chars = [";", "&&", "||", "$(", "`", "{"]
    for char in chain_chars:
        if char in command:
            return _reject(
                "Command Injection",
                f"shell chaining operator '{char}' is not allowed",
                "Run one command at a time: f5_tmsh(command='show ltm pool')",
                "Each command should do exactly one thing.",
            )

    # Bash pipe is blocked; TMSH pipe (for grep/filter) is allowed
    if "|" in command:
        if context == "bash":
            return _reject(
                "Command Injection",
                "pipe operator '|' is not allowed in bash commands",
                "Run each command separately and review the output",
                "Pipes can be used to chain commands in unintended ways.",
            )
        # For TMSH, allow pipe only for safe filter commands
        parts = command.split("|")
        if len(parts) > 2:
            return _reject(
                "Command Injection",
                "multiple pipe operators are not allowed",
                "Use a single filter: show ltm pool | grep name",
                "Only one pipe to a filter command is permitted in TMSH.",
            )

    # Redirections to sensitive paths
    redirect_patterns = ["> /etc/", "> /config/", "> /root/", "> /var/", ">> /etc/", ">> /config/", ">> /root/", ">> /var/"]
    for pat in redirect_patterns:
        if pat in command:
            return _reject(
                "Command Injection",
                "output redirection to system directories is not allowed",
                "Review command output directly instead of writing to files",
                "Redirecting output to system directories can overwrite critical files.",
            )

    # Encoded/obfuscated payloads
    encoded_patterns = ["base64", "%0a", "%0d", "\\x", "${IFS}", "${PATH}", "${HOME}"]
    cmd_check = command  # case-sensitive for variable expansions
    for pat in encoded_patterns:
        if pat in cmd_check or pat in command.lower():
            return _reject(
                "Command Injection",
                f"encoded or obfuscated pattern '{pat}' detected",
                "Use plain, literal arguments in your commands",
                "Encoded payloads can hide malicious command sequences.",
            )

    return None


def _normalize_paths(command: str) -> str:
    """Normalize file paths in a command to defeat path traversal bypasses.

    Handles: double slashes (//), dot segments (./), parent traversal (../),
    and produces canonical paths for matching.
    """
    normalized = command
    # Find all absolute paths in the command and normalize them
    for match in re.finditer(r'(/[^\s;|&>`\'\"]+)', command):
        raw_path = match.group(1)
        clean = posixpath.normpath(raw_path)
        normalized = normalized.replace(raw_path, clean)
    return normalized


# Sensitive file patterns — checked against normalized paths
_SENSITIVE_FILE_PATTERNS = [
    # Authentication & account databases
    (r'/etc/passwd', "system user account database"),
    (r'/etc/shadow', "system password hashes"),
    (r'/etc/gshadow', "group password hashes"),
    (r'/etc/master\.passwd', "system password hashes"),
    (r'/etc/group', "system group database"),
    (r'/etc/sudoers', "sudo privilege configuration"),
    (r'/etc/security/', "PAM/security configuration"),
    # Network access control
    (r'/etc/hosts\.allow', "network access control"),
    (r'/etc/hosts\.deny', "network access control"),
    # Auth logs
    (r'/var/log/secure', "authentication log"),
    (r'/var/log/auth\.log', "authentication log"),
    (r'/var/log/audit', "audit log"),
    # Root home
    (r'/root/', "root home directory"),
    (r'/root$', "root home directory"),
    # F5-specific credentials
    (r'/config/ssl/ssl\.key', "SSL private key"),
    (r'/config/bigip\.conf', "main configuration file with embedded credentials"),
    (r'/config/bigip_base\.conf', "base configuration file with credentials"),
    (r'/config/bigip_user\.conf', "user configuration file with credentials"),
    (r'/config/bigip_script\.conf', "script configuration file"),
    (r'/\.ssh/', "SSH key directory"),
    (r'/config/filestore/.*/certificate_key', "certificate private key store"),
]

# Compile once
_SENSITIVE_FILE_RE = [(re.compile(pat, re.I), desc) for pat, desc in _SENSITIVE_FILE_PATTERNS]


def _extract_and_normalize_paths(command: str) -> list[str]:
    """Extract all file paths from a command and return normalized versions.

    Returns both raw and normalized forms so we catch every variant.
    """
    paths = []
    for match in re.finditer(r'(/[^\s;|&>`\'\"]+)', command):
        raw = match.group(1)
        paths.append(raw.lower())
        paths.append(posixpath.normpath(raw).lower())
    return paths


def _check_credentials(command: str, context: str) -> str | None:
    """Block access to credentials, private keys, and auth config."""
    cmd_lower = command.lower()

    # Extract and normalize ALL file paths from the command
    # This catches any command (cat, awk, head, tail, grep, find, dd, etc.)
    all_paths = _extract_and_normalize_paths(command)
    # Also check the full command string for patterns without a leading /
    check_targets = all_paths + [cmd_lower, _normalize_paths(cmd_lower)]

    for target in check_targets:
        for pattern_re, desc in _SENSITIVE_FILE_RE:
            if pattern_re.search(target):
                return _reject(
                    "Credential Protection",
                    f"access to {desc} is not allowed",
                    "Use 'tmsh show sys version' or 'tmsh list sys user' for system info",
                    "Sensitive system files can expose user accounts, passwords, and security configuration.",
                )

    # Find commands targeting sensitive filenames
    if re.search(r'\bfind\b', cmd_lower):
        sensitive_names = ["shadow", "gshadow", "passwd", "master.passwd", "sudoers",
                          "ssl.key", "bigip.conf", "bigip_base.conf", "bigip_user.conf",
                          "f5masterkey", "unitkey", ".ssh"]
        for name in sensitive_names:
            if name in cmd_lower:
                return _reject(
                    "Credential Protection",
                    f"searching for sensitive file '{name}' is not allowed",
                    "Use 'tmsh list' commands to inspect F5 configuration",
                    "Locating sensitive files can be a precursor to credential theft.",
                )

    # Keyword-based credential patterns (not path-dependent)
    cred_keywords = [
        ("f5masterkey", "F5 master key access"),
        ("unitkey", "F5 unit key access"),
    ]
    for keyword, desc in cred_keywords:
        if keyword in cmd_lower:
            return _reject(
                "Credential Protection",
                f"{desc} is not allowed",
                "Use 'tmsh list sys crypto cert' to view certificate details (public info only)",
                "Private keys and credentials must never be exposed through command output.",
            )

    # TMSH credential commands
    tmsh_cred_patterns = [
        ("list sys crypto key", "Listing crypto keys exposes private key material"),
        ("show auth user", "Viewing auth users can expose password hashes"),
        ("modify auth user", "Modifying auth users requires explicit authorization"),
        ("create auth user", "Creating auth users requires explicit authorization"),
        ("modify auth partition", "Modifying auth partitions requires explicit authorization"),
    ]
    for pattern, reason in tmsh_cred_patterns:
        if pattern in cmd_lower:
            return _reject(
                "Credential Protection",
                reason.lower(),
                "Use 'tmsh list sys crypto cert' for certificate info, or 'tmsh list auth user' for username listing",
                "Credential operations are restricted to prevent unauthorized access.",
            )

    return None


def _check_network(command: str, context: str) -> str | None:
    """Block outbound connections, lateral movement, and network enumeration."""
    cmd_lower = command.lower()

    # Outbound connection tools
    net_tools = ["curl ", "curl\t", "wget ", "wget\t", "nc ", "netcat ", "telnet ", "nmap ", "python -c", "python3 -c", "perl -e", "ruby -e"]
    for tool in net_tools:
        if tool in cmd_lower:
            tool_name = tool.strip()
            return _reject(
                "Network Security",
                f"'{tool_name}' can create outbound connections from the F5 device",
                "Use f5_knowledge or f5_search_docs to find information instead",
                "Outbound connections from network devices can enable data exfiltration.",
            )

    # SSH from F5 to other hosts (bash context)
    if context == "bash" and re.search(r'\bssh\s', cmd_lower):
        return _reject(
            "Network Security",
            "SSH connections from the F5 to other hosts enable lateral movement",
            "Connect to other devices directly using f5_add_device",
            "Each device should be managed through its own authenticated session.",
        )

    # Network enumeration
    enum_patterns = [("arp -a", "ARP table enumeration"), ("show net arp", "ARP table enumeration")]
    for pattern, desc in enum_patterns:
        if pattern in cmd_lower:
            return _reject(
                "Network Security",
                f"{desc} can reveal internal network topology",
                "Use 'tmsh show ltm pool members' to check specific pool member connectivity",
                "Full network enumeration exposes internal infrastructure details.",
            )

    # Tunnel creation
    tunnel_patterns = ["create net tunnels", "iptunnel", "create net vxlan"]
    for pattern in tunnel_patterns:
        if pattern in cmd_lower:
            return _reject(
                "Network Security",
                "tunnel creation can bypass network security boundaries",
                "Use existing network configuration — check with 'tmsh list net tunnels'",
                "Unauthorized tunnels can enable traffic interception.",
            )

    return None


def _check_privilege_escalation(command: str, context: str) -> str | None:
    """Block shell escapes, user modifications, cron, and kernel operations."""
    cmd_lower = command.lower()

    # Shell escapes from TMSH — "run util" can invoke arbitrary commands
    shell_escapes = ["run util bash", "run util /bin/bash", "run util sh", "run util /bin/sh",
                     "run util cat", "run util more", "run util less", "run util head", "run util tail",
                     "bash -c", "bash -i"]
    # Broad "run util" check — only allow known safe utilities
    if "run util" in cmd_lower:
        safe_run_utils = {"run util bigpipe", "run util dig", "run util ping", "run util traceroute"}
        if not any(cmd_lower.strip().startswith(safe) or f"tmsh {safe}" in cmd_lower for safe in safe_run_utils):
            return _reject(
                "Privilege Escalation",
                "'run util' can execute arbitrary system commands and bypass security controls",
                "Use f5_bash for safe read-only diagnostics, or f5_tmsh for TMSH commands",
                "TMSH 'run util' is a known privilege escalation vector.",
            )
    for pattern in shell_escapes:
        if pattern in cmd_lower:
            return _reject(
                "Privilege Escalation",
                f"'{pattern}' is a shell escape that bypasses command restrictions",
                "Use f5_bash for bash commands or f5_tmsh for TMSH commands directly",
                "Shell escapes can bypass security controls and audit logging.",
            )

    # Cron / scheduled tasks
    cron_patterns = ["crontab", "modify sys cron", "create sys cron", r"\bat\b"]
    for pattern in cron_patterns:
        if pattern.startswith("\\"):
            if re.search(pattern, cmd_lower):
                return _reject(
                    "Privilege Escalation",
                    "scheduled task creation is not allowed",
                    "Execute commands directly rather than scheduling them",
                    "Scheduled tasks can maintain persistent unauthorized access.",
                )
        elif pattern in cmd_lower:
            return _reject(
                "Privilege Escalation",
                "scheduled task creation is not allowed",
                "Execute commands directly rather than scheduling them",
                "Scheduled tasks can maintain persistent unauthorized access.",
            )

    # Kernel / setuid operations
    kernel_patterns = ["modprobe", "insmod", "rmmod", "chmod +s", "chmod u+s", "chown root"]
    for pattern in kernel_patterns:
        if pattern in cmd_lower:
            return _reject(
                "Privilege Escalation",
                f"'{pattern}' modifies system-level privileges or kernel modules",
                "Use standard TMSH commands for F5 configuration",
                "Kernel and privilege modifications can compromise the entire system.",
            )

    return None


def _check_exfiltration(command: str, context: str) -> str | None:
    """Block bulk data exports and unauthorized transfers."""
    cmd_lower = command.lower()

    exfil_patterns = [
        ("save sys ucs", "UCS archive creation can package the entire device configuration"),
        ("scp ", "SCP can transfer files to external systems"),
        ("tftp", "TFTP can transfer files to external systems"),
        ("modify sys syslog", "Syslog modification can redirect logs to unauthorized destinations"),
    ]
    for pattern, reason in exfil_patterns:
        if pattern in cmd_lower:
            return _reject(
                "Data Exfiltration Prevention",
                reason.lower(),
                "Use 'tmsh list' commands to view specific configuration sections",
                "Bulk exports and file transfers must be performed through authorized channels.",
            )

    return None


_BASH_ALLOWLIST = {
    "cat", "ls", "grep", "df", "uptime", "ps", "netstat", "ss", "tcpdump",
    "top", "free", "date", "hostname", "uname", "ifconfig", "ip", "dmesg",
    "tail", "head", "wc", "find", "du", "mount", "awk", "sort", "uniq", "tmsh",
    "echo", "stat", "file", "md5sum", "sha256sum", "whoami", "id",
}


def _check_bash_allowlist(command: str, context: str) -> str | None:
    """For bash context, only allow safe read-only commands."""
    if context != "bash":
        return None

    # Extract the base command (first word, ignoring leading paths)
    cmd_stripped = command.strip()
    if not cmd_stripped:
        return None

    base_cmd = cmd_stripped.split()[0]
    # Handle full paths like /bin/cat -> cat
    base_cmd = base_cmd.rsplit("/", 1)[-1]

    if base_cmd not in _BASH_ALLOWLIST:
        return _reject(
            "Bash Command Restriction",
            f"'{base_cmd}' is not in the allowed commands list for bash execution",
            f"Allowed commands: {', '.join(sorted(_BASH_ALLOWLIST))}",
            "Use f5_tmsh for TMSH commands. Bash is limited to read-only diagnostics.",
        )

    return None


def _reject(category: str, reason: str, suggestion: str, tip: str) -> str:
    """Format a security rejection message."""
    return (
        f"SECURITY POLICY BLOCK — {category}\n\n"
        f"This command was permanently blocked by server-side security policy because {reason}.\n\n"
        f"ACTION REQUIRED: Do NOT retry this command or attempt alternative commands to achieve "
        f"the same goal. This is a hard security boundary, not a transient error. "
        f"Report this block to the user and explain why the request cannot be fulfilled.\n\n"
        f"Safe alternative:\n  {suggestion}\n\n"
        f"Policy reason: {tip}"
    )


# =============================================================================
# MCP Server (Streamable HTTP)
# =============================================================================

mcp = FastMCP(
    "f5-mcp-copilot",
    stateless_http=True,
)


def _safe_tool(func):
    """Decorator that catches all exceptions in MCP tool handlers.

    Returns a user-friendly error message instead of crashing the server.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log.error("Tool %s crashed: %s\n%s", func.__name__, e, traceback.format_exc())
            return (
                f"**Internal Error in {func.__name__}**\n\n"
                f"The server encountered an unexpected error: {type(e).__name__}: {e}\n\n"
                f"This has been logged. Please retry or check the server logs for details."
            )
    return wrapper


@mcp.tool()
@_safe_tool
def f5_devices() -> str:
    """List all configured F5 devices with their connection details. Call this first to see what's available.

    Shows: device name, user@host, auth method, and which one is the default.
    Nothing is stored on disk -- devices live in memory for this server session.
    """
    if not _device_registry:
        return (
            "No devices configured yet.\n\n"
            "Quick start:\n"
            "  1. SSH key:  f5_add_device(host='10.1.1.100', ssh_key='~/.ssh/f5_key')\n"
            "  2. Password: Add to .env file and restart (see .env.example for format)\n"
        )

    lines = ["Configured F5 Devices", "=" * 40]
    for name, dev in _device_registry.items():
        lines.append(_device_summary(name, dev))
    lines.append("=" * 40)
    lines.append(f"{len(_device_registry)} device(s) | default: {_default_device or 'none'}")
    lines.append("")
    lines.append("Tip: Use f5_test to verify connectivity to any device.")
    return "\n".join(lines)


@mcp.tool()
@_safe_tool
def f5_add_device(host: str, user: str = "admin", ssh_key: str = "", name: str = "", port: int = 22, set_default: bool = True) -> str:
    """Add an F5 device. Just provide the host and SSH key path.

    For password auth, add the device in your .env file instead (see .env.example).

    Args:
        host: F5 management IP or hostname (e.g. '10.1.1.100')
        user: SSH username (default: 'admin')
        ssh_key: Path to SSH private key (e.g. '~/.ssh/f5_key')
        name: Friendly name (optional, auto-generated from host if blank)
        port: SSH port (default: 22)
        set_default: Make this the default device (default: true)

    Examples:
        f5_add_device(host='10.1.1.100', ssh_key='~/.ssh/f5_key')
        f5_add_device(host='bigip1.lab', user='root', ssh_key='~/.ssh/lab_key', name='lab')
    """
    global _default_device

    if not host or not host.strip():
        return "Error: host is required.\n  Example: f5_add_device(host='10.1.1.100', ssh_key='~/.ssh/f5_key')"

    host = host.strip()
    user = user.strip() or "admin"
    device_name = name.strip() if name else _auto_name(host)

    # Build device config
    device = {"host": host, "user": user, "port": port}

    if ssh_key and ssh_key.strip():
        try:
            expanded = _validate_ssh_key(ssh_key)
        except ValueError:
            return (
                f"SSH key file not found: {os.path.expanduser(ssh_key.strip())}\n\n"
                "Check the path exists on the machine running this MCP server.\n"
                "For password auth, add the device in .env instead (see .env.example)."
            )
        device["key"] = expanded
    else:
        return (
            "Error: ssh_key is required.\n\n"
            "Example:\n"
            f"  f5_add_device(host='{host}', ssh_key='~/.ssh/f5_key')\n\n"
            "For password auth, add the device in .env instead (see .env.example)."
        )

    # Check for duplicate host
    for existing_name, existing_dev in _device_registry.items():
        if existing_dev["host"] == host and existing_dev["port"] == port:
            return (
                f"A device with host {host}:{port} already exists as '{existing_name}'.\n\n"
                f"To update it: f5_update_device(name='{existing_name}', ssh_key='~/.ssh/new_key')\n"
                f"To replace it: f5_remove_device(name='{existing_name}') then add again."
            )

    _device_registry[device_name] = device
    if set_default or not _default_device:
        _default_device = device_name

    # Auto-test connectivity
    test_result = ssh_exec(device, "tmsh show sys version", timeout=5)

    lines = [
        f"Device '{device_name}' added successfully.",
        f"  Host: {user}@{host}:{port}",
        f"  Auth: SSH key ({expanded})",
        f"  Default: {'yes' if _default_device == device_name else 'no'}",
        "",
    ]

    if test_result["success"]:
        version_line = ""
        for line in test_result["output"].splitlines():
            if "Version" in line or "Build" in line:
                version_line = line.strip()
                break
        lines.append(f"  Connectivity: OK" + (f" -- {version_line}" if version_line else ""))
    else:
        lines.append(f"  Connectivity: FAILED -- {test_result['error'][:120]}")
        lines.append("  (Device saved anyway. Fix credentials/network and run f5_test to retry.)")

    return "\n".join(lines)


@mcp.tool()
@_safe_tool
def f5_update_device(name: str, host: str = "", user: str = "", ssh_key: str = "", port: int = 0, set_default: bool = False) -> str:
    """Update an existing F5 device. Only the fields you provide will change.

    Args:
        name: Device name to update (run f5_devices to see names)
        host: New management IP/hostname (blank = keep current)
        user: New SSH username (blank = keep current)
        ssh_key: New SSH key path (blank = keep current)
        port: New SSH port (0 = keep current)
        set_default: Set this device as the new default

    Examples:
        f5_update_device(name='prod', ssh_key='~/.ssh/new_key')
        f5_update_device(name='lab', host='10.1.1.201', port=2222)
    """
    global _default_device

    if name not in _device_registry:
        available = ", ".join(_device_registry.keys()) if _device_registry else "none"
        return f"Device '{name}' not found. Available devices: {available}"

    dev = _device_registry[name]
    changes = []

    if host and host.strip():
        dev["host"] = host.strip()
        changes.append(f"host -> {host.strip()}")

    if user and user.strip():
        dev["user"] = user.strip()
        changes.append(f"user -> {user.strip()}")

    if port and port > 0:
        dev["port"] = port
        changes.append(f"port -> {port}")

    if ssh_key and ssh_key.strip():
        try:
            expanded = _validate_ssh_key(ssh_key)
        except ValueError:
            return (
                f"SSH key file not found: {os.path.expanduser(ssh_key.strip())}\n"
                "Check the path exists on the machine running this MCP server."
            )
        dev.pop("password", None)
        dev["key"] = expanded
        changes.append(f"auth -> SSH key ({expanded})")

    if set_default:
        _default_device = name
        changes.append("set as default")

    if not changes:
        return (
            f"No changes specified for '{name}'.\n"
            f"Current config:\n{_device_summary(name, dev)}\n\n"
            f"Provide at least one field to update: host, user, ssh_key, or port."
        )

    # Re-test connectivity after changes
    test_result = ssh_exec(dev, "tmsh show sys version", timeout=5)
    status = "OK" if test_result["success"] else f"FAILED -- {test_result['error'][:100]}"

    return (
        f"Device '{name}' updated.\n"
        f"  Changes: {', '.join(changes)}\n"
        f"  Current: {_device_summary(name, dev)}\n"
        f"  Connectivity: {status}"
    )


@mcp.tool()
@_safe_tool
def f5_remove_device(name: str) -> str:
    """Remove an F5 device from the session. Credentials are cleared from memory immediately.

    Args:
        name: Device name to remove (run f5_devices to see names)
    """
    global _default_device

    if name not in _device_registry:
        if not _device_registry:
            return "No devices configured. Nothing to remove."
        available = ", ".join(_device_registry.keys())
        return f"Device '{name}' not found. Available devices: {available}"

    host = _device_registry[name]["host"]
    del _device_registry[name]

    if _default_device == name:
        _default_device = next(iter(_device_registry), None)

    remaining = len(_device_registry)
    lines = [
        f"Device '{name}' ({host}) removed. Credentials cleared from memory.",
    ]
    if remaining:
        lines.append(f"  Remaining devices: {remaining} | default: {_default_device or 'none'}")
    else:
        lines.append("  No devices remaining. Add one with f5_add_device.")

    return "\n".join(lines)


@mcp.tool()
@_safe_tool
def f5_set_default(name: str) -> str:
    """Set which F5 device is used by default when no device name is specified.

    Args:
        name: Device name to make default (run f5_devices to see names)
    """
    global _default_device

    if name not in _device_registry:
        if not _device_registry:
            return "No devices configured. Add one first with f5_add_device."
        available = ", ".join(_device_registry.keys())
        return f"Device '{name}' not found. Available devices: {available}"

    _default_device = name
    dev = _device_registry[name]
    return f"Default device set to '{name}' ({dev['user']}@{dev['host']})"


@mcp.tool()
@_safe_tool
def f5_test(device: str = None) -> str:
    """Test SSH connectivity to an F5 device. Runs 'tmsh show sys version' to verify the connection works end-to-end.

    Args:
        device: Device name to test (optional, uses default if blank)
    """
    dev = get_device(device)
    if not dev:
        if not _device_registry:
            return (
                "No devices configured.\n\n"
                "Add one first:\n"
                "  f5_add_device(host='10.1.1.100', ssh_key='~/.ssh/f5_key')"
            )
        target = device or _default_device
        available = ", ".join(_device_registry.keys())
        return f"Device '{target}' not found. Available devices: {available}"

    target_name = device or _default_device
    result = ssh_exec(dev, "tmsh show sys version")
    if result["success"]:
        return f"Device '{target_name}' ({dev['host']}) -- Connected OK\n\n{result['output']}"
    return (
        f"Device '{target_name}' ({dev['host']}) -- Connection FAILED\n\n"
        f"Error: {result['error']}\n\n"
        f"Troubleshooting:\n"
        f"  - Verify host {dev['host']} is reachable from this server\n"
        f"  - Check SSH port {dev.get('port', 22)} is open\n"
        f"  - Verify credentials: user='{dev['user']}', auth={'ssh-key' if dev.get('key') else 'password'}\n"
        f"  - Update with: f5_update_device(name='{target_name}', ssh_key='~/.ssh/new_key')"
    )


@mcp.tool()
@_safe_tool
def f5_tmsh(command: str, device: str = None) -> str:
    """Execute TMSH command on F5. Device is pre-configured - just provide the command."""
    dev = get_device(device)
    if not dev:
        return "No device configured. Run f5_devices to check configuration."

    # Normalize: always use tmsh prefix for security checks and consistency
    cmd = command if command.startswith("tmsh") else f"tmsh {command}"

    rejection = _security_check(cmd, "tmsh")
    if rejection:
        return rejection

    warning = _check_destructive(cmd)

    # ssh_exec auto-detects TMSH shell and retries without prefix if needed
    result = ssh_exec(dev, cmd)

    output = ""
    if warning:
        output += f"{warning}\n\n"
    output += f"**Device:** {dev['host']}\n**Command:** `{cmd}`\n\n"
    if result["success"]:
        output += f"```\n{result['output']}\n```"
    else:
        output += f"**Error:** {result['error']}"
    return output


@mcp.tool()
@_safe_tool
def f5_bash(command: str, device: str = None) -> str:
    """Execute bash command on F5. Device is pre-configured - just provide the command."""
    dev = get_device(device)
    if not dev:
        return "No device configured. Run f5_devices to check configuration."

    rejection = _security_check(command, "bash")
    if rejection:
        return rejection

    result = ssh_exec(dev, command, context="bash")

    output = f"**Device:** {dev['host']}\n**Command:** `{command}`\n\n"
    if result["success"]:
        output += f"```\n{result['output']}\n```"
    else:
        output += f"**Error:** {result['error']}"
    return output


@mcp.tool()
@_safe_tool
def f5_knowledge(query: str) -> str:
    """Search F5 knowledge base for commands and examples. Automatically searches official F5 external documentation (DevCentral, CloudDocs, AskF5 K-articles) when local knowledge is insufficient."""
    content, matched = search_knowledge(query)

    if content:
        output = f"# F5 Knowledge: {query}\n\n{content}"
    else:
        output = ""

    # Supplement with external search when no specific keyword matched
    # (i.e. query fell through to the default quick_reference fallback, or empty)
    if not matched:
        external = search_external_docs(query)
        if external:
            if output:
                output += "\n\n---\n\n# External Documentation\n\n" + external
            else:
                output = f"# F5 External Documentation: {query}\n\n{external}"

    if not output:
        output = f"No information found for '{query}'. Try refining your search terms or use f5_search_docs for a targeted external search."

    return output


@mcp.tool()
@_safe_tool
def f5_search_docs(query: str, source: str = "all") -> str:
    """Search official F5 external documentation. Searches DevCentral community, CloudDocs, AskF5 K-articles, and TMSH reference. Use when local knowledge base doesn't have the answer.

    Args:
        query: Search terms (e.g. 'iRule HTTP redirect', 'AS3 pool declaration', 'SSL profile cipher')
        source: Which source to search - 'all', 'devcentral', 'clouddocs', or 'askf5'
    """
    if source == "all":
        sources = ["clouddocs", "devcentral", "askf5"]
    else:
        sources = [source]

    results = search_external_docs(query, sources=sources)
    if results:
        return f"# F5 Documentation Search: {query}\n\n{results}"

    return f"No external results found for '{query}'. Try different search terms or browse directly:\n- https://community.f5.com\n- https://clouddocs.f5.com\n- https://my.f5.com/manage/s/article"


@mcp.tool()
@_safe_tool
def f5_doc_urls() -> str:
    """Get F5 official documentation URLs and search patterns"""
    refs_file = KNOWLEDGE_DIR / "external_references.md"
    if refs_file.exists():
        return refs_file.read_text()
    return """# F5 Documentation URLs

- **AskF5:** https://my.f5.com/manage/s/article
- **CloudDocs:** https://clouddocs.f5.com
- **TMSH Reference:** https://clouddocs.f5.com/cli/tmsh-reference/latest/
- **DevCentral:** https://community.f5.com
- **iControl REST:** https://clouddocs.f5.com/api/icontrol-rest/
"""


@mcp.tool()
@_safe_tool
def f5_query(question: str, validate: bool = False, device: str = None) -> str:
    """Ask F5 question - returns knowledge (local + external) and optionally validates on device"""
    knowledge, matched = search_knowledge(question)
    output = f"# F5 Knowledge\n\n{knowledge}\n" if knowledge else ""

    # Supplement with external docs when no specific keyword matched
    if not matched:
        external = search_external_docs(question)
        if external:
            output += f"\n\n---\n\n# External Documentation\n\n{external}\n"

    if validate:
        dev = get_device(device)
        if dev:
            q = question.lower()
            cmd = None
            if any(x in q for x in ["pool", "member"]):
                cmd = "tmsh show ltm pool"
            elif any(x in q for x in ["virtual", "vip"]):
                cmd = "tmsh show ltm virtual"
            elif any(x in q for x in ["ha", "failover"]):
                cmd = "tmsh show sys failover"
            elif any(x in q for x in ["ssl", "cert"]):
                cmd = "tmsh list sys crypto cert"
            elif "version" in q:
                cmd = "tmsh show sys version"

            if cmd:
                rejection = _security_check(cmd, "tmsh")
                if rejection:
                    output += f"\n---\n# Security Notice\n{rejection}"
                else:
                    result = ssh_exec(dev, cmd)
                    output += f"\n---\n# Device Validation\n**Command:** `{cmd}`\n"
                    output += f"```\n{result['output'] if result['success'] else result['error']}\n```"

    return output or "No relevant information found."


# =============================================================================
# API Key Auth Middleware
# =============================================================================


class APIKeyMiddleware:
    """Validate API key on /mcp endpoint.

    Skips auth for OPTIONS (CORS preflight), GET, and DELETE requests so that
    VS Code can initialize and tear down the Streamable HTTP transport without
    triggering OAuth discovery.  Tool calls arrive via POST and are always
    authenticated.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            method = scope.get("method", "")
            # Only require API key on POST (actual tool calls / JSON-RPC)
            # GET = SSE session init, DELETE = session teardown, OPTIONS = CORS
            if method in ("OPTIONS", "GET", "DELETE"):
                await self.app(scope, receive, send)
                return
            if path.startswith("/mcp"):
                headers = dict(scope.get("headers", []))
                api_key = headers.get(b"x-api-key", b"").decode()
                if API_KEY and not hmac.compare_digest(api_key.encode(), API_KEY.encode()):
                    response = JSONResponse(
                        {"error": "Unauthorized - invalid or missing API key"},
                        status_code=401,
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


# =============================================================================
# Build Starlette App with Middleware
# =============================================================================


def create_app() -> Starlette:
    """Create Starlette app with MCP, CORS, and API key middleware"""
    mcp_app = mcp.streamable_http_app()

    # Add middleware directly to the MCP app
    mcp_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    mcp_app.add_middleware(APIKeyMiddleware)

    return mcp_app


# =============================================================================
# Entry Point
# =============================================================================

app = create_app()

if __name__ == "__main__":
    import uvicorn

    log.info("F5 MCP Copilot Server starting on http://%s:%s/mcp", SERVER_HOST, SERVER_PORT)
    log.info("API Key auth: %s", "enabled" if API_KEY else "disabled")
    log.info("Knowledge dir: %s (%s)", KNOWLEDGE_DIR, "found" if KNOWLEDGE_DIR.exists() else "missing")

    if _device_registry:
        log.info("Devices loaded: %d", len(_device_registry))
        for dname, dconf in _device_registry.items():
            auth_type = "[ssh-key]" if dconf.get("key") else "[password]" if dconf.get("password") else "[no-auth]"
            default_tag = " (default)" if dname == _default_device else ""
            log.info("  %s%s: %s@%s %s", dname, default_tag, dconf['user'], dconf['host'], auth_type)
    else:
        log.warning("No F5 devices configured - set F5_HOST in .env or add F5_DEVICE_*_HOST entries")

    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        log_level="info",
        access_log=True,
    )
