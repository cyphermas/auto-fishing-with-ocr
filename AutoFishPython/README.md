# Minecraft 自动钓鱼脚本 (Python 字幕识别版)

这是一个使用 Python 编写的外部脚本，通过识别屏幕右下角的 Minecraft 字幕来实现自动钓鱼。

## 前置要求

1.  **Python 3.x**: 确保已安装 Python。
2.  **Tesseract OCR**: 这是一个开源的 OCR 引擎，必须安装它才能识别文字。
    *   下载地址: [https://github.com/UB-Mannheim/tesseract/wiki](https://github.com/UB-Mannheim/tesseract/wiki)
    *   安装时，建议勾选 "Additional language data" 中的 **Chinese (Simplified)** 以支持中文识别。
    *   **重要**: 安装完成后，请记下安装路径（例如 `C:\Program Files\Tesseract-OCR\tesseract.exe`），你需要将其填入 `autofish.py` 脚本中。

## 安装依赖库

在当前目录下打开终端，运行：

```bash
pip install -r requirements.txt
```

## 配置脚本

打开 `autofish.py` 文件，根据你的实际情况修改以下变量：

1.  `pytesseract.pytesseract.tesseract_cmd`: 修改为你安装 Tesseract OCR 的实际路径。
2.  `REGION`: 屏幕截图区域 `(左, 上, 宽, 高)`。
    *   你需要根据你的屏幕分辨率调整这个数值，确保它覆盖了 Minecraft 右下角显示字幕的区域。
    *   可以使用截图工具（如 QQ 截图、Snipaste）来查看坐标。

## 游戏设置

1.  进入 Minecraft。
2.  打开 **选项 (Options)** -> **音乐和声音 (Music & Sounds)**。
3.  将 **显示字幕 (Show Subtitles)** 设置为 **开启 (ON)**。
4.  确保游戏语言与脚本中的关键词匹配（脚本默认支持中文“鱼漂溅起水花”和英文“Fishing Bobber splashes”）。

## 运行

1.  在终端运行脚本：
    ```bash
    python autofish.py
    ```
2.  脚本启动后有 3 秒倒计时，请迅速切换回 Minecraft 游戏窗口并手持鱼竿。
3.  脚本会自动识别字幕并进行收放杆操作。
4.  按 `Ctrl + C` 在终端中停止脚本。
