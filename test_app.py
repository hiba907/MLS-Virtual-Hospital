"""
test_app.py — MLS Virtual Hospital · Pytest Suite
==================================================

Problems fixed vs the original:
  1. call_ai(system, messages, ...) — two required args, not one string.
     The original tests called call_ai("fever") which would crash immediately.
     We test through the thin wrapper call_ai_simple() defined below so tests
     stay independent of Streamlit session state and the credit system.

  2. Direct `from app import call_ai` pulls in Streamlit at import time → crash
     outside a running Streamlit server. We mock every Streamlit symbol and the
     credits gate before importing the real function.

  3. The credit gate (can_use_credits) would always fail in a test environment
     because there is no authenticated session. We patch it to always allow.

  4. "error" not in result.lower() was fragile — call_ai legitimately returns
     "!ERR ..." strings on API failure. We now check for that sentinel instead.

  5. Medical keyword assertions used too-strict word lists; extended to cover
     real Gemini phrasing ("myocardial", "pneumonia", "respiratory" etc.).

Run:
  pytest test_app.py -v
  pytest test_app.py -v -k "not live"   # skip tests that hit the real API
"""

import sys
import types
import pytest
from unittest.mock import patch, MagicMock

# ─────────────────────────────────────────────────────────────────────────────
# 1. Stub out Streamlit BEFORE app.py is imported.
#    app.py calls st.set_page_config() and st.session_state at module level,
#    which crashes outside a Streamlit server.
# ─────────────────────────────────────────────────────────────────────────────

def _make_streamlit_stub():
    st = types.ModuleType("streamlit")

    # session_state: behaves like a dict
    class _SS(dict):
        def __getattr__(self, k):
            try: return self[k]
            except KeyError: raise AttributeError(k)
        def __setattr__(self, k, v): self[k] = v
        def get(self, k, d=None): return super().get(k, d)
        def pop(self, k, *a): return super().pop(k, *a) if a else super().pop(k)

    st.session_state = _SS()

    # Secrets: return empty string for everything
    st.secrets = MagicMock()
    st.secrets.get = lambda k, d="": d

    # UI calls — all no-ops
    for name in [
        "set_page_config", "markdown", "write", "info", "warning", "error",
        "success", "spinner", "sidebar", "columns", "tabs", "expander",
        "text_input", "text_area", "selectbox", "multiselect", "button",
        "toggle", "file_uploader", "rerun", "stop", "metric", "progress",
        "dataframe", "plotly_chart", "image", "caption", "title", "header",
        "subheader", "divider",
    ]:
        setattr(st, name, MagicMock(return_value=None))

    # context managers (sidebar, columns, tabs, expander, spinner, form)
    class _CM:
        def __enter__(self): return MagicMock()
        def __exit__(self, *_): pass

    st.sidebar     = _CM()
    st.spinner     = lambda *a, **kw: _CM()
    st.columns     = lambda *a, **kw: [_CM(), _CM()]
    st.tabs        = lambda labels: [_CM() for _ in labels]
    st.expander    = lambda *a, **kw: _CM()

    # components sub-module
    comp = types.ModuleType("streamlit.components.v1")
    comp.html = MagicMock()
    sys.modules["streamlit.components.v1"] = comp
    sys.modules["streamlit.components"]    = types.ModuleType("streamlit.components")

    sys.modules["streamlit"] = st
    return st


_st_stub = _make_streamlit_stub()


# ─────────────────────────────────────────────────────────────────────────────
# 2. Stub heavy optional dependencies that may not be installed in the
#    test environment (plotly, fpdf, transformers, openpyxl …)
# ─────────────────────────────────────────────────────────────────────────────

for _mod in ["plotly", "plotly.express", "plotly.graph_objects",
             "fpdf", "transformers", "torch",
             "openpyxl", "openpyxl.styles"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Patch the credit gate so every test call is allowed, and patch get_api_key
#    to return a dummy value (real API calls are isolated further per test).
# ─────────────────────────────────────────────────────────────────────────────

with (
    patch("builtins.__import__", side_effect=lambda name, *a, **kw: sys.modules.get(name, __import__(name, *a, **kw))),
):
    pass  # just warming the import machinery


# Lazy import of app — happens after all stubs are registered
@pytest.fixture(scope="session")
def app_module():
    """Import app exactly once per test session, with all stubs in place."""
    with (
        patch.dict("sys.modules", {"streamlit": _st_stub}),
    ):
        import importlib
        if "app" in sys.modules:
            app = sys.modules["app"]
        else:
            import app  # noqa: PLC0415
        # Patch credits gate to always allow
        app.can_use_credits = lambda *a, **kw: (True, "")
        app.use_credits     = lambda *a, **kw: (True, "")
        return app


# ─────────────────────────────────────────────────────────────────────────────
# 4. Thin wrapper that matches the OLD test signature: call_ai_simple(text)
#    Maps a single symptom string into the real call_ai(system, messages) shape.
# ─────────────────────────────────────────────────────────────────────────────

def call_ai_simple(text: str, app) -> str:
    """
    Wraps the real call_ai(system, messages) so tests can pass a single string.
    This is the adapter the original test_app.py was missing.
    """
    system   = "You are a clinical decision support assistant. Be concise."
    messages = [{"role": "user", "content": text}] if text.strip() else \
               [{"role": "user", "content": "No symptoms provided. What should I do?"}]
    return app.call_ai(system, messages, max_tokens=300, credit_type="chat")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Shared mock for tests that should NOT hit the real network
# ─────────────────────────────────────────────────────────────────────────────

MOCK_RESPONSES = {
    "fever":                "Possible causes include viral infection, bacterial infection, or inflammatory conditions.",
    "headache":             "Differential includes tension headache, migraine, and sinusitis.",
    "chest pain":           "Consider cardiac causes: angina, myocardial infarction. Also pulmonary embolism.",
    "abdominal pain":       "Differential: appendicitis, gastritis, bowel obstruction.",
    "severe abdominal pain":"Urgent evaluation needed. Consider peritonitis or mesenteric ischemia.",
    "fever and cough":      "Likely respiratory viral infection or pneumonia.",
    "":                     "Please provide symptom information for clinical assessment.",
}

def _mock_gemini_response(text: str) -> str:
    """Return a canned response without hitting the network."""
    key = text.strip().lower()
    for k, v in MOCK_RESPONSES.items():
        if k and k in key:
            return v
    return MOCK_RESPONSES.get(key, "Clinical assessment requires further information.")


# ═════════════════════════════════════════════════════════════════════════════
# TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestBasicBehaviour:
    """
    Unit tests — network is mocked. Fast, deterministic, run in CI.
    """

    def _patched_call(self, app, text: str) -> str:
        """Call with a mocked requests.post so no real HTTP is made."""
        import requests as _req

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "candidates": [{
                "content": {
                    "parts": [{"text": _mock_gemini_response(text)}]
                }
            }]
        }

        with patch.object(_req, "post", return_value=fake_resp):
            with patch.object(app, "get_api_key", return_value="test-key-123"):
                return call_ai_simple(text, app)

    # ── 1. Basic response ─────────────────────────────────────────────────
    def test_basic_response(self, app_module):
        result = self._patched_call(app_module, "fever")
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    # ── 2. Parametrised stability ─────────────────────────────────────────
    @pytest.mark.parametrize("symptom", [
        "fever", "headache", "chest pain", "abdominal pain", ""
    ])
    def test_multiple_inputs(self, app_module, symptom):
        result = self._patched_call(app_module, symptom)
        assert result is not None
        assert isinstance(result, str)

    # ── 3. No crash ───────────────────────────────────────────────────────
    def test_no_crash(self, app_module):
        try:
            self._patched_call(app_module, "random input 123")
        except Exception as e:
            pytest.fail(f"call_ai_simple raised unexpectedly: {e}")

    # ── 4. Output sanity — no error sentinel ──────────────────────────────
    def test_output_not_error_sentinel(self, app_module):
        """
        Fixed: original checked 'error' not in result which is too broad.
        The real call_ai returns '!ERR ...' on failure — test for that instead.
        """
        result = self._patched_call(app_module, "severe abdominal pain")
        assert result is not None
        assert len(result.strip()) > 5
        assert not result.startswith("!ERR"), f"Got error sentinel: {result}"

    # ── 5. Medical keyword relevance ──────────────────────────────────────
    @pytest.mark.parametrize("symptom,expected_keywords", [
        (
            "chest pain",
            ["heart", "cardiac", "angina", "myocardial", "ischemia",
             "coronary", "pericarditis", "pulmonary"],
        ),
        (
            "fever and cough",
            ["infection", "flu", "viral", "respiratory", "pneumonia",
             "bacterial", "bronchitis"],
        ),
    ])
    def test_medical_keywords(self, app_module, symptom, expected_keywords):
        result = self._patched_call(app_module, symptom).lower()
        matched = [kw for kw in expected_keywords if kw in result]
        assert matched, (
            f"No expected medical keyword found for '{symptom}'.\n"
            f"  Expected one of: {expected_keywords}\n"
            f"  Got: {result[:300]}"
        )

    # ── 6. Empty input ────────────────────────────────────────────────────
    def test_empty_input(self, app_module):
        result = self._patched_call(app_module, "")
        assert result is not None
        assert isinstance(result, str)
        # Should not crash, and should not be an error sentinel
        assert not result.startswith("!ERR"), f"Empty input caused error: {result}"

    # ── 7. Long input stress test ─────────────────────────────────────────
    def test_long_input(self, app_module):
        """Gemini has a context window limit. call_ai should handle long input gracefully."""
        long_text = "pain " * 500   # 2500 chars — within most model limits
        result = self._patched_call(app_module, long_text)
        assert result is not None
        assert isinstance(result, str)

    # ── 8. Credit gate bypass works ───────────────────────────────────────
    def test_credits_not_blocking(self, app_module):
        """
        In a test environment there is no session. Verify our patch means
        the credit gate never returns the !ERR_CREDITS sentinel.
        """
        result = self._patched_call(app_module, "headache")
        assert not result.startswith("!ERR_CREDITS"), (
            "Credit gate blocked the call — patch did not apply correctly."
        )

    # ── 9. Model fallback — simulate primary model 429, fallback succeeds ─
    def test_model_fallback(self, app_module):
        """
        If the primary model returns 429 (rate limit), call_ai should try
        the next model in GEMINI_MODELS_CASCADE automatically.
        """
        import requests as _req

        call_count = {"n": 0}

        def _side_effect(*a, **kw):
            call_count["n"] += 1
            resp = MagicMock()
            if call_count["n"] == 1:
                resp.status_code = 429   # primary rate-limited
            else:
                resp.status_code = 200
                resp.json.return_value = {
                    "candidates": [{"content": {"parts": [{"text": "Fallback response OK"}]}}]
                }
            return resp

        with patch.object(_req, "post", side_effect=_side_effect):
            with patch.object(app_module, "get_api_key", return_value="test-key-123"):
                result = call_ai_simple("fever", app_module)

        assert "Fallback response OK" in result, (
            f"Expected fallback model response, got: {result}"
        )
        assert call_count["n"] >= 2, "Expected at least 2 API calls (primary + fallback)"

    # ── 10. All models fail → returns !ERR sentinel, does not raise ───────
    def test_all_models_fail_gracefully(self, app_module):
        import requests as _req

        fail_resp = MagicMock()
        fail_resp.status_code = 500

        with patch.object(_req, "post", return_value=fail_resp):
            with patch.object(app_module, "get_api_key", return_value="test-key-123"):
                result = call_ai_simple("fever", app_module)

        assert result.startswith("!ERR"), (
            f"Expected !ERR sentinel when all models fail, got: {result}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# LIVE tests — only run when GEMINI_API_KEY is set in the environment.
# Skip gracefully in CI if key is absent.
# pytest test_app.py -v -m live
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.live
class TestLiveAPI:
    """
    These tests hit the real Gemini API.
    Requires GEMINI_API_KEY env variable to be set.
    Mark: pytest -m live
    """

    @pytest.fixture(autouse=True)
    def require_api_key(self, app_module):
        import os
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            pytest.skip("GEMINI_API_KEY not set — skipping live API tests")
        with patch.object(app_module, "get_api_key", return_value=key):
            yield

    def test_live_basic_response(self, app_module):
        result = call_ai_simple("fever", app_module)
        assert isinstance(result, str)
        assert len(result.strip()) > 10
        assert not result.startswith("!ERR"), f"Live API error: {result}"

    def test_live_meningitis_ddx(self, app_module):
        result = call_ai_simple(
            "19yo, severe headache, neck stiffness, fever 39.8°C, photophobia, petechial rash",
            app_module,
        ).lower()
        assert "meningitis" in result, (
            f"Expected 'meningitis' in live DDx response. Got: {result[:300]}"
        )

    def test_live_stemi_recognition(self, app_module):
        result = call_ai_simple(
            "55yo male, chest pain 45 min, ST elevation leads II III aVF",
            app_module,
        ).lower()
        assert any(kw in result for kw in ["stemi", "infarction", "inferior"]), (
            f"Expected STEMI recognition. Got: {result[:300]}"
        )

    def test_live_empty_input_no_crash(self, app_module):
        result = call_ai_simple("", app_module)
        assert isinstance(result, str)
        assert not result.startswith("!ERR")