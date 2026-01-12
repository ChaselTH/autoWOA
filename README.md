# autoWOA

macOS 上的自动化脚本，结合 `cliclick` 与 Vision OCR 执行点击流程，并用 OCR 结果做“gate”判断。

## 功能概览

- 使用 `cliclick` 执行点击、拖拽等操作。
- 调用 macOS Vision OCR 识别 UI 中的数字/比例信息。
- 通过 OCR 结果控制流程是否继续（gate 逻辑）。
- 支持全局 ESC 停止。

## 运行环境

- macOS（需要系统 Vision 框架）。
- Python 3.8+。
- 需要安装：
  - [`cliclick`](https://github.com/BlueM/cliclick)
  - Python 依赖：`pip install pillow pynput pyobjc`

> 注意：脚本会控制鼠标，请在安全环境下运行并确保窗口在前台。

## 快速开始

1. 安装依赖：

   ```bash
   brew install cliclick
   pip install pillow pynput pyobjc
   ```

2. 打开并校准坐标：

   - 主要配置在 `main.py` 顶部“你只需要改这一段”区域。
   - 使用 `cliclick p` 获取坐标（单位为 points）。
   - 如需多屏幕支持，保持 `ALL_SCREENS = True`。

3. 运行主脚本：

   ```bash
   python3 main.py
   ```

4. 停止脚本：

   - 在运行过程中按 `Esc` 可立即停止。

## Gate 逻辑说明

- OCR 读取关键区域的左/右数值。
- 当 `right - left > GATE_DELTA` 时才会执行后续操作。
- 相关参数在 `main.py`：
  - `GATE_DELTA`
  - `OCR_*`（缩放、对比度、锐化等）

## OCR 调试脚本

`OCR.py` 是用于调试 Vision OCR 的独立脚本：

- 会截取指定 ROI 并保存 `full.png / roi_raw.png / roi_proc.png`。
- 输出识别结果，便于调整 OCR 参数。

运行方式：

```bash
python3 OCR.py
```

在 `OCR.py` 顶部配置 `ROI_TL / ROI_BR` 与 `SCALE`。

## 常见问题

- **识别不稳定**：尝试调整 `OCR_SCALE / OCR_CONTRAST / OCR_SHARPNESS`。
- **坐标偏移**：确认 `COORD_SCALE` 与 `SCALE` 是否与显示器缩放一致。
- **窗口没响应**：确保目标窗口处于前台，并且系统辅助功能权限已开启。

## 文件说明

- `main.py`：主自动化流程。
- `OCR.py`：OCR 调试工具。
