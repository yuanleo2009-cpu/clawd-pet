# ClawdPet：Clawd 桌寵

一隻住在 Windows 桌面上的橘色像素小螃蟹 Clawd。雙擊牠，就會打開桌面版 Claude。

![Clawd 示範：揮手打招呼、橫著走、被摸摸冒愛心、被拎起來猛搖、摔下來暈頭轉向、跳舞](docs/demo.gif)

**下載：**到 [Releases](../../releases/latest) 下載 `ClawdPet-Setup-*.exe`，雙擊安裝即可（Windows 10/11，64 位元）。

> 非官方的粉絲作品，與 Anthropic 無關，也未獲其認可。程式碼以 [MIT 授權](LICENSE) 釋出；**授權只涵蓋程式碼**，Clawd 形象與 Claude 商標歸 Anthropic 所有，不在授權範圍內。僅供個人非商業使用。
>
> 介面目前只有繁體中文（安裝精靈支援繁中、簡中、英文）。每一版改了什麼見 [更新紀錄](CHANGELOG.md)。

---

# 使用者說明

## 安裝

1. 從 [Releases](../../releases/latest) 下載 `ClawdPet-Setup-<版本>.exe`。
2. 雙擊執行。安裝檔沒有數位簽章，Windows 可能顯示「Windows 已保護你的電腦」：點「其他資訊」→「仍要執行」。
   - 想確認檔案沒被動過：每個 Release 都附有 SHA-256，可以用 PowerShell 比對：
     ```powershell
     Get-FileHash .\ClawdPet-Setup-1.1.0.exe -Algorithm SHA256
     ```
   - 從 v1.1.0 起，安裝檔由 GitHub Actions 從公開的原始碼自動打包（見 `.github/workflows/release.yml`），打包過程記錄在 Actions 頁面，任何人都能檢查。
3. 依精靈安裝：只裝給目前使用者，不需要系統管理員權限。可以選擇建立桌面捷徑、開機自動啟動。
4. 安裝完會檢查電腦裡有沒有 Claude 桌面版；沒有的話會問你要不要打開 https://claude.ai/download 。

安裝後可以從「開始」功能表或 Windows 搜尋輸入 `Clawd` 開啟。

## 怎麼玩

| 操作 | 反應 |
|---|---|
| 放著不管 | 緩慢上下浮動、眨眼、左右張望；偶爾在工作列上橫著走一走，或自己跳舞、轉圈；3 分鐘沒人理就睡覺（冒 z） |
| 滑鼠靠近 | 轉身看向滑鼠 |
| 滑鼠在牠身上來回滑 | 摸摸頭：開心地扭來扭去、冒愛心（睡著的話會被摸醒） |
| 單擊 | 隨機：跳一下、壓扁回彈、搖晃、轉一圈，或冒泡泡說一句話（邊說邊揮手） |
| 雙擊 | 開啟桌面版 Claude（已經開著的話，會把視窗叫到最前面；沒安裝會提示去下載） |
| 拖動 | 被拎起來：身體拉長、手舉高、腳垂下，隨拖動方向晃動 |
| 拖著快速左右晃 | 放下後會被搖暈：X X 眼、頭上星星繞圈 |
| 放開 | 像受重力一樣掉下去，站在工作列上（半空中可以再接住牠） |
| 用力一甩再放開 | 被丟出去：在空中轉圈、撞到螢幕邊緣會彈回來、摔到地上彈一兩下 |
| 在牠身上滾動滑鼠滾輪 | 往上變大、往下變小 |
| 右鍵 | 設定選單（見下方） |
| 工作列右下角圖示（^ 箭頭裡） | 左鍵：顯示 / 隱藏 Clawd；右鍵：同一份設定選單 |

視窗透明、無邊框、永遠在最上層，不佔工作列，也不會出現在 Alt+Tab 裡。透明的地方滑鼠會直接穿透，不影響你操作底下的視窗。

## 右鍵選單

- **🚀 開啟 Claude**：和雙擊一樣。
- **🎭 動作**：跳舞、轉一圈、揮手打招呼、走一走、餵點心、開合跳、躲貓貓、睡覺（會先打哈欠伸懶腰）；開關「閒著時到處走走」「滑鼠靠近時轉頭看」「跟著滑鼠走」。
- **⏰ 提醒**：番茄鐘（專注 25 分鐘 → 休息 5 分鐘）、喝水提醒（每 30 / 45 / 60 / 90 分鐘）、整點報時。Clawd 被隱藏時會改用 Windows 通知。
- **💻 進階：終端機版 Claude Code**：在指定的專案資料夾裡用終端機開啟命令列版 Claude Code（需要另外安裝 `claude` 指令）。
- **📏 大小**：小 / 中 / 大 / 特大（寬約 96 / 128 / 160 / 192 px），會依螢幕縮放比例換算，保持整數倍放大，不會模糊。
- **🎞 畫面**
  - 幀率：30、60、120（預設）、144、240，或跟隨螢幕更新率。睡著時會自動降到 30 FPS 省電。
  - 抗鋸齒（平滑）：預設開啟，旋轉、擠壓、浮動時邊緣平滑；關掉就是純像素銳利模式。
- **🧲 吸附底部**：放開後總是落到底部（預設）/ 靠近底部時吸附 / 關閉；還有「立刻落到底部」。
- **🎨 造型**：內建 Clawd，或使用自訂圖片（見「自訂」）。
- **💬 說話**：點擊時冒泡泡、偶爾自言自語、編輯台詞。
- **⚙ 開機自動啟動**、**📍 重設位置**、**👋 結束**。最下面會顯示目前版本。

Windows 11 預設把新圖示收在 ^ 箭頭裡；想讓它一直顯示，把圖示從箭頭裡拖到工作列上即可。

## 自訂

- **台詞**：右鍵 → 💬 說話 → 編輯台詞…。每行一句，存檔後立即生效。
- **自訂圖片**：把透明背景的 PNG 命名為 `clawd.png`，放到安裝資料夾的 `assets\` 裡（`%LOCALAPPDATA%\Programs\ClawdPet\assets\clawd.png`，沒有 `assets` 就自己建），或放到 `%APPDATA%\ClawdPet\clawd.png`；然後右鍵 → 🎨 造型 → 自訂圖片。已經放大過的像素圖會自動還原成原始像素；單張圖模式下所有動作都靠變換。

## 資料存放位置

| 內容 | 位置 |
|---|---|
| 程式本體 | `%LOCALAPPDATA%\Programs\ClawdPet` |
| 設定（位置、大小、幀率…） | `%APPDATA%\ClawdPet\settings.json`（刪掉就恢復預設；手改壞的欄位會自動改用預設值） |
| 台詞 | `%APPDATA%\ClawdPet\phrases.txt` |
| 錯誤紀錄 | `%APPDATA%\ClawdPet\error.log`（程式出錯時才會產生，回報問題時請附上） |

## 解除安裝

「設定 → 應用程式」搜尋「Clawd 桌寵」→ 解除安裝。會先請 Clawd 正常結束，並清掉開機自動啟動；最後會問你要不要一併刪除設定與台詞。

---

# 開發者說明

## 環境

需要 Windows 10/11 與 Python 3.13。

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# 執行（pythonw 不會跳出主控台視窗；想看錯誤訊息改用 python）
.\.venv\Scripts\pythonw.exe main.py

# 單元測試
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

- `requirements.txt`：執行需要的套件（PySide6）。
- `requirements-dev.txt`：再加上打包用的 PyInstaller，以及產生示範動畫用的 Pillow。

## 打包

```powershell
.\build.ps1
```

需要 Inno Setup 6（`winget install JRSoftware.InnoSetup`）。會產生：

- `dist\ClawdPet\`：程式資料夾（`ClawdPet.exe` + `_internal\`）。用資料夾模式而不是單一 exe，啟動不用每次解壓到 `%TEMP%`，比較快、不留暫存檔，也比較不會被防毒誤判。
- `dist\ClawdPet-Setup-<版本>.exe`：安裝包（約 25 MB），以及同名的 `.sha256`。

`ClawdPet.spec` 會拿掉用不到的元件（軟體 OpenGL、加密函式庫、多餘的 Qt 外掛）來瘦身。

## 發布新版本

1. 改 `services/version.py` 的 `__version__`（安裝包和選單裡的版本都從這裡來）。
2. 在 [`CHANGELOG.md`](CHANGELOG.md) 最上面新增這一版的段落（`## [版本] - 日期`），寫清楚新功能、改進、修正。
   沒寫的話，自動打包會在一開始就失敗。可以先自己檢查：
   ```powershell
   .\.venv\Scripts\python.exe tools\release_notes.py 1.2.0 --check
   ```
3. commit 後推一個同名的 tag，例如：
   ```powershell
   git tag v1.2.0
   git push origin main v1.2.0
   ```
4. GitHub Actions（`.github/workflows/release.yml`）會在 Windows 機器上跑測試、打包，並建立 Release。Release 說明會自動放上 CHANGELOG 裡這一版的更新內容、安裝說明、SHA-256 與打包紀錄連結。

## 檔案結構

```
main.py                 程式入口；只允許一隻（再開一次會叫原本那隻出來；--quit 請它正常結束）
pet/
  window.py             主視窗：繪製、滑鼠（單擊/雙擊/拖動）、吸附、工作列圖示、右鍵選單
  animator.py           動畫狀態機（純計算，時間由外部傳入，方便測試）
  sprites.py            讀取素材，整數倍最近鄰放大；自訂單張圖片
  effects.py            特效：灰塵、愛心、音符、點心、汗滴、驚嘆號
  bubble.py             對話泡泡
  phrases.py            台詞讀取（存檔後立即生效）
services/
  launcher.py           開啟桌面版 Claude / 終端機版 Claude Code
  autostart.py          開機自動啟動（目前使用者的登錄機碼，不需要系統管理員）
  settings.py           設定檔（逐欄檢查，壞掉的值改用預設）
  paths.py              路徑（開發模式 / 打包後通用）
  reminders.py          提醒：喝水、番茄鐘、整點報時（純邏輯，時間由外部傳入）
  version.py            版本號
tools/
  make_sprites.py       用程式畫出所有動作的素材
  make_demo_gif.py      產生 docs/demo.gif（離屏繪製）
  release_notes.py      從 CHANGELOG.md 取出某一版的更新內容，組成 Release 說明
tests/                  單元測試（動畫、提醒、設定檔）
installer/              Inno Setup 安裝腳本與中文語系檔
assets/                 素材、圖示、預設台詞
docs/                   README 用的圖
```

## 技術說明

- **Python + PySide6 (Qt 6)**：透明無邊框置頂視窗、滑鼠穿透、高 DPI 都由 Qt 原生支援。
- **像素清晰**：素材以「螢幕實際像素」的整數倍最近鄰放大；抗鋸齒模式再加 2 倍超取樣後平滑縮放。
- **動畫**：一個計時器以設定的幀率（預設 120，睡著時 30）呼叫 `animator.py`，算出這一幀要顯示的圖與位移、縮放、旋轉。
- **開啟 Claude**：桌面版用 Windows 應用程式 ID（`shell:AppsFolder`）啟動；終端機版的指令用 `-EncodedCommand` 傳遞，路徑有空白、引號、分號都不會出錯。
- **修改造型**：改 `tools/make_sprites.py`（以「格」為單位畫矩形），`build.ps1` 會重新產生素材。
