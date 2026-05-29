# multi_sites_with_multiple_creds.py
# Site-specific Python Playwright runner built from the verified recordings.

import os
import re
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Playwright is not installed. Run: "
        "python -m pip install playwright && python -m playwright install chromium"
    ) from exc


# ===== CONFIG =====

DEFAULT_CREDENTIALS = [
    os.getenv("INSTA_USER_1", "stejasvi812"),
    os.getenv("INSTA_USER_2", "stejasvi812026"),
]
CREDENTIALS = [
    item.strip()
    for item in os.getenv("INSTA_CREDENTIALS", ",".join(DEFAULT_CREDENTIALS)).split(",")
    if item.strip()
]
TARGET_USERNAME = os.getenv("INSTA_TARGET_USERNAME", "tjasvs")
HEADLESS = os.getenv("INSTA_HEADLESS", "true").strip().lower() not in {"0", "false", "no"}

DEFAULT_TIMEOUT_MS = 15_000
QUICK_TIMEOUT_MS = 5_000
TASK_TIMEOUT_MS = 15_000
PAGE_LOAD_TIMEOUT_MS = 60_000

LOGIN_ANY_RE = re.compile(r"(login|log.?n|giri.|g.{1,2}r.{1,2})", re.I)
LOGIN_WITH_INSTAGRAM_RE = re.compile(
    r"((login|log.?n|giri.).*instagram|instagram.*(login|log.?n|giri.))",
    re.I,
)
GIRIS_TAKIP_RE = re.compile(r"((login|log.?n|giri.).*takip|(login|log.?n|giri.))", re.I)
USERNAME_RE = re.compile(r"^username$", re.I)
PASSWORD_RE = re.compile(r"^password$", re.I)
FIND_USER_RE = re.compile(r"find\s*user", re.I)
START_RE = re.compile(r"start", re.I)


@dataclass(frozen=True)
class SiteFlow:
    name: str
    url: str
    login_re: re.Pattern
    follower_count: str
    amount_label: str
    amount_value: str
    tools_url: str | None = None


SITES = [
    SiteFlow(
        name="takipcikrali",
        url="https://takipcikrali.com/",
        login_re=LOGIN_ANY_RE,
        follower_count="0",
        amount_label="50",
        amount_value="5000",
    ),
    SiteFlow(
        name="fastfollow",
        url="https://fastfollow.in/",
        login_re=LOGIN_WITH_INSTAGRAM_RE,
        follower_count="280",
        amount_label="50",
        amount_value="5000",
    ),
    SiteFlow(
        name="takipcigir",
        url="https://takipcigir.com/",
        login_re=LOGIN_WITH_INSTAGRAM_RE,
        follower_count="175",
        amount_label="50",
        amount_value="5000",
    ),
    SiteFlow(
        name="takip88",
        url="https://takip88.com/",
        login_re=LOGIN_WITH_INSTAGRAM_RE,
        follower_count="280",
        amount_label="50",
        amount_value="5000",
    ),
    # Site 5 disabled from the manual run:
    # SiteFlow(
    #     name="takipcitime",
    #     url="https://takipcitime.net/",
    #     login_re=LOGIN_WITH_INSTAGRAM_RE,
    #     follower_count="",
    #     amount_label="50",
    #     amount_value="5000",
    # ),
    SiteFlow(
        name="takipcimx",
        url="https://takipcimx.net/",
        login_re=GIRIS_TAKIP_RE,
        follower_count="245",
        amount_label="60",
        amount_value="6000",
    ),
    SiteFlow(
        name="instamoda",
        url="https://instamoda.org/",
        login_re=LOGIN_WITH_INSTAGRAM_RE,
        follower_count="420",
        amount_label="50",
        amount_value="50000",
    ),
    SiteFlow(
        name="takipcizen",
        url="https://takipcizen.com/",
        login_re=LOGIN_WITH_INSTAGRAM_RE,
        follower_count="245",
        amount_label="50",
        amount_value="50000",
        tools_url="https://takipcizen.com/tools",
    ),
    SiteFlow(
        name="takipcibase",
        url="https://takipcibase.com/a",
        login_re=LOGIN_ANY_RE,
        follower_count="210",
        amount_label="70",
        amount_value="70000",
        tools_url="https://takipcibase.com/tools",
    ),
]


# ===== Helpers =====

def make_password(username: str) -> str:
    return f"{username}{username}"


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return cleaned or "site"


def host_for(url: str) -> str:
    return safe_name(urlparse(url).netloc or url)


def wait_for_page_settle(page, timeout_ms: int = 8_000) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass
    except Exception:
        pass
    page.wait_for_timeout(500)


def goto(page, url: str) -> None:
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
    except PlaywrightError as exc:
        if "net::ERR_ABORTED" not in str(exc):
            raise
        print(f"[!] Navigation aborted for {url}; continuing with the current page.")
        page.wait_for_timeout(1_500)
    wait_for_page_settle(page)


def is_instagram_appeal_page(page) -> bool:
    checks = [
        page.get_by_role("button", name=re.compile(r"start\s*appeal", re.I)),
        page.get_by_role("link", name=re.compile(r"log\s*in\s*with\s*another\s*account", re.I)),
        page.get_by_text(re.compile(r"start\s*appeal|log\s*in\s*with\s*another\s*account|can't\s*log\s*in", re.I)),
    ]

    for locator in checks:
        try:
            locator.first.wait_for(state="visible", timeout=1_000)
            return True
        except Exception:
            pass
    return False


def save_error_screenshot(page, prefix: str, flow: SiteFlow, cred_idx: int, site_idx: int) -> None:
    out = Path("errors")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{prefix}_cred{cred_idx}_site{site_idx}_{flow.name}_{host_for(flow.url)}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        print(f"[!] Screenshot saved: {path}")
    except Exception as exc:
        print(f"[!] Failed to save screenshot: {exc}")


def compact(value, limit: int = 90) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value[:limit]


def contexts_for(page):
    contexts = [("page", page)]
    for index, frame in enumerate(page.frames):
        if frame == page.main_frame:
            continue
        contexts.append((f"frame[{index}]", frame))
    return contexts


def dump_visible_controls(page, limit: int = 60) -> None:
    print("[!] Visible controls snapshot:")
    printed = 0

    for label, ctx in contexts_for(page):
        try:
            controls = ctx.locator("input, button, a, textarea, select, [role='button']")
            count = min(controls.count(), 160)
        except Exception as exc:
            print(f"    {label}: could not inspect controls: {exc}")
            continue

        for index in range(count):
            if printed >= limit:
                print("    ...")
                return

            control = controls.nth(index)
            try:
                if not control.is_visible():
                    continue

                details = control.evaluate(
                    """el => ({
                        tag: el.tagName.toLowerCase(),
                        type: el.getAttribute('type') || '',
                        role: el.getAttribute('role') || '',
                        name: el.getAttribute('name') || '',
                        id: el.id || '',
                        placeholder: el.getAttribute('placeholder') || '',
                        aria: el.getAttribute('aria-label') || '',
                        value: el.getAttribute('value') || el.value || '',
                        text: el.innerText || el.textContent || ''
                    })"""
                )
                secret_hint = " ".join(
                    [
                        details["type"],
                        details["name"],
                        details["id"],
                        details["placeholder"],
                        details["aria"],
                    ]
                ).lower()
                value = "<hidden>" if any(word in secret_hint for word in ("password", "pass", "sifre")) else compact(details["value"])
                bits = [
                    f"tag={details['tag']}",
                    f"type={compact(details['type'])}",
                    f"role={compact(details['role'])}",
                    f"name={compact(details['name'])}",
                    f"id={compact(details['id'])}",
                    f"placeholder={compact(details['placeholder'])}",
                    f"aria={compact(details['aria'])}",
                    f"value={value}",
                    f"text={compact(details['text'])}",
                ]
                print(f"    {label} #{index}: " + " | ".join(bits))
                printed += 1
            except Exception:
                continue

    if printed == 0:
        print("    no visible input/button/link controls found")


def try_action(label: str, candidates, operation, timeout_ms: int) -> bool:
    last_error = None

    for description, locator in candidates:
        target = locator.first
        try:
            target.wait_for(state="visible", timeout=timeout_ms)
            operation(target, timeout_ms)
            print(f"[+] {label}: {description}")
            return True
        except Exception as exc:
            last_error = exc

    if last_error:
        print(f"[!] Could not {label}. Last error: {last_error}")
    else:
        print(f"[!] Could not {label}. No candidates were provided.")
    return False


def click_candidates(label: str, candidates, timeout_ms: int = QUICK_TIMEOUT_MS) -> bool:
    return try_action(label, candidates, lambda locator, timeout: locator.click(timeout=timeout), timeout_ms)


def fill_candidates(label: str, candidates, value: str, timeout_ms: int = QUICK_TIMEOUT_MS) -> bool:
    return try_action(label, candidates, lambda locator, timeout: locator.fill(value, timeout=timeout), timeout_ms)


def link_or_button_candidates(ctx, name_re: re.Pattern):
    return [
        ("role link", ctx.get_by_role("link", name=name_re)),
        ("role button", ctx.get_by_role("button", name=name_re)),
        ("anchor text", ctx.locator("a").filter(has_text=name_re)),
        ("button text", ctx.locator("button").filter(has_text=name_re)),
        ("role=button text", ctx.locator("[role='button']").filter(has_text=name_re)),
        ("input value", ctx.locator("input[type='submit'], input[type='button']").filter(has_text=name_re)),
    ]


def login_open_candidates(page, flow: SiteFlow):
    candidates = []
    for label, ctx in contexts_for(page):
        for desc, locator in link_or_button_candidates(ctx, flow.login_re):
            candidates.append((f"{label} {desc}", locator))
    return candidates


def username_candidates(page):
    candidates = []
    for label, ctx in contexts_for(page):
        candidates.extend(
            [
                (f"{label} textbox named Username", ctx.get_by_role("textbox", name=USERNAME_RE)),
                (f"{label} input name username", ctx.locator("input[name='username']")),
                (f"{label} input name contains username", ctx.locator("input[name*='username' i]")),
                (f"{label} input placeholder Username", ctx.locator("input[placeholder*='username' i]")),
                (f"{label} input aria Username", ctx.locator("input[aria-label*='username' i]")),
            ]
        )
    return candidates


def password_candidates(page):
    candidates = []
    for label, ctx in contexts_for(page):
        candidates.extend(
            [
                (f"{label} textbox named Password", ctx.get_by_role("textbox", name=PASSWORD_RE)),
                (f"{label} input type password", ctx.locator("input[type='password']")),
                (f"{label} input name password", ctx.locator("input[name*='password' i]")),
                (f"{label} input placeholder Password", ctx.locator("input[placeholder*='password' i]")),
                (f"{label} input aria Password", ctx.locator("input[aria-label*='password' i]")),
            ]
        )
    return candidates


def login_submit_candidates(page):
    login_button_re = re.compile(r"^login$", re.I)
    candidates = []
    for label, ctx in contexts_for(page):
        candidates.extend(
            [
                (f"{label} Login button", ctx.get_by_role("button", name=login_button_re)),
                (f"{label} button text Login", ctx.locator("button").filter(has_text=login_button_re)),
                (f"{label} submit input", ctx.locator("input[type='submit'][value*='Login' i]")),
                (f"{label} generic submit", ctx.locator("button[type='submit'], input[type='submit']")),
            ]
        )
    return candidates


def follower_candidates(page, flow: SiteFlow):
    exact_re = re.compile(rf"\b{re.escape(flow.follower_count)}\s*IG\s*Followers\b", re.I)
    any_re = re.compile(r"\bIG\s*Followers\b", re.I)
    candidates = [
        ("exact follower link", page.get_by_role("link", name=exact_re)),
        ("exact follower anchor", page.locator("a").filter(has_text=exact_re)),
        ("any IG Followers link", page.get_by_role("link", name=any_re)),
        ("any IG Followers anchor", page.locator("a").filter(has_text=any_re)),
    ]
    return candidates


def target_username_candidates(page):
    name_re = re.compile(r"^fatihh$", re.I)
    candidates = []
    for label, ctx in contexts_for(page):
        candidates.extend(
            [
                (f"{label} textbox named fatihh", ctx.get_by_role("textbox", name=name_re)),
                (f"{label} placeholder fatihh", ctx.locator("input[placeholder*='fatihh' i]")),
                (f"{label} aria fatihh", ctx.locator("input[aria-label*='fatihh' i]")),
            ]
        )
    return candidates


def find_user_candidates(page):
    candidates = []
    for label, ctx in contexts_for(page):
        candidates.extend(
            [
                (f"{label} Find User button", ctx.get_by_role("button", name=FIND_USER_RE)),
                (f"{label} button text Find User", ctx.locator("button").filter(has_text=FIND_USER_RE)),
                (f"{label} input value Find User", ctx.locator("input[type='submit'][value*='Find' i], input[type='button'][value*='Find' i]")),
            ]
        )
    return candidates


def amount_candidates(page, flow: SiteFlow):
    amount_re = re.compile(rf"^\s*{re.escape(flow.amount_label)}\s*$")
    amount_value_selector = f"input[value='{flow.amount_label}']"
    amount_placeholder_selector = f"input[placeholder='{flow.amount_label}'], textarea[placeholder='{flow.amount_label}']"
    amount_aria_selector = f"input[aria-label='{flow.amount_label}'], textarea[aria-label='{flow.amount_label}']"
    candidates = []
    for label, ctx in contexts_for(page):
        candidates.extend(
            [
                (f"{label} textbox named {flow.amount_label}", ctx.get_by_role("textbox", name=amount_re)),
                (f"{label} input value {flow.amount_label}", ctx.locator(amount_value_selector)),
                (f"{label} input placeholder {flow.amount_label}", ctx.locator(amount_placeholder_selector)),
                (f"{label} input aria-label {flow.amount_label}", ctx.locator(amount_aria_selector)),
                (f"{label} amount-like input", ctx.locator("input[name*='amount' i], input[name*='count' i], input[name*='quantity' i], input[name*='adet' i]")),
                (f"{label} number input", ctx.locator("input[type='number']")),
            ]
        )
    return candidates


def start_candidates(page):
    candidates = []
    for label, ctx in contexts_for(page):
        candidates.extend(
            [
                (f"{label} Start button", ctx.get_by_role("button", name=START_RE)),
                (f"{label} button text Start", ctx.locator("button").filter(has_text=START_RE)),
                (f"{label} input value Start", ctx.locator("input[type='submit'][value*='Start' i], input[type='button'][value*='Start' i]")),
            ]
        )
    return candidates


def attempt_login(page, flow: SiteFlow, username: str) -> bool:
    password = make_password(username)

    print("[*] Opening login form")
    if not click_candidates("open login form", login_open_candidates(page, flow), timeout_ms=TASK_TIMEOUT_MS):
        dump_visible_controls(page)
        return False

    page.wait_for_timeout(900)

    if not fill_candidates("fill account username", username_candidates(page), username, timeout_ms=TASK_TIMEOUT_MS):
        dump_visible_controls(page)
        return False

    if not fill_candidates("fill account password", password_candidates(page), password, timeout_ms=TASK_TIMEOUT_MS):
        dump_visible_controls(page)
        return False

    if not click_candidates("submit login", login_submit_candidates(page), timeout_ms=TASK_TIMEOUT_MS):
        dump_visible_controls(page)
        return False

    wait_for_page_settle(page, timeout_ms=12_000)
    if is_instagram_appeal_page(page):
        print("[!] Instagram returned an appeal/checkpoint page for this credential on this site.")
        return False

    return True


def perform_task_after_login(page, flow: SiteFlow) -> bool:
    if flow.tools_url:
        print(f"[*] Opening tools page: {flow.tools_url}")
        goto(page, flow.tools_url)

    if is_instagram_appeal_page(page):
        print("[!] Still on Instagram appeal/checkpoint page; skipping this site.")
        return False

    print(f"[*] Opening {flow.follower_count} IG Followers service")
    if not click_candidates("open followers service", follower_candidates(page, flow), timeout_ms=TASK_TIMEOUT_MS):
        dump_visible_controls(page)
        return False

    wait_for_page_settle(page, timeout_ms=10_000)

    if not fill_candidates("fill target username", target_username_candidates(page), TARGET_USERNAME, timeout_ms=TASK_TIMEOUT_MS):
        dump_visible_controls(page)
        return False

    if not click_candidates("click Find User", find_user_candidates(page), timeout_ms=TASK_TIMEOUT_MS):
        dump_visible_controls(page)
        return False

    wait_for_page_settle(page, timeout_ms=12_000)

    if not fill_candidates("fill amount", amount_candidates(page, flow), flow.amount_value, timeout_ms=TASK_TIMEOUT_MS):
        dump_visible_controls(page)
        return False

    if not click_candidates("click Start", start_candidates(page), timeout_ms=TASK_TIMEOUT_MS):
        dump_visible_controls(page)
        return False

    wait_for_page_settle(page, timeout_ms=8_000)
    return True


# ===== Main runner =====

def run_all() -> None:
    if not CREDENTIALS:
        raise RuntimeError("No credentials configured. Set INSTA_CREDENTIALS or INSTA_USER_1/INSTA_USER_2.")

    print(f"[*] Enabled sites: {len(SITES)}")
    print(f"[*] Credentials queued: {len(CREDENTIALS)}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=HEADLESS)

        try:
            for cred_idx, username in enumerate(CREDENTIALS, start=1):
                print(f"\n=== CREDENTIAL [{cred_idx}/{len(CREDENTIALS)}] username={username} password=<hidden> ===")
                context = browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    locale="en-US",
                )
                context.set_default_timeout(DEFAULT_TIMEOUT_MS)

                try:
                    for site_idx, flow in enumerate(SITES, start=1):
                        print(f"\n--- [{site_idx}/{len(SITES)}] {flow.url} ({username}) ---")

                        page = context.new_page()
                        page.set_default_timeout(DEFAULT_TIMEOUT_MS)
                        page.on("dialog", lambda dialog: dialog.accept())

                        try:
                            goto(page, flow.url)

                            if not attempt_login(page, flow, username):
                                print(f"[!] Login failed on {flow.url} using {username}")
                                save_error_screenshot(page, "login_failed", flow, cred_idx, site_idx)
                                continue

                            if not perform_task_after_login(page, flow):
                                print(f"[!] Task flow failed on {flow.url} using {username}")
                                save_error_screenshot(page, "task_failed", flow, cred_idx, site_idx)
                                continue

                            print(f"[+] Done: {flow.url} (credential: {username})")

                        except Exception as exc:
                            print(f"[!] Exception for {flow.url} with {username}: {exc}")
                            traceback.print_exc()
                            save_error_screenshot(page, "error", flow, cred_idx, site_idx)
                        finally:
                            try:
                                page.close()
                            except Exception:
                                pass

                        time.sleep(1.0)
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass

                time.sleep(1.5)

        finally:
            browser.close()


if __name__ == "__main__":
    run_all()
