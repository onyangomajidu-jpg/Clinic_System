"""
_check_templates.py
====================

Validate every Django template in the project compiles and (best effort)
renders, without starting a web server.

What it does
------------
1. Configures Django using the real ``clinic_system.settings`` module.
2. Discovers templates from:
     - the project-level ``templates/`` directory (TEMPLATES['DIRS']), and
     - every installed app's ``templates/`` directory (APP_DIRS).
3. Compiles each template with Django's template engine. This catches the
   usual breakages: syntax errors, invalid block/endblock pairing, missing
   included/extends targets, and unknown custom tags/filters.
4. Best-effort render pass: renders each template against a minimal
   request context (anonymous user, ``/dashboard/`` resolver) so that
   ``{% url 'accounts:dashboard' %}`` and ``request.resolver_match`` style
   references are actually exercised. Render failures are reported as
   warnings because a template can legitimately need database data that is
   not available in this harness.

Exit code is non-zero if any template *fails to compile*, modelling a CI
gate. Run from the project root:

    .venv\\Scripts\\python.exe _check_templates.py            (Windows)
    python _check_templates.py                                (POSIX)

Requires Django (and its dependencies) to be importable, i.e. run it inside
the project's virtual environment.
"""

import os
import sys
from pathlib import Path

import django

# --------------------------------------------------------------------------
# Bootstrap (must happen before importing anything that touches settings)
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "clinic_system.settings")
django.setup()

# --------------------------------------------------------------------------
# Imports that need a configured Django installation
# --------------------------------------------------------------------------
from django.apps import apps  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth.models import AnonymousUser  # noqa: E402
from django.template import TemplateDoesNotExist  # noqa: E402
from django.template.exceptions import TemplateSyntaxError  # noqa: E402
from django.template.loader import get_template  # noqa: E402
from django.test import RequestFactory  # noqa: E402

# ``resolve``/``NoReverseMatch`` moved between Django versions; import
# forwards keep the script working across versions.
try:  # pragma: no cover - version shim
    from django.urls import NoReverseMatch, resolve as resolve_url

    MODERN_DJANGO = True
except ImportError:  # pragma: no cover - legacy fallback (< Django 2)
    from django.core.urlresolvers import NoReverseMatch, resolve as resolve_url

    MODERN_DJANGO = True

# --------------------------------------------------------------------------
# Template discovery
# --------------------------------------------------------------------------
def _template_roots():
    """Return a list of template root directories.

    Covers both TEMPLATES['DIRS'] (project level) and APP_DIRS (per app).
    """
    roots = []

    # 1) Project-level TEMPLATES['DIRS'].
    for directory in settings.TEMPLATES[0].get("DIRS", []):
        root = Path(directory)
        if root.is_dir():
            roots.append(root)

    # 2) App-level templates dirs (APP_DIRS) for every installed app.
    for config in apps.get_app_configs():
        app_templates = Path(config.path) / "templates"
        if app_templates.is_dir():
            roots.append(app_templates)

    return roots


def _discover_templates():
    """Return a list of (template_name, absolute_path) for every .html file."""
    seen = set()
    found = []
    for root in _template_roots():
        for path in sorted(root.rglob("*.html")):
            name = path.relative_to(root).as_posix()
            if name in seen:
                continue
            seen.add(name)
            found.append((name, path))
    return found

# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------
def _compile_check(template_name, path):
    """Compile a template by name; raise on syntax error."""
    get_template(template_name)


def _render_check(template_name):
    """Best-effort render against a minimal request context.

    Returns an error message string, or ``None`` on success. Failures here
    are warnings, not gate failures, because templates may require real
    database-backed request context to render fully.
    """
    try:
        factory = RequestFactory()
        request = factory.get("/dashboard/")
        try:
            request.resolver_match = resolve_url("/dashboard/")
        except Exception:  # pragma: no cover - URL resolution fallback
            pass
        request.user = AnonymousUser()
        request.session = {}
        # Modern Django render API: dict context + request kwarg. Passing the
        # request lets Django apply context processors (request, auth,
        # messages, clinic_info) exactly like a real view render.
        get_template(template_name).render({}, request)
        return None
    except TemplateDoesNotExist as exc:
        return f"missing template (could not render): {exc}"
    except (TemplateSyntaxError, NoReverseMatch) as exc:
        return f"render-time error: {exc}"
    except Exception as exc:  # noqa: BLE001 - report, do not gate
        return f"render warning: {type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------
def main():
    templates = _discover_templates()
    if not templates:
        print("No templates found to check.")
        return 0

    print(f"Checking {len(templates)} templates...\n")

    compile_errors = []
    render_warnings = []

    for template_name, path in templates:
        # 1) Compile gate.
        try:
            _compile_check(template_name, path)
        except (TemplateSyntaxError, TemplateDoesNotExist) as exc:
            compile_errors.append((template_name, str(exc)))
            print(f"  [COMPILE FAIL] {template_name}\n        -> {exc}")
            continue  # no point rendering something that won't compile
        except Exception as exc:  # pragma: no cover - truly unexpected
            compile_errors.append((template_name, f"{type(exc).__name__}: {exc}"))
            print(f"  [COMPILE FAIL] {template_name}\n        -> {exc}")
            continue

        # 2) Best-effort render (warning only).
        warning = _render_check(template_name)
        if warning:
            render_warnings.append((template_name, warning))
            print(f"  [RENDER WARN ] {template_name}\n        -> {warning}")
        else:
            print(f"  [OK          ] {template_name} ({path.name})")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"Templates checked : {len(templates)}")
    print(f"Compile failures  : {len(compile_errors)}")
    print(f"Render warnings   : {len(render_warnings)}")

    if compile_errors:
        print("\nCompile failures (gate FAILED):")
        for name, err in compile_errors:
            print(f"  - {name}: {err}")
        return 1

    if render_warnings:
        print("\nRender warnings (review, non-fatal):")
        for name, err in render_warnings:
            print(f"  - {name}: {err}")

    print("\nAll templates compiled successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())