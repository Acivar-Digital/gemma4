# 05 — The 14-Task Evaluation Gauntlet

> Verified archetypal defect matrix sampled from the 129 tasks in `tasks.jsonl`.
> Recorded in Beads via `bd recall gauntlet-14-task-suite`.
> All 14 tasks have 100% complete sidecars (`snapshots/*.tgz`, `graphs/*.json`, `embeddings/*.npz`).

---

## Matrix Overview

| # | Task ID | Repository | Defect Category | Target Module | Container B Test Target |
|---|---|---|---|---|---|
| 1 | `rich_4076` | `Textualize/rich` | String Boundaries & Delimiters | `rich/ansi.py` | `tests/test_ansi.py::test_decode` |
| 2 | `requests_6589` | `psf/requests` | String Boundaries & Byte Counting | `src/requests/utils.py` | `tests/test_requests.py::test_content_length_for_string_data_counts_bytes` |
| 3 | `requests_7328` | `psf/requests` | Protocol Invariants & State Reference Safety | `src/requests/sessions.py` | `tests/test_requests.py::test_redirect_history_no_self_reference` |
| 4 | `fastapi_15588` | `fastapi/fastapi` | Protocol Invariants & State Reference Safety | `fastapi/sse.py` | `tests/test_sse.py::test_server_sent_event_single_line_fields_reject_newlines` |
| 5 | `rich_4077` | `Textualize/rich` | Object Wrappers & Multi-File Diffs | `rich/file_proxy.py` | `tests/test_file_proxy.py::test_isatty` |
| 6 | `fastapi_14986` | `fastapi/fastapi` | Object Wrappers & Multi-File Diffs | `fastapi/applications.py`, `fastapi/openapi/docs.py` | `tests/test_swagger_ui_escape.py` |
| 7 | `fastapi_14794` | `fastapi/fastapi` | Dependency Injection & Type Annotations | `fastapi/dependencies/utils.py` | `tests/test_response_dependency.py::test_response_with_depends_annotated` |
| 8 | `fastapi_14786` | `fastapi/fastapi` | Schema Contracts & Pipeline Automation | `fastapi/security/utils.py` | `tests/test_security_http_base.py` |
| 9 | `rich_3278` | `Textualize/rich` | String Boundaries & Escape Sequences | `rich/ansi.py` | `tests/test_ansi.py::test_strip_private_es` |
| 10 | `rich_3894` | `Textualize/rich` | Object Wrappers & Introspection | `rich/_inspect.py` | `tests/test_inspect.py::test_qualname_in_slots` |
| 11 | `requests_7315` | `psf/requests` | Protocol Invariants & URL Normalization | `src/requests/adapters.py` | `tests/test_adapters.py::test_request_url_handles_leading_path_separators` |
| 12 | `requests_7433` | `psf/requests` | Byte Counting & Stream Detection | `src/requests/models.py` | `tests/test_requests.py::test_getattr_proxy_stream_follows_redirect` |
| 13 | `fastapi_14258` | `fastapi/fastapi` | Protocol Invariants & Circular Ref Safety | `fastapi/routing.py` | `tests/test_router_circular_import.py::test_router_circular_import` |
| 14 | `fastapi_5077` | `fastapi/fastapi` | Dependency Injection & Function Wrappers | `fastapi/dependencies/utils.py` | `tests/test_wrapped_method_forward_reference.py::test_wrapped_method_type_inference` |

---

## Detailed Task Specifications

### Category 1: String Boundaries, Delimiters & Byte Encoding

#### 1. `rich_4076` (`Textualize/rich`)
* **Problem**: `AnsiDecoder.decode()` uses `terminal_text.splitlines()`, which discards trailing newlines and fails to preserve terminal formatting boundaries.
* **Fix**: Replace line splitting with regex lookbehind `re.split(r"(?<=\n)", terminal_text)` and strip trailing newlines cleanly.
* **Container B Test**: `tests/test_ansi.py`
  ```python
  expected = [
      Text("Hello"),
      Text("foo", spans=[Span(0, 3, Style.parse("bold"))]),
      Text("bar", spans=[Span(0, 3, Style.parse("link http://example.org"))]),
      Text("red", spans=[Span(0, 3, Style.parse("#ff0000 on color(200)"))]),
      Text("red", spans=[Span(0, 3, Style.parse("color(200) on #ff0000"))]),
      Text(""),  # Trailing newline must produce an empty line
  ]
  assert lines == expected
  ```

#### 2. `requests_6589` (`psf/requests`)
* **Problem**: `super_len` returns character length `len(str)` instead of encoded UTF-8 byte count, emitting incorrect `Content-Length` headers for multi-byte Unicode strings.
* **Fix**: Count encoded UTF-8 bytes for string inputs in `super_len`.
* **Container B Test**: `tests/test_requests.py`
  ```python
  data = "This is a string containing multi-byte UTF-8 ☃️"
  length = str(len(data.encode("utf-8")))
  req = requests.Request("POST", httpbin("post"), data=data)
  p = req.prepare()
  assert p.headers["Content-Length"] == length
  ```

---

### Category 2: Protocol Invariants & State Reference Safety

#### 3. `requests_7328` (`psf/requests`)
* **Problem**: When resolving redirects, the current `Response` is unintentionally appended to its own `response.history` list, causing a self-referential cycle and recursion/serialization errors.
* **Fix**: Ensure `history` copies only preceding redirect responses and never includes `self`.
* **Container B Test**: `tests/test_requests.py`
  ```python
  for i, resp in enumerate(r.history):
      assert resp not in resp.history
      assert resp.history == r.history[:i]
  ```

#### 4. `fastapi_15588` (`fastapi/fastapi`)
* **Problem**: Server-Sent Event (SSE) fields (`event`, `id`) accept raw newline characters (`\n`, `\r`, `\r\n`), allowing stream injection attacks that corrupt SSE framing.
* **Fix**: Validate that `event` and `id` single-line fields reject newline sequences with `ValueError`.
* **Container B Test**: `tests/test_sse.py`
  ```python
  with pytest.raises(ValueError, match=f"SSE '{field_name}' must be a single line"):
      ServerSentEvent(data="test", **{field_name: value})
  ```

---

### Category 3: Object Wrappers & Multi-File Diffs

#### 5. `rich_4077` (`Textualize/rich`)
* **Problem**: `FileProxy.isatty` returns `self.__console.is_terminal` rather than delegating `isatty()` to the underlying wrapped file descriptor, breaking terminal detection.
* **Fix**: Delegate `isatty()` directly to the wrapped file object with fallback handling.
* **Container B Test**: `tests/test_file_proxy.py`
  ```python
  class TTYFile:
      def isatty(self) -> bool:
          return True

  file = TTYFile()
  console = Console()
  file_proxy = FileProxy(console, file)
  assert file_proxy.isatty() is True
  ```

#### 6. `fastapi_14986` (`fastapi/fastapi`)
* **Problem**: Swagger UI parameters and OAuth configurations are not properly HTML/JSON-escaped in the rendered HTML, exposing applications to XSS via crafted endpoints or titles.
* **Fix**: 2-file coordinated patch in `fastapi/applications.py` and `fastapi/openapi/docs.py` using `jsonable_encoder` and `escape` shims.
* **Container B Test**: `tests/test_swagger_ui_escape.py`
  ```python
  html = get_swagger_ui_html(
      openapi_url="/openapi.json",
      title="Test",
      swagger_ui_parameters={"customKey": "<img src=x onerror=alert(1)>"},
  )
  body = html.body.decode()
  assert "<img src=x onerror=alert(1)>" not in body
  assert "\\u003cimg" in body
  ```

---

### Category 4: Dependency Injection & Specification Contracts

#### 7. `fastapi_14794` (`fastapi/fastapi`)
* **Problem**: Using `Response` (or special non-param types like `Request`, `BackgroundTasks`) as a type hint with `Depends` failed with `AssertionError: Cannot specify `Depends` for type Response` in `analyze_param()`.
* **Fix**: In `fastapi/dependencies/utils.py`, update `analyze_param()` to only apply special handling when `depends is None`, removing the assertion and allowing explicit dependency injection to resolve the dependency.
* **Container B Test**: `tests/test_response_dependency.py::test_response_with_depends_annotated`
  ```python
  def test_response_with_depends_annotated():
      """Response type hint should work with Annotated[Response, Depends(...)]."""
      app = FastAPI()

      def modify_response(response: Response) -> Response:
          response.headers["X-Custom"] = "modified"
          return response

      @app.get("/")
      def endpoint(response: Annotated[Response, Depends(modify_response)]):
          return {"status": "ok"}

      client = TestClient(app)
      response = client.get("/")
      assert response.headers["X-Custom"] == "modified"
  ```

#### 8. `fastapi_14786` (`fastapi/fastapi`)
* **Problem**: Whitespaces in `Authorization` header credentials are not stripped in `get_authorization_scheme_param()`, violating RFC 6750 specifications.
* **Fix**: Strip trailing/leading whitespaces from the extracted `param` credential in `fastapi/security/utils.py`.
* **Container B Test**: `tests/test_security_http_base.py::test_security_http_base_with_whitespaces`
  ```python
  response = client.get("/users/me", headers={"Authorization": "Other  foobar "})
  assert response.status_code == 200, response.text
  assert response.json() == {"scheme": "Other", "credentials": "foobar"}
  ```

---

### Category 5: Expansion Cohort (Archetypal Challenger Tasks)

#### 9. `rich_3278` (`Textualize/rich`)
* **Problem**: Problematic private ANSI escape sequences (`\x1b[0-?]`) leak through terminal output rather than being stripped cleanly by the ANSI parser.
* **Fix**: In `rich/ansi.py`, update `re_ansi` regex pattern to include `(?:\x1b[0-?])|`.
* **Container B Test**: `tests/test_ansi.py::test_strip_private_es`
  ```python
  @pytest.mark.parametrize("code", [*"0123456789:;<=>?"])
  def test_strip_private_escape_sequences(code):
      text = Text.from_ansi(f"\x1b{code}Hello")
      assert str(text) == "Hello"
  ```

#### 10. `rich_3894` (`Textualize/rich`)
* **Problem**: Objects with unusual `__qualname__` attribute types (e.g. non-string or descriptor slots in classes) crash `rich._inspect._get_signature` during object introspection.
* **Fix**: In `rich/_inspect.py`, check `isinstance(qualname, str)` and fall back to `__name__` or default name.
* **Container B Test**: `tests/test_inspect.py::test_qualname_in_slots`
  ```python
  @lru_cache
  class Klass:
      __slots__ = ("__qualname__",)
  inspect(Klass)  # Must not raise
  ```

#### 11. `requests_7315` (`psf/requests`)
* **Problem**: S3 presigned URLs with keys starting with `/` (e.g. `https://bucket.s3.amazonaws.com//key_name`) have their leading double slash collapsed to a single slash, corrupting signature validation.
* **Fix**: In `src/requests/adapters.py`, remove the URL manipulation in `request_url()` that collapsed `//` to `/`.
* **Container B Test**: `tests/test_adapters.py::test_request_url_handles_leading_path_separators`
  ```python
  a = requests.adapters.HTTPAdapter()
  p = requests.Request(method="GET", url="http://127.0.0.1:10000//v:h").prepare()
  assert "//v:h" == a.request_url(p, {})
  ```

#### 12. `requests_7433` (`psf/requests`)
* **Problem**: File-like stream wrappers utilizing `__getattr__` delegation do not directly implement `__iter__`, causing `prepare_body()` to fail stream detection and fail redirect body replay.
* **Fix**: In `src/requests/models.py`, check `isinstance(data, Iterable) or hasattr(data, "__iter__")` in `prepare_body()`.
* **Container B Test**: `tests/test_requests.py::test_getattr_proxy_stream_follows_redirect`
  ```python
  class AttrProxy:
      def __init__(self):
          self._file = io.BytesIO(b"data")
      def __getattr__(self, name):
          return getattr(self._file, name)
  r = requests.post(httpbin("redirect-to?url=/post&status_code=307"), data=AttrProxy())
  assert r.json()["data"] == "data"
  ```

#### 13. `fastapi_14258` (`fastapi/fastapi`)
* **Problem**: Calling `router.include_router(router)` recursively includes an `APIRouter` instance into itself, causing infinite loops / recursion errors without a clear error message.
* **Fix**: In `fastapi/routing.py`, add `assert self is not router, "Cannot include the same APIRouter instance into itself. Did you mean to include a different router?"` in `include_router()`.
* **Container B Test**: `tests/test_router_circular_import.py::test_router_circular_import`
  ```python
  router = APIRouter()
  with pytest.raises(AssertionError, match="Cannot include the same APIRouter instance into itself"):
      router.include_router(router)
  ```

#### 14. `fastapi_5077` (`fastapi/fastapi`)
* **Problem**: Decorated functions wrapped with `@functools.wraps` copy annotations verbatim, causing `get_typed_signature()` to fail resolving string forward references because `__globals__` was read from the wrapper instead of the unwrapped function.
* **Fix**: In `fastapi/dependencies/utils.py`, unwrap the callable with `inspect.unwrap(call)` before extracting `__globals__` in `get_typed_signature()` and `get_typed_return_annotation()`.
* **Container B Test**: `tests/test_wrapped_method_forward_reference.py::test_wrapped_method_type_inference`
  ```python
  def passthrough(f):
      @functools.wraps(f)
      def method(*args, **kwargs):
          return f(*args, **kwargs)
      return method
  ```
