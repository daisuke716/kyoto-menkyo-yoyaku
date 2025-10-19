# kyoto_exam_auto.py
import re
import asyncio
from datetime import datetime, timedelta, date
from playwright.async_api import async_playwright, Page, TimeoutError
import calendar
import os, sys, asyncio


URL = "https://unmen-yoyaku.police.pref.kyoto.lg.jp/menkyo-yoyaku/main"

# ===== 配置 =====
FLOW_CONFIG = {
    "step1_choice": "学科試験",        # 或 "免許更新"
    "step2_choice": "原付以外",        # 或 "原付"
    "step3_place_button": "運転免許試験場",
}
USER_CONFIG = {
    "kana": "ヤマダタロウ", # 例：ヤマダタロウ
    "confirm_code6": "123456", # 例：123456　6桁の予約番号
    "birth_year": "2001", # 例：2001
    "birth_month": "7", # 例：7
    "birth_day": "16", # 例：16
    "email": "adaisuke716@gmail.com",
}

# debug
CHECK_INTERVAL_SEC = 60
AUTO_SUBMIT = True  # auto submit on step 6
STOP_AFTER_CLICK = True
HEADLESS = False        # browser headless mode
SLOW_MO = 120

TIME_BUTTON_PREFIX = "受付時間"
NO_SEATS_PATTERN = "残り：0名"
NEXT_MONTH_BTNS = ["＞", ">", "›", "次へ", "次"]  # next month buttons

# ===== tools =====
STEP_HEADERS = {
    1: "1.予約する手続きを選択してください。",
    2: "2.予約する講習または試験を選択してください。",
    3: "3.予約する場所を選択してください。",
    4: "4.予約者の情報を入力してください。",
    5: "5.受付を希望する日付を選択してください。",
    6: "6.予約内容を確認してください。",
}
import re


async def wait_idle(page: Page, t=10_000):
    try:
        await page.wait_for_load_state("networkidle", timeout=t)
    except TimeoutError:
        pass

async def wait_step_header(page: Page, step: int, timeout_ms=15000):
    await page.wait_for_selector(f"text={STEP_HEADERS[step]}", timeout=timeout_ms)

async def at_step(page: Page, step: int) -> bool:
    return await page.get_by_text(STEP_HEADERS[step]).first.is_visible()

async def click_big_blue(page: Page, label: str, timeout_ms=8000) -> bool:
    try:
        loc = page.get_by_role("button", name=re.compile(re.escape(label))).first
        await loc.wait_for(state="visible", timeout=timeout_ms)
        await loc.scroll_into_view_if_needed()
        await loc.click()
        await wait_idle(page)
        return True
    except:
        pass
    for sel in (f"button:has-text('{label}')", f"a:has-text('{label}')"):
        try:
            loc = page.locator(sel).first
            await loc.wait_for(state="visible", timeout=timeout_ms)
            await loc.scroll_into_view_if_needed()
            await loc.click()
            await wait_idle(page)
            return True
        except:
            continue
    return False

# ===== 0→3  =====
async def step0_intro(page: Page):
    for role in ("button", "link"):
        loc = page.get_by_role(role, name="予約登録").first
        if await loc.is_visible():
            await loc.click(); await wait_idle(page); break

async def step1_select(page: Page):
    await wait_step_header(page, 1)
    btn = page.get_by_role("button", name=FLOW_CONFIG["step1_choice"]).first
    await btn.wait_for(state="visible"); await btn.scroll_into_view_if_needed(); await btn.click()
    await wait_step_header(page, 2)

async def step2_select(page: Page):
    await wait_step_header(page, 2)
    if not await click_big_blue(page, FLOW_CONFIG["step2_choice"]):
        btn = page.get_by_role("button", name=FLOW_CONFIG["step2_choice"]).first
        await btn.wait_for(state="visible"); await btn.click()
    await wait_step_header(page, 3)

async def step3_select_place(page: Page):
    await wait_step_header(page, 3)
    if not await click_big_blue(page, FLOW_CONFIG["step3_place_button"]):
        btn = page.get_by_role("button", name=FLOW_CONFIG["step3_place_button"]).first
        await btn.wait_for(state="visible"); await btn.click()
    await wait_step_header(page, 4)

# ========= Step4(Recovery: text anchor + DOM order fallback)  =========
async def _first_visible(page: Page, loc):
    try:
        await loc.first.wait_for(state="visible", timeout=1500)
        return loc.first
    except:
        return None

async def _nearest_input_below(page: Page, text_list: list[str], dy_limit: float = 180.0):
    """
    Find a visible element containing given text and return the nearest visible, enabled <input> element below it (within dy_limit).
    """
    anchor = None
    for t in text_list:
        loc = page.locator(f"xpath=(//*[contains(normalize-space(), '{t}')])[1]")
        anchor = await _first_visible(page, loc)
        if anchor: break
    if not anchor:
        return None

    ab = await anchor.bounding_box()
    if not ab: return None
    ay = ab["y"]

    cand = page.locator("input:not([type='hidden'])").filter(has_not=page.locator("[disabled]"))
    n = await cand.count()
    best_i, best_dy = None, 10**9
    for i in range(n):
        el = cand.nth(i)
        if not await el.is_visible():
            continue
        bb = await el.bounding_box()
        if not bb:
            continue
        dy = bb["y"] - ay
        if 0 < dy <= dy_limit and dy < best_dy:
            best_i, best_dy = i, dy
    return cand.nth(best_i) if best_i is not None else None

async def _select_by_value_or_label_contains(sel, target_text: str) -> bool:
    try:
        await sel.select_option(target_text)
        return True
    except:
        pass
    try:
        options = sel.locator("option")
        m = await options.count()
        for i in range(m):
            opt = options.nth(i)
            label = (await opt.inner_text()).strip()
            val = (await opt.get_attribute("value")) or ""
            if (target_text in label) or (label == target_text) or (val == target_text):
                await sel.select_option(val or label)
                return True
    except:
        pass
    return False

async def _first_form_inputs_in_order(page: Page, n: int = 4):
    """Return the first n visible <input> elements in the form (excluding hidden/disabled)."""
    form = page.locator("form").first
    scope = form if await form.is_visible() else page
    items = scope.locator("input:not([type='hidden'])").filter(has_not=page.locator("[disabled]"))
    arr = []
    cnt = await items.count()
    for i in range(cnt):
        el = items.nth(i)
        if await el.is_visible():
            arr.append(el)
        if len(arr) >= n:
            break
    return arr

async def force_go_step5(page: Page) -> bool:
    # Trigger input validation
    try:
        await page.evaluate("""
            () => {
              document.querySelectorAll('input,select').forEach(el=>{
                el.dispatchEvent(new Event('input',  {bubbles:true}));
                el.dispatchEvent(new Event('change', {bubbles:true}));
              });
            }
        """)
    except:
        pass

    # Try clicking“次へ/進む/提交”
    selectors = [
        "button:has-text('予約希望日時')",
        "button:has-text('次へ')",
        "button:has-text('次')",
        "button:has-text('進む')",
        "button:has-text('次に進む')",
        "input[type='submit']",
        "button[type='submit']",
    ]
    for sel in selectors:
        btn = page.locator(sel).first
        if await btn.is_visible():
            try:
                await btn.scroll_into_view_if_needed()
            except:
                pass
            for _ in range(2):
                try:
                    await btn.click()
                    await wait_idle(page)
                    if await at_step(page, 5):
                        return True
                except:
                    continue

    # Fallback: submit form or press Enter
    form = page.locator("form").first
    if await form.is_visible():
        try:
            await form.evaluate("f => (f.requestSubmit ? f.requestSubmit() : f.submit())")
            await wait_idle(page)
            if await at_step(page, 5):
                return True
        except:
            pass
    try:
        await page.keyboard.press("Enter")
        await wait_idle(page)
        if await at_step(page, 5):
            return True
    except:
        pass
    return False

async def step4_fill(page: Page):
    if not await at_step(page, 4):
        return
    await wait_step_header(page, 4)

    # 1) Locate inputs by text anchors
    kana   = await _nearest_input_below(page, ["氏名(カナ", "氏名（カナ", "カナ"])
    code   = await _nearest_input_below(page, ["本人確認番号", "本人確認番号(数字6桁)", "確認番号", "数字6桁"])
    email1 = await _nearest_input_below(page, ["e-mail", "メールアドレス"])
    email2 = await _nearest_input_below(page, ["e-mail（確認用）", "e-mail(確認用)", "メール（確認用）", "メール(確認用)", "確認用"])

    # 2) Fallback: use first 4 visible inputs in DOM order (Kana → code → email → confirm email)
    if not (kana and code and email1 and email2):
        arr = await _first_form_inputs_in_order(page, 4)
        idx = 0
        if kana is None and idx < len(arr):   kana   = arr[idx]; idx += 1
        if code is None and idx < len(arr):   code   = arr[idx]; idx += 1
        if email1 is None and idx < len(arr): email1 = arr[idx]; idx += 1
        if email2 is None and idx < len(arr): email2 = arr[idx]; idx += 1

    # 3) Birth date (first 3 visible <select>)
    selects = page.locator("select")
    for _ in range(20):
        if await selects.count() >= 3 and all([await selects.nth(i).is_visible() for i in range(3)]):
            break
        await asyncio.sleep(0.1)
    try:
        year_sel = selects.nth(0); month_sel = selects.nth(1); day_sel = selects.nth(2)
        await _select_by_value_or_label_contains(year_sel,  USER_CONFIG["birth_year"])
        await _select_by_value_or_label_contains(month_sel, USER_CONFIG["birth_month"])
        await _select_by_value_or_label_contains(day_sel,   USER_CONFIG["birth_day"])
    except:
        pass

    # 4) Fill safely (only if value is different)
    async def fill_once(el, value):
        if not el: return
        for _ in range(15):
            if await el.is_enabled(): break
            await asyncio.sleep(0.1)
        if not await el.is_enabled(): return
        cur = (await el.input_value() or "").strip()
        if cur != value:
            await el.fill("")
            await asyncio.sleep(0.03)
            await el.fill(value)

    await fill_once(kana,   USER_CONFIG["kana"])
    await fill_once(code,   USER_CONFIG["confirm_code6"])
    await fill_once(email1, USER_CONFIG["email"])
    await fill_once(email2, USER_CONFIG["email"])

    # 5) Proceed to next step (ensure reaching step 5)
    await force_go_step5(page)

# ===== Step 5: Search day by day from today up to 30 days ahead (cross-month supported) =====
def _parse_month_title(text: str) -> tuple[int, int]:
    y = int(text.split("年")[0])
    m = int(text.split("年")[1].split("月")[0])
    return y, m

async def go_next_month(page: Page) -> bool:
    """Click “Next month” as reliably as possible and verify the month actually advanced."""
    # Current month
    title_loc = page.locator(r"text=/\d{4}年\d{1,2}月/").first
    await title_loc.wait_for(state="visible", timeout=5000)
    prev_title = (await title_loc.inner_text()).strip()

    # Candidate locators (from stable to aggressive)
    candidates = [
        page.get_by_role("button", name=re.compile(r"(次|翌|›|＞|>|▶)")).first,
        page.get_by_role("link",   name=re.compile(r"(次|翌|›|＞|>|▶)")).first,
        page.locator("text='＞'").first,
        page.locator("text='>'").first,
        page.locator("text='›'").first,
        page.locator("text='▶'").first,
        page.locator("text='次へ'").first,
        page.locator("text='次'").first,
        page.locator("[aria-label*='次'], [title*='次'], [class*='next'], [class*='Next'], [class*='arrow'], [class*='navNext']").first,
    ]

    async def _changed() -> bool:
        try:
            await page.wait_for_timeout(200)  # wait for UI update
            cur = (await title_loc.inner_text()).strip()
            return cur != prev_title
        except:
            return False

    # Try clicking each candidate
    for loc in candidates:
        try:
            if await loc.is_visible():
                try:
                    await loc.scroll_into_view_if_needed()
                except:
                    pass
                try:
                    await loc.click()
                except:
                    await loc.click(force=True)
                if await _changed():
                    return True
        except:
            continue

    # Aggressive: search by text content and click nearest clickable parent
    try:
        await page.evaluate("""
        () => {
          const looksNext = (el) => {
            const t = (el.textContent || '').trim();
            const aria = (el.getAttribute('aria-label') || '');
            const title = (el.getAttribute('title') || '');
            return ['>','＞','›','▶'].includes(t) || /次|翌/.test(t+aria+title);
          };
          const clickNearest = (el) => {
            let cur = el;
            for (let i=0; i<4 && cur; i++) {
              if (cur.click) { try { cur.click(); return true; } catch(e) {}
              cur = cur.parentElement;
            }
            return false;
          };
          const nodes = Array.from(document.querySelectorAll('*')).filter(looksNext);
          for (const n of nodes) {
            if (clickNearest(n)) return true;
          }
          return false;
        }
        """)
        # Check if month changed
        if (await title_loc.inner_text()).strip() != prev_title:
            return True
    except:
        pass

    return False

# ===== Step 5: Find and book within the next 30 days (cross-month supported) =====
async def find_and_book_within_next_30_days(page: Page):
    if not await at_step(page, 5):
        return None

    start_d: date = date.today()
    end_d:   date = start_d + timedelta(days=32)
    num_re = re.compile(r"^\s*\d{1,2}\s*$")

    while True:
        # Get current month
        title_loc = page.locator(r"text=/\d{4}年\d{1,2}月/").first
        await title_loc.wait_for(state="visible", timeout=5000)
        mt = (await title_loc.inner_text()).strip()
        yyyy = int(mt.split("年")[0])
        mm   = int(mt.split("年")[1].split("月")[0])
        last_day = calendar.monthrange(yyyy, mm)[1]

        # Stop if exceeded date range
        if date(yyyy, mm, 1) > end_d.replace(day=1):
            return None

        # Calendar visible region (between header and “time slot selection”)
        mt_bb = await title_loc.bounding_box()
        y_top = mt_bb["y"] if mt_bb else 0
        time_hdr = page.get_by_text("受付を希望する時間を選択してください。").first
        y_bottom = 10**9
        if await time_hdr.is_visible():
            th_bb = await time_hdr.bounding_box()
            if th_bb: y_bottom = th_bb["y"]

        # Collect day buttons
        all_nodes = page.locator("button, [role='button'], a, td, div").filter(has_text=num_re)
        cnt = await all_nodes.count()
        day_nodes = []
        for i in range(cnt):
            el = all_nodes.nth(i)
            if not await el.is_visible(): 
                continue
            dis_attr = (await el.get_attribute("disabled")) is not None
            aria_dis = (await el.get_attribute("aria-disabled")) == "true"
            cls = (await el.get_attribute("class") or "")
            if dis_attr or aria_dis or ("disabled" in cls): 
                continue
            bb = await el.bounding_box()
            if not bb or not (y_top < bb["y"] < y_bottom):
                continue
            txt = (await el.inner_text()).strip()
            try:
                dd = int(txt)
            except:
                continue
            if dd < 1 or dd > last_day:
                continue
            cur_d = date(yyyy, mm, dd)
            if cur_d < start_d or cur_d > end_d:
                continue
            day_nodes.append((cur_d, (bb["y"], bb["x"]), el))

        # If no clickable days in this month → go to next month
        if not day_nodes:
            moved = await go_next_month(page)
            if not moved:
                return None
            continue

        # Keep only one node per day (top-most)
        best = {}
        for d, pos, el in day_nodes:
            if d not in best or pos < best[d][0]:
                best[d] = (pos, el)

        # Check each date in order
        for d, (pos, el) in sorted(best.items(), key=lambda kv: kv[0]):
            print(f"[CHECK] Checking {d.isoformat()}")

            try:
                await el.scroll_into_view_if_needed()
                await el.click()
            except:
                continue

            await asyncio.sleep(0.2)

            # Collect time slot buttons
            time_btns = page.get_by_role("button").filter(has_text=TIME_BUTTON_PREFIX)
            tcnt = await time_btns.count()
            if tcnt == 0:
                print(f"[SKIP] {d.isoformat()} No available time slots, skipping.")
                continue

            found_slot = False
            for j in range(tcnt):
                tb = time_btns.nth(j)
                if not await tb.is_visible():
                    continue
                try:
                    label = (await tb.inner_text()).strip()
                except:
                    label = ""
                if not label or NO_SEATS_PATTERN in label:
                    continue
                dis_attr = (await tb.get_attribute("disabled")) is not None
                aria_dis = (await tb.get_attribute("aria-disabled")) == "true"
                cls = (await tb.get_attribute("class") or "")
                if dis_attr or aria_dis or ("disabled" in cls):
                    continue

                try:
                    await tb.click()
                except:
                    try:
                        await tb.click(force=True)
                    except:
                        continue

                # Extract time range + 残り人数
                time_range = "未取得"
                remain_info = ""
                if "：" in label:
                    try:
                        # label 示例: "受付時間：08:50-09:10　残り：2名"
                        parts = label.split("：", 1)[1].split("　")
                        time_range = parts[0].strip() if parts else "未取得"
                        if len(parts) > 1:
                            remain_info = parts[1].strip()
                    except:
                        pass
                now = datetime.now().strftime("%H:%M:%S")            
                print(f"[INFO][{now}] Selected：{d.isoformat()} {time_range} ({remain_info})")
                return d.isoformat(), f"{time_range} ({remain_info})"

                found_slot = True

            if not found_slot:
                print(f"[SKIP] {d.isoformat()} No available slots, skipping.")

        # Move to next month if nothing found
        moved = await go_next_month(page)
        if not moved:
            return None



# ===== Step 6 (auto check + submit) =====
async def step6_submit(page: Page):
    """Step 6: Automatically check confirmation box, submit, and play sound on success."""
    print("[STEP] Checking if step 6 page is reached...")

    try:
        await page.wait_for_selector("text=6.予約内容確認", timeout=5000)
        print("[STEP] Step 6 confirmed: Reservation confirmation page detected.")
    except:
        # Fallback: match any element containing “予約内容確認”
        try:
            await page.wait_for_selector("text=予約内容確認", timeout=5000)
            print("[STEP] Step 6 (fuzzy match) detected.")
        except:
            print("[ERROR] Step 6 title not detected, attempting to continue anyway.")

    # ==== Auto check ====
    checked = False
    try:
        # 京都府page label: 上記予約内容を確認いたしました。
        label = page.locator("text=上記予約内容を確認いたしました。").first
        await label.wait_for(state="visible", timeout=3000)

        checkbox = page.locator("input[type='checkbox']").first
        if await checkbox.count() > 0:
            if not await checkbox.is_checked():
                try:
                    await checkbox.click(force=True)
                except:
                    await page.evaluate("""
                        () => {
                            const cb = document.querySelector('input[type="checkbox"]');
                            if (cb) { cb.checked = true; cb.dispatchEvent(new Event('change', {bubbles:true})); }
                        }
                    """)
            checked = True
    except Exception as e:
        print(f"[WARN] Failed to check confirmation box: {e}")

    if checked:
        print("[INFO] Confirmation checkbox checked automatically.")

    # ==== 2️⃣ Auto click「予約する」 ====
    clicked = False
    try:
        btn = page.get_by_role("button", name=re.compile("予約する")).first
        await btn.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)
        await btn.click()
        clicked = True
        await page.wait_for_timeout(3000)
    except:
        try:
            btn = page.locator("button:has-text('予約'), input[value*='予約']").first
            await btn.scroll_into_view_if_needed()
            await btn.click()
            clicked = True
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[WARN] Failed to click '予約する': {e}")

    # ==== 3️⃣ 发出声音提示 ====
    def _beep():
        try:
            if sys.platform.startswith("darwin"):
                os.system("say '予約完了'")  # macOS voice alert
            elif sys.platform.startswith("win"):
                import winsound
                winsound.Beep(800, 400)
                winsound.Beep(1200, 400)
            else:
                sys.stdout.write('\a')
                sys.stdout.flush()
        except Exception as e:
            print(f"[WARN] 无法发声: {e}")

    now = datetime.now().strftime("%H:%M:%S")
    if clicked:
        print(f"[{now}] ✅ Automatically clicked '予約する' button. Reservation complete!")
        _beep()
    else:
        print(f"[{now}] ⚠️ Could not find '予約する' button. Please click manually.")
        _beep()

# ===== main =====
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        ctx = await browser.new_context(locale="ja-JP")
        page = await ctx.new_page()
        await page.goto(URL); await wait_idle(page)

        # 1→4
        await step0_intro(page)
        await step1_select(page)
        await step2_select(page)
        await step3_select_place(page)
        await step4_fill(page)

        while True:
            if await at_step(page, 4):
                await step4_fill(page)
                continue
            if not await at_step(page, 5):
                # Try to advance to step 5
                for t in ["次へ", "進む", "次", "次に進む"]:
                    b = page.get_by_role("button", name=t).first
                    if await b.is_visible():
                        try:
                            await b.click(); await wait_idle(page)
                        except:
                            pass
                if not await at_step(page, 5):
                    # Unable to reach step 5, restart from beginning
                    await page.goto(URL); await wait_idle(page)
                    await step0_intro(page); await step1_select(page); await step2_select(page); await step3_select_place(page)
                    await step4_fill(page)
                    continue

            res = await find_and_book_within_next_30_days(page)
            if res:
                # res[0] = 日期, res[1] = "時間帯 (残りX名)"
                print(f"[SUCCESS] Found available reservation: {res[0]} {res[1]}")

                if AUTO_SUBMIT:
                    await step6_submit(page)

                if STOP_AFTER_CLICK:
                    # More precise message depending on AUTO_SUBMIT flag
                    if AUTO_SUBMIT:
                        print("Reservation auto-submitted. Keep page open to confirm result. Close browser or press Ctrl+C to exit.")
                    else:
                        print("[DONE] Time slot selected; waiting on confirmation/submission page. Close browser or press Ctrl+C to exit.")

                    try:
                        # Keep the page open
                        while not page.is_closed():
                            await asyncio.sleep(60)
                    except asyncio.CancelledError:
                        pass
                return

            now = datetime.now().strftime("%H:%M:%S")
            print(f"[{now}] No availability within 30 days. Retrying in {CHECK_INTERVAL_SEC}s…")
            await asyncio.sleep(CHECK_INTERVAL_SEC)
            await page.reload(); await wait_idle(page)

if __name__ == "__main__":
    asyncio.run(main())
