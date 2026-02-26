# multi_sites_with_multiple_creds.py
# Rewritten to support multiple usernames (password = username repeated twice)
# Behavior: for each credential, a fresh browser context is created and the script
# visits every site in `sites` using that credential.

import time
import traceback
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ===== CONFIG =====
# list of usernames provided by the user
CREDENTIALS = [
    "ericawotsa59",
    "ericawotsa51",
    "ifonlyisentthis7",
    "newtejasvi809",
    "newtejasvi801",
    "stejasvi8172",
    "stejasvi8177",
    "gvvdx262",
    "gvvdx267",
    "ifonlyisentthis5",
    "ifonlyisentthis6",
    "newtejasvi802026",
    "winxgx1",

]

# helper to build password as "double of username" (concatenate username with itself)
def make_password(username: str) -> str:
    return f"{username}{username}"

TARGET_USERNAME = "tjvsi"
TARGET_AMOUNT = "50000"
HEADLESS = True  # set True if you don't want the browser UI

sites = [
    "https://takipcikrali.com/",
    "https://fastfollow.in/",
    #"https://takipciking.com/",
    #"https://takipcimx.com/",
    "https://takipcigir.com/",
    "https://takip88.com/",
    "https://takipcitime.net/",
    "https://takipcimx.net/",
    #"https://takipcitime.com/",
    "https://instamoda.org/",
    #"https://bayitakipci.com/",
    #"https://takipciking.net/",
    #"https://hepsitakipci.com/",
    "https://takipcizen.com/",
    "https://takipcibase.com/",
]

# ===== Helpers =====

def safe_click(locator):
    try:
        locator.click(timeout=5000)
    except PWTimeout:
        locator.click(timeout=15000)


def safe_fill(locator, value):
    try:
        locator.fill(value, timeout=5000)
    except PWTimeout:
        locator.fill(value, timeout=15000)


def save_error_screenshot(page, name):
    out = Path("errors")
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    try:
        page.screenshot(path=str(path))
        print(f"[!] Screenshot saved: {path}")
    except Exception as e:
        print("[!] Failed to save screenshot:", e)


def attempt_login(page, username, password):
    """
    Try to click login, then fill inside iframe (safer selector),
    fallback to searching common username/password inputs on the page.
    Uses provided username/password (no globals).
    """
    # try clicking any login button/link that contains "GİRİŞ" (works even if icon present)
    try:
        # try role-based first
        page.get_by_role("link", name=lambda n: n and "GİRİŞ" in n).first.click(timeout=5000)
    except Exception:
        # fallback: generic text match
        try:
            page.locator("text=GİRİŞ").first.click(timeout=5000)
        except Exception:
            # sometimes "Giriş" without special char/capitalization
            try:
                page.locator("text=Giriş").first.click(timeout=5000)
            except Exception:
                print("[!] Could not find a GİRİŞ button. Continuing anyway (maybe already on login).")

    # wait a little for iframe/modal to appear
    time.sleep(0.8)

    # Primary approach: target iframe whose name starts with fancybox-frame
    try:
        frame = page.frame_locator("iframe[name^='fancybox-frame']")
        # try filling using role names seen in recording
        safe_fill(frame.get_by_role("textbox", name="Kullanıcı adı"), username)
        safe_fill(frame.get_by_role("textbox", name="Şifre"), password)
        safe_click(frame.get_by_role("button", name="Giriş yap"))
        return True
    except Exception:
        # fallback: try to find typical input fields on the main page (in case no iframe)
        try:
            # common selectors—try a few
            selectors = [
                "input[name='username']",
                "input[name='user']",
                "input[name='email']",
                "input[placeholder*='Kullan']",
                "input[placeholder*='Kullanıcı']",
                "input[aria-label*='Kullan']",
                "input[name='Kullanıcı adı']",
                "input[placeholder*='Username']",
            ]
            for sel in selectors:
                loc = page.locator(sel)
                if loc.count():
                    safe_fill(loc.first, username)
                    break
            # password
            pass_selectors = [
                "input[type='password']",
                "input[name='password']",
                "input[name='pass']",
                "input[placeholder*='Şifre']",
            ]
            for sel in pass_selectors:
                loc = page.locator(sel)
                if loc.count():
                    safe_fill(loc.first, password)
                    break
            # submit button
            try:
                # try role-based submit
                page.get_by_role("button", name=lambda n: n and ("Giriş" in n or "Giriş yap" in n)).first.click(timeout=4000)
            except Exception:
                # fallback generic
                if page.locator("button:has-text('Giriş')").count():
                    page.locator("button:has-text('Giriş')").first.click()
                elif page.locator("button:has-text('Giriş yap')").count():
                    page.locator("button:has-text('Giriş yap')").first.click()
                else:
                    print("[!] Could not find explicit submit — hope it's auto-submitted.")
            return True
        except Exception as e:
            print("[!] Login fallback failed:", e)
            return False


def perform_task_after_login(page):
    """
    Click Followers section, fill the target username and amount, then Start.
    Uses resilient selectors where possible.
    """
    time.sleep(1)  # small wait after login

    # Try to click a link/button that leads to followers / followers widget
    tried = False
    try:
        # first try to find any link that contains 'Followers' (English)
        if page.locator("a:has-text('Followers')").count():
            page.locator("a:has-text('Followers')").first.click()
            tried = True
    except Exception:
        pass

    if not tried:
        # try to click the Instagram/followers icon link (recording had that)
        try:
            page.get_by_role("link", name=lambda n: n and "Followers" in n).first.click(timeout=3000)
            tried = True
        except Exception:
            pass

    # if still not navigated, continue — maybe already visible
    time.sleep(0.8)

    # Fill the target username field
    try:
        username_boxes = page.get_by_role("textbox")
        if username_boxes.count() >= 1:
            # prefer a textbox with placeholder or name hints
            filled = False
            for sel in ["input[name='username']", "input[name='user']", "input[placeholder*='kullan']", "input[placeholder*='user']"]:
                if page.locator(sel).count():
                    safe_fill(page.locator(sel).first, TARGET_USERNAME)
                    filled = True
                    break
            if not filled:
                # fallback: fill first textbox
                username_boxes.first.fill(TARGET_USERNAME)
        else:
            print("[!] No textbox role found to fill username.")
    except Exception as e:
        print("[!] Error filling target username:", e)

    # click "Kullanıcıyı Bul" (Find User) button if present
    try:
        if page.get_by_role("button", name="Kullanıcıyı Bul").count():
            page.get_by_role("button", name="Kullanıcıyı Bul").first.click()
        elif page.locator("button:has-text('Kullanıcıyı Bul')").count():
            page.locator("button:has-text('Kullanıcıyı Bul')").first.click()
        else:
            # maybe button text in english or different — try 'Find' or first button
            if page.get_by_role("button", name=lambda n: n and "Find" in n).count():
                page.get_by_role("button", name=lambda n: n and "Find" in n).first.click()
    except Exception as e:
        print("[!] Error clicking 'Kullanıcıyı Bul':", e)

    time.sleep(0.6)

    # Fill amount
    try:
        tb_count = page.get_by_role("textbox").count()
        if tb_count >= 2:
            page.get_by_role("textbox").nth(1).fill(TARGET_AMOUNT)
        else:
            if page.locator("input[name='amount']").count():
                page.locator("input[name='amount']").first.fill(TARGET_AMOUNT)
            else:
                page.get_by_role("textbox").first.fill(TARGET_AMOUNT)
    except Exception as e:
        print("[!] Error filling amount:", e)

    time.sleep(0.4)

    # Click Start
    try:
        if page.get_by_role("button", name="Start").count():
            page.get_by_role("button", name="Start").first.click()
        elif page.locator("button:has-text('Start')").count():
            page.locator("button:has-text('Start')").first.click()
        else:
            if page.locator("button:has-text('Başlat')").count():
                page.locator("button:has-text('Başlat')").first.click()
    except Exception as e:
        print("[!] Error clicking Start:", e)


# ===== Main runner =====

def run_all():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)

        for cred_idx, username in enumerate(CREDENTIALS, start=1):
            password = make_password(username)
            print(f"\n=== CREDENTIAL [{cred_idx}/{len(CREDENTIALS)}] username={username} password=<hidden> ===")

            # create a fresh context for each credential to avoid session carryover
            context = browser.new_context()

            for site_idx, url in enumerate(sites, start=1):
                print(f"\n--- [{site_idx}/{len(sites)}] {url} ({username}) ---")
                page = context.new_page()
                try:
                    page.goto(url, timeout=60000)
                    success = attempt_login(page, username, password)
                    if not success:
                        print(f"[!] Login attempt failed on {url} using {username}")
                        save_error_screenshot(page, f"login_failed_cred{cred_idx}_site{site_idx}")
                    else:
                        # small wait for post-login redirect/modal close
                        try:
                            page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            pass
                        perform_task_after_login(page)
                        print(f"[+] Done: {url} (user: {username})")
                except Exception as e:
                    print(f"[!] Exception for {url} with {username}: {e}")
                    traceback.print_exc()
                    try:
                        save_error_screenshot(page, f"error_cred{cred_idx}_site{site_idx}")
                    except Exception:
                        pass
                finally:
                    try:
                        page.close()
                    except Exception:
                        pass

                    # small rest between sites
                    time.sleep(1.0)

            # close context (clears cookies/session)
            try:
                context.close()
            except Exception:
                pass

            # small rest between credentials
            time.sleep(1.5)

        browser.close()


if __name__ == "__main__":
    run_all()
