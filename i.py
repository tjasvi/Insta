# multi_sites_with_multiple_creds.py
# Python Playwright runner updated from the latest recorded flow in new.txt.
#
# For each credential, the script opens a fresh browser context, visits every
# configured site, logs in, opens the IG followers service, fills the target
# username/amount, and starts the task.

import os
import re
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Playwright is not installed. Run: "
        "python -m pip install playwright && python -m playwright install chromium"
    ) from exc


# ===== CONFIG =====

DEFAULT_CREDENTIALS = [
    "stejasvi8175",
]

CREDENTIALS = [
    item.strip()
    for item in os.getenv("INSTA_CREDENTIALS", ",".join(DEFAULT_CREDENTIALS)).split(",")
    if item.strip()
]

TARGET_USERNAME = os.getenv("INSTA_TARGET_USERNAME", "tjasvs")
TARGET_AMOUNT = os.getenv("INSTA_TARGET_AMOUNT", "5000")
HEADLESS = os.getenv("INSTA_HEADLESS", "true").strip().lower() not in {"0", "false", "no"}

DEFAULT_TIMEOUT_MS = 15_000
QUICK_TIMEOUT_MS = 3_500
PAGE_LOAD_TIMEOUT_MS = 60_000

SITES = [
    "https://takipcikrali.com/",
    "https://fastfollow.in/",
    # "https://takipciking.com/",
    # "https://takipcimx.com/",
    "https://takipcigir.com/",
    "https://takip88.com/",
    "https://takipcitime.net/",
    "https://takipcimx.net/",
    # "https://takipcitime.com/",
    "https://instamoda.org/",
    # "https://bayitakipci.com/",
    # "https://takipciking.net/",
    # "https://hepsitakipci.com/",
    "https://takipcizen.com/",
    "https://takipcibase.com/",
]


# Text patterns are intentionally broad. They cover the latest recording
# from new.txt and the older Turkish labels without relying on broken encoding.
LOGIN_TEXT = re.compile(r"(login|log.{1,2}n|giri.|giris)", re.I)
ACCOUNT_USERNAME_TEXT = re.compile(r"(username|user\s*name|kullan)", re.I)
PASSWORD_TEXT = re.compile(r"(password|pass|sifre|.ifre)", re.I)
FOLLOWERS_TEXT = re.compile(r"(420\s*ig\s*followers|ig\s*followers|followers|takip)", re.I)
TARGET_USERNAME_TEXT = re.compile(r"(fatihh|username|user\s*name|user|profile|instagram)", re.I)
FIND_USER_TEXT = re.compile(r"(find\s*user|kullan.*bul|user.*find|bul)", re.I)
AMOUNT_TEXT = re.compile(r"^\s*(50|amount|adet|count|quantity)\s*$", re.I)
START_TEXT = re.compile(r"(start|baslat|ba.*lat)", re.I)


# ===== Helpers =====

def make_password(username: str) -> str:
    return f"{username}{username}"


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return cleaned or "site"


def host_for(url: str) -> str:
    return safe_name(urlparse(url).netloc or url)


def pause(page, milliseconds: int = 600) -> None:
    page.wait_for_timeout(milliseconds)


def wait_for_page_settle(page, timeout_ms: int = 8_000) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        pass
    except Exception:
        pass
    pause(page, 400)


def save_error_screenshot(page, prefix: str, url: str, cred_idx: int, site_idx: int) -> None:
    out = Path("errors")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{prefix}_cred{cred_idx}_site{site_idx}_{host_for(url)}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        print(f"[!] Screenshot saved: {path}")
    except Exception as exc:
        print(f"[!] Failed to save screenshot: {exc}")


def contexts_for(page):
    contexts = [("page", page)]
    for index, frame in enumerate(page.frames):
        if frame == page.main_frame:
            continue
        contexts.append((f"frame[{index}]", frame))
    return contexts


def try_action(label: str, candidates, operation, timeout_ms: int = QUICK_TIMEOUT_MS) -> bool:
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
    return try_action(
        label,
        candidates,
        lambda locator, timeout: locator.click(timeout=timeout),
        timeout_ms=timeout_ms,
    )


def fill_candidates(label: str, candidates, value: str, timeout_ms: int = QUICK_TIMEOUT_MS) -> bool:
    return try_action(
        label,
        candidates,
        lambda locator, timeout: locator.fill(value, timeout=timeout),
        timeout_ms=timeout_ms,
    )


def login_open_candidates(page):
    return [
        ("latest LOGIN link", page.get_by_role("link", name=LOGIN_TEXT)),
        ("LOGIN button", page.get_by_role("button", name=LOGIN_TEXT)),
        ("LOGIN text", page.get_by_text(LOGIN_TEXT)),
        ("anchor containing Login", page.locator("a:has-text('Login')")),
        ("anchor containing LOGIN", page.locator("a:has-text('LOGIN')")),
        ("anchor containing Giris", page.locator("a:has-text('Giris')")),
    ]


def account_username_candidates(page):
    candidates = []
    for label, ctx in contexts_for(page):
        candidates.extend(
            [
                (f"{label} textbox named Username", ctx.get_by_role("textbox", name=ACCOUNT_USERNAME_TEXT)),
                (f"{label} input[name='username']", ctx.locator("input[name='username']")),
                (f"{label} input[name*='username']", ctx.locator("input[name*='username' i]")),
                (f"{label} input[name*='user']", ctx.locator("input[name*='user' i]")),
                (f"{label} placeholder user", ctx.locator("input[placeholder*='user' i]")),
                (f"{label} placeholder kullan", ctx.locator("input[placeholder*='kullan' i]")),
                (f"{label} aria-label user", ctx.locator("input[aria-label*='user' i]")),
            ]
        )
    return candidates


def password_candidates(page):
    candidates = []
    for label, ctx in contexts_for(page):
        candidates.extend(
            [
                (f"{label} textbox named Password", ctx.get_by_role("textbox", name=PASSWORD_TEXT)),
                (f"{label} input[type='password']", ctx.locator("input[type='password']")),
                (f"{label} input[name*='password']", ctx.locator("input[name*='password' i]")),
                (f"{label} input[name*='pass']", ctx.locator("input[name*='pass' i]")),
                (f"{label} placeholder password", ctx.locator("input[placeholder*='password' i]")),
                (f"{label} placeholder sifre", ctx.locator("input[placeholder*='sifre' i]")),
            ]
        )
    return candidates


def login_submit_candidates(page):
    candidates = []
    for label, ctx in contexts_for(page):
        candidates.extend(
            [
                (f"{label} Login button", ctx.get_by_role("button", name=LOGIN_TEXT)),
                (f"{label} submit button", ctx.locator("button[type='submit']")),
                (f"{label} input submit", ctx.locator("input[type='submit']")),
                (f"{label} button text Login", ctx.locator("button:has-text('Login')")),
                (f"{label} button text LOGIN", ctx.locator("button:has-text('LOGIN')")),
                (f"{label} button text Giris", ctx.locator("button:has-text('Giris')")),
            ]
        )
    return candidates


def followers_candidates(page):
    return [
        ("latest 420 IG Followers link", page.get_by_role("link", name=re.compile(r"420\s*ig\s*followers", re.I))),
        ("IG Followers link", page.get_by_role("link", name=FOLLOWERS_TEXT)),
        ("Followers button", page.get_by_role("button", name=FOLLOWERS_TEXT)),
        ("anchor text 420 IG Followers", page.locator("a:has-text('420 IG Followers')")),
        ("anchor text IG Followers", page.locator("a:has-text('IG Followers')")),
        ("anchor text Followers", page.locator("a:has-text('Followers')")),
        ("any anchor containing takip", page.locator("a:has-text('takip')")),
    ]


def target_username_candidates(page):
    return [
        ("latest target textbox named fatihh", page.get_by_role("textbox", name=re.compile(r"fatihh", re.I))),
        ("target username textbox", page.get_by_role("textbox", name=TARGET_USERNAME_TEXT)),
        ("input placeholder fatihh", page.locator("input[placeholder*='fatihh' i]")),
        ("input name username", page.locator("input[name='username']")),
        ("input name contains username", page.locator("input[name*='username' i]")),
        ("input name contains user", page.locator("input[name*='user' i]")),
        ("input placeholder user", page.locator("input[placeholder*='user' i]")),
        ("first text input", page.locator("input[type='text']")),
    ]


def find_user_candidates(page):
    return [
        ("latest Find User button", page.get_by_role("button", name=re.compile(r"find\s*user", re.I))),
        ("Find User text button", page.locator("button:has-text('Find User')")),
        ("button matching find/user", page.get_by_role("button", name=FIND_USER_TEXT)),
        ("submit input", page.locator("input[type='submit']")),
        ("generic find button", page.locator("button").filter(has_text=FIND_USER_TEXT)),
    ]


def amount_candidates(page):
    return [
        ("latest textbox named 50", page.get_by_role("textbox", name=re.compile(r"^\s*50\s*$"))),
        ("amount textbox", page.get_by_role("textbox", name=AMOUNT_TEXT)),
        ("input placeholder 50", page.locator("input[placeholder='50']")),
        ("input value 50", page.locator("input[value='50']")),
        ("input name amount", page.locator("input[name*='amount' i]")),
        ("input name count", page.locator("input[name*='count' i]")),
        ("number input", page.locator("input[type='number']")),
    ]


def start_candidates(page):
    return [
        ("latest Start button", page.get_by_role("button", name=re.compile(r"start", re.I))),
        ("button matching start", page.get_by_role("button", name=START_TEXT)),
        ("button text Start", page.locator("button:has-text('Start')")),
        ("button text Baslat", page.locator("button:has-text('Baslat')")),
        ("submit input", page.locator("input[type='submit']")),
    ]


def fill_fallback_textbox(page, label: str, value: str, preferred_indexes) -> bool:
    textboxes = page.get_by_role("textbox")
    try:
        count = textboxes.count()
    except Exception as exc:
        print(f"[!] Could not inspect textboxes for {label}: {exc}")
        return False

    for index in preferred_indexes:
        if index < 0:
            index = count + index
        if index < 0 or index >= count:
            continue
        try:
            box = textboxes.nth(index)
            box.wait_for(state="visible", timeout=QUICK_TIMEOUT_MS)
            box.fill(value, timeout=QUICK_TIMEOUT_MS)
            print(f"[+] {label}: fallback textbox #{index}")
            return True
        except Exception:
            continue

    print(f"[!] Could not {label} with any fallback textbox.")
    return False


def attempt_login(page, username: str, password: str) -> bool:
    print("[*] Opening login form")
    click_candidates("open login form", login_open_candidates(page), timeout_ms=QUICK_TIMEOUT_MS)
    pause(page, 900)

    username_filled = fill_candidates(
        "fill account username",
        account_username_candidates(page),
        username,
        timeout_ms=QUICK_TIMEOUT_MS,
    )
    password_filled = fill_candidates(
        "fill account password",
        password_candidates(page),
        password,
        timeout_ms=QUICK_TIMEOUT_MS,
    )

    if not username_filled or not password_filled:
        return False

    submitted = click_candidates(
        "submit login",
        login_submit_candidates(page),
        timeout_ms=QUICK_TIMEOUT_MS,
    )
    if not submitted:
        return False

    wait_for_page_settle(page, timeout_ms=10_000)
    return True


def perform_task_after_login(page) -> bool:
    print("[*] Opening followers service")
    opened_followers = click_candidates(
        "open followers service",
        followers_candidates(page),
        timeout_ms=QUICK_TIMEOUT_MS,
    )
    if opened_followers:
        wait_for_page_settle(page, timeout_ms=8_000)
    else:
        print("[!] Followers service link was not found. Trying the form on the current page.")

    username_filled = fill_candidates(
        "fill target username",
        target_username_candidates(page),
        TARGET_USERNAME,
        timeout_ms=QUICK_TIMEOUT_MS,
    )
    if not username_filled:
        username_filled = fill_fallback_textbox(
            page,
            "fill target username",
            TARGET_USERNAME,
            preferred_indexes=[0, 1, -1],
        )

    if not username_filled:
        return False

    find_clicked = click_candidates(
        "click Find User",
        find_user_candidates(page),
        timeout_ms=QUICK_TIMEOUT_MS,
    )
    if find_clicked:
        wait_for_page_settle(page, timeout_ms=8_000)
    else:
        print("[!] Find User button was not found. Continuing in case the amount field is already available.")

    amount_filled = fill_candidates(
        "fill amount",
        amount_candidates(page),
        TARGET_AMOUNT,
        timeout_ms=QUICK_TIMEOUT_MS,
    )
    if not amount_filled:
        amount_filled = fill_fallback_textbox(
            page,
            "fill amount",
            TARGET_AMOUNT,
            preferred_indexes=[1, -1, 0],
        )

    if not amount_filled:
        return False

    started = click_candidates(
        "click Start",
        start_candidates(page),
        timeout_ms=QUICK_TIMEOUT_MS,
    )
    if started:
        wait_for_page_settle(page, timeout_ms=8_000)

    return started


# ===== Main runner =====

def run_all() -> None:
    if not CREDENTIALS:
        raise RuntimeError("No credentials configured.")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=HEADLESS)

        try:
            for cred_idx, username in enumerate(CREDENTIALS, start=1):
                password = make_password(username)
                print(f"\n=== CREDENTIAL [{cred_idx}/{len(CREDENTIALS)}] username={username} password=<hidden> ===")

                context = browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    locale="en-US",
                )
                context.set_default_timeout(DEFAULT_TIMEOUT_MS)

                try:
                    for site_idx, url in enumerate(SITES, start=1):
                        print(f"\n--- [{site_idx}/{len(SITES)}] {url} ({username}) ---")
                        page = context.new_page()
                        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
                            wait_for_page_settle(page)

                            if not attempt_login(page, username, password):
                                print(f"[!] Login failed on {url} using {username}")
                                save_error_screenshot(page, "login_failed", url, cred_idx, site_idx)
                                continue

                            if not perform_task_after_login(page):
                                print(f"[!] Task flow failed on {url} using {username}")
                                save_error_screenshot(page, "task_failed", url, cred_idx, site_idx)
                                continue

                            print(f"[+] Done: {url} (credential: {username})")

                        except Exception as exc:
                            print(f"[!] Exception for {url} with {username}: {exc}")
                            traceback.print_exc()
                            save_error_screenshot(page, "error", url, cred_idx, site_idx)
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

        finally:
            browser.close()


if __name__ == "__main__":
    run_all()
