"""NI-062 static sink and secret audit of the API source tree.

Offline AST/grep-style enumeration with zero runtime behavior change:

- the ONLY subprocess use in ``apps/api/src`` is the pinned NI-057 renderer
  boundary in ``exports/charts.py``, invoked as a fixed ARGV list with no
  shell anywhere, and no os.system/os.popen/eval/exec sink exists;
- outbound HTTP clients exist only in the three documented, operator-gated
  or configured-URL modules (JWKS fetcher, provider finalized-header
  collector, capability probe) — no route, service or repository opens a
  network connection and no request model can name a fetch target;
- no credential material or provider secret shape is hardcoded in source
  and no logging call embeds a token-shaped literal.
"""

import ast
import json
import re
import unittest
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src/near_api"


def _require_sources() -> None:
    """Guard against a vacuous scan: the audited tree must exist."""
    if not SRC_ROOT.is_dir() or not any(SRC_ROOT.rglob("*.py")):
        raise RuntimeError(f"The audited source tree is missing: {SRC_ROOT}")


_require_sources()

ALLOWED_HTTP_MODULES = (
    "auth/jwks.py",  # fetches ONLY the configured https JWKS URL
    "ingestion/providers/finalized_header.py",  # operator-gated collector (stopped by default)
    "ingestion/capabilities/probe.py",  # operator capability probe, injected transport
    "ai/adapter.py",  # NI-065 optional commentary adapter: ONLY the operator-configured
                      # NEAR_AI_COMMENTARY_ENDPOINT (disabled by default, injected
                      # transport in tests, finalized-header bounds, no retry)
)

FORBIDDEN_CALL_NAMES = {"os.system", "os.popen", "eval", "exec", "compile"}
HTTP_MODULE_NAMES = {"httpx", "urllib.request", "requests"}
# Top-level request parameter/body-property names that would let a request
# name a fetch target. Nested rich-text hrefs are stored content, rendered
# inert by the schema + export boundaries (see test_security_untrusted_content).
FETCH_TARGET_PARAM_PATTERN = re.compile(
    r"^(url|endpoint|webhook|callback|redirect_uri|redirect_to|fetch|target_url|"
    r"next_url|image_url|avatar_url)$", re.IGNORECASE)


def python_files() -> dict[str, Path]:
    return {str(path.relative_to(SRC_ROOT)): path
            for path in sorted(SRC_ROOT.rglob("*.py"))}


def parse(relative: str) -> ast.Module:
    return ast.parse(python_files()[relative].read_text("utf-8"))


def call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = call_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


class SubprocessSinkTests(unittest.TestCase):
    """No shell, no dynamic execution; the renderer is the only subprocess."""

    def test_subprocess_is_confined_to_the_renderer_boundary(self):
        users = set()
        for relative, path in python_files().items():
            tree = ast.parse(path.read_text("utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(
                        alias.name == "subprocess" for alias in node.names):
                    users.add(relative)
                if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                    users.add(relative)
        self.assertEqual(users, {"exports/charts.py"})

    def test_renderer_invocation_is_a_fixed_argv_list_without_shell(self):
        tree = parse("exports/charts.py")
        runs = [node for node in ast.walk(tree)
                if isinstance(node, ast.Call) and call_name(node.func) == "subprocess.run"]
        self.assertEqual(len(runs), 1)
        run = runs[0]
        self.assertIsInstance(run.args[0], (ast.List, ast.Tuple))
        keywords = {keyword.arg: keyword.value for keyword in run.keywords}
        self.assertNotIn("shell", keywords)
        self.assertIn("input", keywords)  # typed payload travels on STDIN

    def test_no_dynamic_execution_or_shell_sinks_anywhere(self):
        for relative, path in python_files().items():
            tree = ast.parse(path.read_text("utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = call_name(node.func)
                    if name in FORBIDDEN_CALL_NAMES:
                        self.fail(f"{relative} uses {name}")
                if isinstance(node, ast.keyword) and node.arg == "shell":
                    self.fail(f"{relative} passes shell=True")


class NetworkSinkTests(unittest.TestCase):
    """Outbound HTTP is confined to the documented operator/config modules."""

    def test_http_clients_exist_only_in_allowed_modules(self):
        users = set()
        for relative, path in python_files().items():
            tree = ast.parse(path.read_text("utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    name = call_name(node.func)
                    if name.split(".")[0] in HTTP_MODULE_NAMES or (
                            name.startswith(("httpx.", "urllib.request."))):
                        users.add(relative)
        self.assertEqual(users, set(ALLOWED_HTTP_MODULES))

    def test_jwks_fetcher_targets_only_the_configured_https_url(self):
        source = python_files()["auth/jwks.py"].read_text("utf-8")
        # The cache constructor refuses any non-https URL, redirects are
        # never followed, and the fetcher has no other target expression.
        self.assertIn('url.startswith("https://")', source)
        self.assertIn("follow_redirects=False", source)
        tree = parse("auth/jwks.py")
        gets = [node for node in ast.walk(tree)
                if isinstance(node, ast.Call) and call_name(node.func) == "httpx.get"]
        self.assertEqual(len(gets), 1)
        self.assertIsInstance(gets[0].args[0], ast.Name)
        self.assertEqual(gets[0].args[0].id, "url")

    def test_no_openapi_request_surface_names_a_fetch_target(self):
        from near_api.main import app

        schema = app.openapi()
        offending: list[str] = []
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                if method not in {"get", "post", "patch", "delete", "put"}:
                    continue
                for parameter in operation.get("parameters", []):
                    if FETCH_TARGET_PARAM_PATTERN.match(parameter.get("name", "")):
                        offending.append(f"{method.upper()} {path} param {parameter['name']}")
                body = operation.get("requestBody", {}).get("content", {})
                for media in body.values():
                    properties = (media.get("schema", {})
                                  .get("properties", media.get("schema", {})))
                    if not isinstance(properties, dict):
                        continue
                    for name in properties:
                        if FETCH_TARGET_PARAM_PATTERN.match(str(name)):
                            offending.append(f"{method.upper()} {path} body {name}")
        self.assertEqual(offending, [])


class SecretAndLoggingScanTests(unittest.TestCase):
    """No hardcoded credential shapes; no token-shaped logging literals."""

    SECRET_SHAPES = (
        "sb_secret_", "sb_publishable_", "sk_live_", "sk_test_", "-----BEGIN PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----", "-----BEGIN EC PRIVATE KEY-----",
        "supabase_service_role", "SERVICE_ROLE", "api_key=", "apikey=",
    )
    TOKEN_LOG_PATTERN = re.compile(
        r"(access_token|refresh_token|authorization|password|signing_secret)",
        re.IGNORECASE)

    def test_no_credential_material_in_source(self):
        for relative, path in python_files().items():
            content = path.read_text("utf-8")
            for shape in self.SECRET_SHAPES:
                if shape in content:
                    self.fail(f"{relative} contains hardcoded credential shape {shape}")

    def test_logging_and_print_calls_never_embed_token_literals(self):
        offenders: list[str] = []
        for relative, path in python_files().items():
            tree = ast.parse(path.read_text("utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, (
                        ast.Name, ast.Attribute)):
                    name = call_name(node.func)
                    if name in {"print", "logging.info", "logging.warning",
                                "logging.error", "logger.info", "logger.warning",
                                "logger.error", "logging.debug", "logger.debug"}:
                        for argument in node.args:
                            if isinstance(argument, ast.Constant) and \
                                    isinstance(argument.value, str) and \
                                    self.TOKEN_LOG_PATTERN.search(argument.value):
                                offenders.append(f"{relative}: {argument.value[:60]}")
        self.assertEqual(offenders, [])

    def test_settings_are_environment_sourced_not_hardcoded(self):
        # The auth/database configuration modules read settings objects; no
        # default credential value may exist in source.
        for relative in ("auth_settings.py", "settings.py"):
            content = python_files()[relative].read_text("utf-8")
            for shape in self.SECRET_SHAPES:
                self.assertNotIn(shape, content)


if __name__ == "__main__":
    unittest.main()
