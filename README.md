# ClawdPet：Clawd 桌面宠物

一只住在 Windows 桌面上的橘色像素小螃蟹 Clawd。双击它，就会打开桌面版 Claude 应用。

**下载：**到 [Releases](../../releases/latest) 下载 `ClawdPet-Setup-*.exe`，双击安装即可（Windows 10/11，64 位）。

> 粉丝自制的非官方作品，与 Anthropic 无关，也未获其认可。Clawd 形象及 Claude 商标归 Anthropic 所有。仅供个人非商业使用。

## 功能

| 操作 | 反应 |
|---|---|
| 放着不管 | 缓慢上下浮动、眨眼、偶尔转身左右张望；3 分钟没人理就睡觉（冒 z） |
| 单击 | 随机：跳一下、压扁回弹、摇晃，或冒气泡说一句话（边说边挥手） |
| 双击 | 打开桌面版 Claude 应用（已经开着的话，会把窗口叫到最前面） |
| 拖动 | 被拎起来：身体拉长、手举高、脚垂下，随拖动方向晃动；放下会回弹，并记住位置 |
| 拖动后放开 | 吸附：像受重力一样掉下去，站在工作列上（可以在半空中接住它） |
| 工作列右下角图标（^ 箭头里） | 左键：显示或隐藏 Clawd；右键：完整设置菜单，包括「结束」 |
| 右键 | 菜单：开启 Claude、进阶（终端版 Claude Code）、大小、画面（帧率、抗锯齿）、造型、说话设置、开机自启、重设位置、退出 |

**吸附底部**（右键 → 🧲 吸附底部）：
- 放开后总是落到底部（默认）
- 靠近底部时吸附
- 关闭
- 「立刻落到底部」可以马上让它掉下去。

**工作列图标**：Windows 11 默认把新图标收在 ^ 箭头里。想让它一直显示在工作列上，把图标从箭头里拖到工作列上就行。

**画面设置**（右键 → 🎞 畫面）：
- 帧率：可选 30、60、120（默认）、144、240，或跟随屏幕刷新率。120 FPS 下约占 0.5% 的 CPU。
- 抗锯齿（平滑）：默认开启。素材以 2 倍精度准备，再平滑缩放，所以旋转、挤压、浮动时边缘都是平滑的；关掉就是纯像素锐利模式。

窗口透明、无边框、始终置顶，不占任务栏，也不出现在 Alt+Tab 里。透明的地方鼠标会直接穿透，不影响你操作底下的窗口。

## 安装包（给朋友用）

把 `dist\ClawdPet-Setup-1.0.0.exe` 传给朋友，他们双击后按向导安装即可：

- **安装位置：**只装给当前用户（`%LOCALAPPDATA%\Programs\ClawdPet`），不需要管理员权限。
- **向导语言：**会依系统语言自动选择繁体中文、简体中文或英文。
- **可选项：**桌面快捷方式、开机自动启动；最后一页可以勾「立即启动」。
- **检查 Claude：**安装完会检查电脑里有没有 Claude 桌面版。没有的话，会询问是否打开 https://claude.ai/download。
- **双击 Clawd：**会自动找到朋友电脑里的 Claude 桌面版，不管是从 Microsoft Store 还是官网安装的都可以；找不到时也会提示去下载。
- **卸载：**在「设置 → 应用」里卸载，会一并清掉开机自启。
- **重新安装：**新版直接覆盖安装，会自动先关掉正在运行的 Clawd。

> 安装包没有数字签名，第一次运行时 Windows 可能显示「Windows 已保护你的电脑」。点「更多信息」→「仍要运行」即可。
> 本程序是粉丝自制，与 Anthropic 无关；Clawd 形象属于 Anthropic，请只在朋友之间私下分享，不要公开发布或用于商业用途。

## 直接使用

1. 双击 `dist\ClawdPet.exe`。
2. 双击 Clawd，就会打开桌面版 Claude。
3. （进阶）右键 → 💻 進階：終端機版 Claude Code，可以在指定的项目文件夹里，用终端打开命令行版 Claude Code。

exe 可以复制到任何地方（例如 `D:\Apps\ClawdPet.exe`）。搬动之后，在右键菜单重新勾一次「开机自动启动」即可。

### 加到 Steam

Steam → 左下角「添加游戏」→「添加非 Steam 游戏」→ 选 `ClawdPet.exe`。
如果 Steam 界面（Shift+Tab）造成闪烁，在该游戏的「属性」里关掉「在游戏中启用 Steam 界面」。

## 开发环境

需要 Python 3.13（已用 winget 安装）。

```powershell
# 第一次：建立虚拟环境并安装依赖
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 运行（pythonw 不会出现黑色控制台窗口）
.\.venv\Scripts\pythonw.exe main.py

# 想看报错信息时用 python
.\.venv\Scripts\python.exe main.py
```

## 打包成 exe

```powershell
.\build.ps1
```

会输出两个文件：
- `dist\ClawdPet.exe`：单一文件，约 24MB，不需要另外安装 Python。打包设置在 `ClawdPet.spec`，里面会拿掉用不到的组件来瘦身，比如软件 OpenGL、加密库、多余的 Qt 插件。
- `dist\ClawdPet-Setup-<版本>.exe`：安装包，需要 Inno Setup 6（`winget install JRSoftware.InnoSetup`）。

脚本会先关掉正在运行的 ClawdPet 再覆盖。要更新版本号，改 `installer\ClawdPet.iss` 里的 `AppVersion`。

> PyInstaller 打包的 exe 偶尔会被杀毒软件误报。遇到的话，把 `dist` 文件夹加入白名单即可。

## 文件结构

```
main.py                 程序入口；只允许运行一只（再开一次会让原来那只跳出来打招呼）
pet/
  window.py             主窗口：绘制、鼠标（单击/双击/拖动）、右键菜单
  animator.py           动画状态机：浮动、张望、眨眼、跳、压扁、摇晃、被拎起、睡觉
  sprites.py            读取素材，按整数倍最近邻放大（像素清晰），支持自定义单张图片
  bubble.py             对话气泡
  phrases.py            台词读取（改完存档立即生效）
services/
  launcher.py           打开终端运行 claude
  autostart.py          开机自启（写入当前用户的注册表启动项，不需要管理员权限）
  settings.py           设置文件
  paths.py              路径（开发模式 / exe 模式通用）
tools/make_sprites.py   用程序画出所有动作的素材
assets/
  sprites/*.png         8 个动作帧（40×38 原始像素）
  phrases.txt           默认台词
  icon.ico / icon.png   图标
build.ps1               一键打包
```

## 自定义

- **台词**：右键 → 💬 說話 → 編輯台詞…（实际文件：`%APPDATA%\ClawdPet\phrases.txt`）。每行一句，存档后立即生效。
- **大小**：右键 → 📏 大小，有小、中、大、特大四档（螃蟹宽约 96 / 128 / 160 / 192px）。会依屏幕缩放比例自动换算，并保持整数倍放大，所以不会模糊。
- **造型 / 动作素材**：改 `tools\make_sprites.py`（以「格」为单位画矩形），再执行 `.\build.ps1` 就会重新生成素材并打包。
- **用自己的单张图片**：把透明背景的 PNG 放到 `assets\clawd.png`（打包版放在 exe 旁边的 `assets\` 里），然后右键 → 🎨 造型 → 自訂圖片。如果是已经放大过的像素图，程序会自动还原成原始像素。单张图片模式下，所有动作都靠变换实现。
- **设置文件**：`%APPDATA%\ClawdPet\settings.json`（位置、大小、项目文件夹等）。删掉它就会恢复默认。

## 技术说明

- **Python + PySide6 (Qt 6)**：透明无边框置顶窗口、鼠标穿透、高 DPI 都由 Qt 原生支持，代码好改。
- **像素清晰**：素材按「屏幕实际像素」的整数倍最近邻放大，绘制位置也对齐到实际像素。
- **动画**：一个计时器在动作中跑 60fps、待机时 30fps，每帧由 `animator.py` 算出要显示哪一帧，以及位移、缩放、旋转。
- **启动 Claude**：PowerShell 命令用 `-EncodedCommand` 传递，路径里有空格、引号也不会出错。
