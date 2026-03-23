"""
XSS task utilities: HTML page generation and upload.

render_xss_page(spec) -> str   — generates self-contained HTML with a vulnerable input
upload_xss_page(html, batch_id, variant_id) -> str  — uploads to S3, returns key
"""
from __future__ import annotations

import html as html_lib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class XSSError(RuntimeError):
    pass


# ── Templates ──────────────────────────────────────────────────────────────────

_REFLECTED_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>{page_title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }}
    h1 {{ color: #333; }}
    .search-box {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    input[type=text] {{ width: 70%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; }}
    button {{ padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }}
    .results {{ margin-top: 20px; padding: 15px; background: white; border-radius: 8px; display: none; }}
    .results.show {{ display: block; }}
    footer {{ margin-top: 40px; color: #999; font-size: 12px; text-align: center; }}
  </style>
</head>
<body>
  <h1>{page_title}</h1>
  <div class="search-box">
    <p>{page_description}</p>
    <form method="GET" action="">
      <input type="text" name="{param}" placeholder="Введите запрос..." value="">
      <button type="submit">Поиск</button>
    </form>
  </div>
  <div class="results show" id="results">
    <!-- search results will appear here -->
  </div>
  <footer>CTF Challenge Platform &copy; 2025</footer>

  <script>
    // Set flag in cookie
    document.cookie = "flag={flag}; path=/";

    // Reflected XSS: inject URL param value directly into DOM
    (function() {{
      var params = new URLSearchParams(window.location.search);
      var q = params.get("{param}");
      if (q !== null) {{
        var results = document.getElementById("results");
        {filter_js}
        results.innerHTML = "<p>Результаты поиска по запросу: " + q + "</p>";
      }}
    }})();
  </script>
</body>
</html>
"""

_DOM_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>{page_title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }}
    h1 {{ color: #333; }}
    .widget {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    #output {{ margin-top: 15px; padding: 10px; background: #fff3cd; border-radius: 4px; }}
    footer {{ margin-top: 40px; color: #999; font-size: 12px; text-align: center; }}
  </style>
</head>
<body>
  <h1>{page_title}</h1>
  <div class="widget">
    <p>{page_description}</p>
    <p>Перейдите по ссылке с параметром в хэше: <code>#{param}=&lt;значение&gt;</code></p>
    <div id="output">Ожидание параметра...</div>
  </div>
  <footer>CTF Challenge Platform &copy; 2025</footer>

  <script>
    document.cookie = "flag={flag}; path=/";

    // DOM XSS: value from location.hash injected via innerHTML
    (function() {{
      var hash = window.location.hash.slice(1);
      var params = new URLSearchParams(hash);
      var val = params.get("{param}");
      if (val !== null) {{
        document.getElementById("output").innerHTML = val;
      }}
    }})();
  </script>
</body>
</html>
"""

_STORED_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <title>{page_title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; background: #f5f5f5; }}
    h1 {{ color: #333; }}
    .post-box {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
    textarea {{ width: 100%; height: 80px; padding: 8px; border: 1px solid #ccc; border-radius: 4px; resize: vertical; }}
    button {{ padding: 8px 16px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; margin-top: 8px; }}
    .comment {{ background: white; padding: 15px; border-radius: 8px; margin-top: 10px; border-left: 4px solid #007bff; }}
    footer {{ margin-top: 40px; color: #999; font-size: 12px; text-align: center; }}
  </style>
</head>
<body>
  <h1>{page_title}</h1>
  <div class="post-box">
    <p>{page_description}</p>
    <form onsubmit="addComment(event)">
      <textarea name="{param}" id="{param}" placeholder="Оставьте комментарий..."></textarea>
      <button type="submit">Отправить</button>
    </form>
  </div>
  <div id="comments">
    <div class="comment"><strong>Система:</strong> Добро пожаловать! Оставляйте комментарии ниже.</div>
  </div>
  <footer>CTF Challenge Platform &copy; 2025</footer>

  <script>
    document.cookie = "flag={flag}; path=/";

    // Stored XSS simulation: comments stored in localStorage, rendered unsanitized
    var comments = JSON.parse(localStorage.getItem("ctf_comments") || "[]");

    function renderComments() {{
      var container = document.getElementById("comments");
      {filter_js}
      comments.forEach(function(c) {{
        var div = document.createElement("div");
        div.className = "comment";
        div.innerHTML = "<strong>Пользователь:</strong> " + c;
        container.appendChild(div);
      }});
    }}

    function addComment(e) {{
      e.preventDefault();
      var val = document.getElementById("{param}").value;
      if (!val.trim()) return;
      comments.push(val);
      localStorage.setItem("ctf_comments", JSON.stringify(comments));
      location.reload();
    }}

    renderComments();
  </script>
</body>
</html>
"""


# ── Filter JS snippets ────────────────────────────────────────────────────────

_FILTER_NONE = ""  # No filter

_FILTER_SCRIPT_TAG = """\
        // Basic filter: replace <script> tag (bypass via event handlers)
        q = q.replace(/<script[^>]*>/gi, "").replace(/<\\/script>/gi, "");"""

_FILTER_SCRIPT_TAG_STORED = """\
      // Basic filter: replace <script> tag (bypass via event handlers)
      comments = comments.map(function(c) {{
        return c.replace(/<script[^>]*>/gi, "").replace(/<\\/script>/gi, "");
      }});"""


def render_xss_page(spec: dict) -> str:
    """
    Generate a self-contained HTML page for an XSS CTF task.

    The page:
    - Sets the flag in document.cookie as 'flag=CTF{...}'
    - Has a vulnerability matching xss_type and vulnerable_param
    - Optionally applies a basic filter (for intermediate tasks)
    """
    flag = (spec.get("flag") or "").strip()
    xss_type = (spec.get("xss_type") or "reflected").strip().lower()
    param = (spec.get("vulnerable_param") or "q").strip()
    filter_bypass = (spec.get("filter_bypass") or "").strip()
    title = (spec.get("title") or "CTF Challenge").strip()
    description = (spec.get("description") or "Найдите флаг.").strip()

    # Pick filter JS based on whether a filter is described
    has_filter = bool(filter_bypass)

    if xss_type == "dom":
        page = _DOM_TEMPLATE.format(
            page_title=html_lib.escape(title),
            page_description=html_lib.escape(description),
            param=html_lib.escape(param),
            flag=html_lib.escape(flag),
        )
    elif xss_type == "stored":
        filter_js = _FILTER_SCRIPT_TAG_STORED if has_filter else ""
        page = _STORED_TEMPLATE.format(
            page_title=html_lib.escape(title),
            page_description=html_lib.escape(description),
            param=html_lib.escape(param),
            flag=html_lib.escape(flag),
            filter_js=filter_js,
        )
    else:
        # default: reflected
        filter_js = _FILTER_SCRIPT_TAG if has_filter else _FILTER_NONE
        page = _REFLECTED_TEMPLATE.format(
            page_title=html_lib.escape(title),
            page_description=html_lib.escape(description),
            param=html_lib.escape(param),
            flag=html_lib.escape(flag),
            filter_js=filter_js,
        )

    return page


def upload_xss_page(html_content: str, batch_id: str, variant_id: str) -> str:
    """
    Upload the HTML page to S3 and return the object key.
    Raises XSSError on failure.
    """
    from botocore.exceptions import ClientError
    from app.services.storage import get_s3_client
    from app.config import settings

    bucket = settings.s3_task_bucket_name
    key = f"ctf_xss/{batch_id}/{variant_id}/challenge.html"

    try:
        client = get_s3_client(
            access_key=settings.s3_task_access_key,
            secret_key=settings.s3_task_secret_key,
        )
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=html_content.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
        )
        return key
    except ClientError as exc:
        raise XSSError(f"S3 upload failed: {exc}") from exc
    except Exception as exc:
        raise XSSError(f"Unexpected upload error: {exc}") from exc
