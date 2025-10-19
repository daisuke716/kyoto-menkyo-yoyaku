# 京都府運転免許更新・学科試験 自動予約スクリプト
# Kyoto Driving License Test Auto Booking Script  


## 🧭 Overview | 概要
This project is an **automation tool for booking driving license updates and written exams**  
through the [Kyoto Police Internet reservation system](https://unmen-yoyaku.police.pref.kyoto.lg.jp/menkyo-yoyaku/main](https://unmen-yoyaku.police.pref.kyoto.lg.jp/menkyo-yoyaku/main).  
It automatically fills in user information, searches available time slots, and can confirm reservations automatically.

本プロジェクトは、[京都府警察運転免許予約サイト](https://unmen-yoyaku.police.pref.kyoto.lg.jp/menkyo-yoyaku/main](https://unmen-yoyaku.police.pref.kyoto.lg.jp/menkyo-yoyaku/main)  
を対象とした **免許更新・学科試験のインターネット自動予約ツール** です。  
個人情報の自動入力、空き枠の探索、予約確定までを自動化します。

> ⚠️ **This software is for personal learning and research purposes only.**  
> Commercial or large-scale use is strictly prohibited.  
>  
> ⚠️ **本ツールは個人の学習・研究目的のみに使用可能です。**  
> 商用利用・大量アクセスは禁止されています。

---

## ⚙️ Requirements | 必要環境
- Python 3.8 or later  
- [Playwright](https://playwright.dev/python/) library  
- Stable internet connection

### Install dependencies | 依存関係のインストール
```bash
pip install playwright
playwright install
```

---

## 🚀 Usage | 使い方

### 1️⃣ Edit user settings in `kyoto_exam_auto.py`
```python
USER_CONFIG = {
    "kana": "ヤマダタロウ",
    "confirm_code6": "123456",
    "birth_year": "2001",
    "birth_month": "7",
    "birth_day": "16",
    "email": "example@gmail.com",
}
```
📝 Fill in your actual name, confirmation code, birthday, and email.  
（上記の部分を自分の情報に変更してください。）

---

### 2️⃣ Run the script | スクリプトを実行
```bash
python kyoto_exam_auto.py
```

The program will automatically:
- Open the Kyoto license reservation website  
- Fill in personal data  
- Search available dates within 30 days  
- Automatically click “予約する” when availability is found  
- Play a sound on successful booking  

プログラムは自動的に以下を実行します：
- 京都府免許試験場の予約ページを開く  
- 入力フォームへの自動入力  
- 30日以内の空き枠検索  
- 自動で「予約する」をクリック  
- 成功時に音声で通知  

---

## ⚙️ Configuration | 設定項目

| Variable | Description (English) | 説明 (日本語) | Default |
|-----------|----------------------|----------------|----------|
| `HEADLESS` | Run browser in headless mode | ブラウザを非表示モードで実行 | `False` |
| `CHECK_INTERVAL_SEC` | Interval between retry checks (seconds) | 再チェック間隔（秒） | `60` |
| `AUTO_SUBMIT` | Automatically click “予約する” in Step 6 | Step6で自動的に「予約する」をクリック | `True` |
| `STOP_AFTER_CLICK` | Stop after one reservation attempt | 予約完了後に停止 | `True` |
| `SLOW_MO` | Delay between browser actions (ms) | 操作間の遅延（ミリ秒） | `120` |

---

## 🧠 Notes | 注意事項

- This script uses **Playwright** to simulate normal browser operations.  
  Please **avoid excessive access or automation loops** to prevent server overload.  
- Kyoto Police or related organizations are **not affiliated** with this software.  
- All entered personal data is processed **locally only**, never uploaded anywhere.  
- Tested on macOS and Windows with Chromium browser.

本スクリプトは Playwright により通常のブラウザ操作を模倣しています。  
短時間に大量のアクセスを行うことは避けてください。  
京都府警察や関連機関とは一切関係ありません。  
入力された個人情報はローカル環境内でのみ処理されます。  
macOS および Windows（Chromium ブラウザ）で動作確認済みです。

---

## 🧾 License | ライセンス

This software is provided **as-is**, without warranty of any kind.  
Use or modify freely **for personal learning and research purposes only**.

本ソフトウェアは無保証のまま提供されます。  
**学習・研究目的に限り**、自由に使用・改変可能です。

---
