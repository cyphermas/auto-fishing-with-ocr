import time
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
import pyautogui
import pytesseract
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageGrab
import os
import win32gui
import win32ui
import win32con
import win32api

# ================= 配置区域 =================

# 默认 Tesseract OCR 路径
DEFAULT_TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# 触发关键词 (支持中文和英文)
KEYWORDS = ["splashes", "溅起水花","鸳起水花", "Bobber", "鱼漂","钓 鱼 钩 : 温 起 水 花"]

# 动作冷却时间 (秒)
RECAST_DELAY = 1.5

# 抛竿后忽略检测的时间 (秒)
COOLDOWN = 2.0

# ===========================================

class WindowSelector:
    def __init__(self, master, callback):
        self.master = master
        self.callback = callback
        self.top = tk.Toplevel(master)
        self.top.title("选择游戏窗口")
        self.top.geometry("400x300")
        
        tk.Label(self.top, text="请选择 Minecraft 游戏窗口:").pack(pady=5)
        
        frame_list = tk.Frame(self.top)
        frame_list.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.listbox = tk.Listbox(frame_list, selectmode=tk.SINGLE)
        self.listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = tk.Scrollbar(frame_list, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scrollbar.set)
        
        self.windows = []
        self.refresh_windows()
        
        frame_btn = tk.Frame(self.top)
        frame_btn.pack(fill="x", padx=5, pady=5)
        
        tk.Button(frame_btn, text="刷新列表", command=self.refresh_windows).pack(side="left")
        tk.Button(frame_btn, text="确定", command=self.confirm).pack(side="right")
        
    def refresh_windows(self):
        self.listbox.delete(0, tk.END)
        self.windows = []
        
        def enum_handler(hwnd, ctx):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    self.windows.append((hwnd, title))
        
        win32gui.EnumWindows(enum_handler, None)
        # 优先显示包含 Minecraft 的窗口
        self.windows.sort(key=lambda x: "Minecraft" not in x[1])
        
        for hwnd, title in self.windows:
            self.listbox.insert(tk.END, f"[{hwnd}] {title}")
            
    def confirm(self):
        selection = self.listbox.curselection()
        if selection:
            index = selection[0]
            hwnd, title = self.windows[index]
            self.callback(hwnd, title)
            self.top.destroy()

class RegionSelector:
    def __init__(self, master, callback):
        self.master = master
        self.callback = callback
        self.start_x = None
        self.start_y = None
        self.rect = None

        # 截取全屏用于显示
        self.img = ImageGrab.grab()
        self.tk_img = ImageTk.PhotoImage(self.img)

        self.top = tk.Toplevel(master)
        self.top.attributes('-fullscreen', True)
        self.top.attributes('-topmost', True)
        self.top.attributes('-alpha', 1.0)
        
        self.canvas = tk.Canvas(self.top, cursor="cross", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # 按 ESC 取消
        self.top.bind("<Escape>", lambda e: self.top.destroy())
        
        # 提示文字
        self.canvas.create_text(self.top.winfo_screenwidth()//2, 50, text="请按住鼠标左键拖动选择字幕区域 (按 ESC 取消)", fill="red", font=("Arial", 16, "bold"))

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=3)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        x1, y1 = self.start_x, self.start_y
        x2, y2 = event.x, event.y
        
        # 计算左上角和宽高
        left = min(x1, x2)
        top = min(y1, y2)
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        
        if width > 10 and height > 10:
            self.callback((left, top, width, height))
            self.top.destroy()
        else:
            # 如果选区太小，可能是误触，重置
            if self.rect:
                self.canvas.delete(self.rect)
                self.rect = None

class AutoFishApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Minecraft 自动钓鱼 (字幕识别版)")
        self.root.geometry("600x800")
        
        # 变量
        self.tesseract_path = tk.StringVar(value=DEFAULT_TESSERACT_CMD)
        self.region = (1500, 800, 400, 250) # 默认值
        self.running = False
        self.thread = None
        self.debug_mode = tk.BooleanVar(value=False)
        self.lang_var = tk.StringVar(value="chi_sim+eng")
        
        # 后台模式相关变量
        self.target_hwnd = None
        self.target_title = tk.StringVar(value="未选择窗口")
        self.background_mode = tk.BooleanVar(value=False)
        self.relative_region = None # 相对于窗口左上角的区域 (x, y, w, h)
        
        self.setup_ui()
        
    def setup_ui(self):
        # 1. Tesseract 设置
        frame_ocr = tk.LabelFrame(self.root, text="OCR 设置", padx=10, pady=10)
        frame_ocr.pack(fill="x", padx=10, pady=5)
        
        tk.Label(frame_ocr, text="Tesseract 路径:").pack(anchor="w")
        frame_path = tk.Frame(frame_ocr)
        frame_path.pack(fill="x")
        tk.Entry(frame_path, textvariable=self.tesseract_path).pack(side="left", fill="x", expand=True)
        tk.Button(frame_path, text="浏览...", command=self.browse_tesseract).pack(side="right", padx=5)

        # 1.5 语言设置
        frame_lang = tk.Frame(frame_ocr)
        frame_lang.pack(fill="x", pady=5)
        tk.Label(frame_lang, text="识别语言:").pack(side="left")
        tk.Radiobutton(frame_lang, text="中英文 (较慢)", variable=self.lang_var, value="chi_sim+eng").pack(side="left", padx=5)
        tk.Radiobutton(frame_lang, text="仅英文 (较快)", variable=self.lang_var, value="eng").pack(side="left", padx=5)
        
        # 2. 窗口与区域设置
        frame_target = tk.LabelFrame(self.root, text="目标设置", padx=10, pady=10)
        frame_target.pack(fill="x", padx=10, pady=5)
        
        # 窗口选择
        frame_win = tk.Frame(frame_target)
        frame_win.pack(fill="x", pady=2)
        tk.Label(frame_win, text="目标窗口:").pack(side="left")
        tk.Label(frame_win, textvariable=self.target_title, fg="blue").pack(side="left", padx=5)
        tk.Button(frame_win, text="选择窗口", command=self.select_window).pack(side="right")
        
        # 模式选择
        tk.Checkbutton(frame_target, text="启用后台模式 (窗口被遮挡也能运行)", variable=self.background_mode, command=self.on_mode_change).pack(anchor="w", pady=5)
        
        # 区域显示
        self.lbl_region_val = tk.Label(frame_target, text=f"当前屏幕区域: {self.region}", font=("Consolas", 10))
        self.lbl_region_val.pack(pady=5)
        
        tk.Button(frame_target, text="选取识别区域", command=self.select_region, bg="#e1f5fe").pack(fill="x")
        tk.Label(frame_target, text="注意: 选取区域时请确保游戏窗口可见", fg="gray", font=("Arial", 8)).pack()
        
        # 3. 控制按钮
        frame_ctrl = tk.Frame(self.root, padx=10, pady=10)
        frame_ctrl.pack(fill="x", padx=10, pady=5)
        
        self.btn_start = tk.Button(frame_ctrl, text="开始运行", command=self.start_fishing, bg="#c8e6c9", font=("Arial", 12, "bold"), height=2)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=5)
        
        self.btn_stop = tk.Button(frame_ctrl, text="停止", command=self.stop_fishing, bg="#ffcdd2", font=("Arial", 12, "bold"), height=2, state="disabled")
        self.btn_stop.pack(side="right", fill="x", expand=True, padx=5)
        
        # 4. 日志区域
        frame_log = tk.LabelFrame(self.root, text="运行日志", padx=10, pady=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(frame_log, state='disabled', height=10)
        self.log_area.pack(fill="both", expand=True)

        # 5. 调试区域
        frame_debug = tk.LabelFrame(self.root, text="调试预览", padx=10, pady=10)
        frame_debug.pack(fill="both", expand=True, padx=10, pady=5)
        
        tk.Checkbutton(frame_debug, text="开启调试模式 (显示二值化图像和所有识别文本)", variable=self.debug_mode).pack(anchor="w")
        
        self.lbl_preview = tk.Label(frame_debug, text="[图像预览区域]")
        self.lbl_preview.pack(pady=5)
        
        self.log("程序已启动。请配置 Tesseract 路径并选取字幕区域。")

    def browse_tesseract(self):
        filename = filedialog.askopenfilename(filetypes=[("Executable", "*.exe")])
        if filename:
            self.tesseract_path.set(filename)

    def select_window(self):
        WindowSelector(self.root, self.on_window_selected)
        
    def on_window_selected(self, hwnd, title):
        self.target_hwnd = hwnd
        self.target_title.set(title)
        self.log(f"已选择窗口: {title} ({hwnd})")
        # 切换到后台模式推荐
        self.background_mode.set(True)
        self.on_mode_change()

    def on_mode_change(self):
        if self.background_mode.get():
            if not self.target_hwnd:
                messagebox.showwarning("提示", "请先选择一个游戏窗口！")
                self.background_mode.set(False)
                return
            self.lbl_region_val.config(text=f"当前模式: 后台窗口 (区域将自动转换为相对坐标)")
        else:
            self.lbl_region_val.config(text=f"当前模式: 屏幕截图 (区域: {self.region})")

    def select_region(self):
        self.root.iconify() # 最小化主窗口
        # 延迟 200ms 等待窗口最小化动画完成，避免截取到主窗口
        self.root.after(200, lambda: RegionSelector(self.root, self.on_region_selected))
        
    def on_region_selected(self, region):
        self.region = region
        self.root.deiconify() # 恢复主窗口
        
        if self.target_hwnd:
            # 如果选择了窗口，计算相对坐标
            try:
                rect = win32gui.GetWindowRect(self.target_hwnd)
                win_x, win_y = rect[0], rect[1]
                # 相对坐标 = 屏幕坐标 - 窗口左上角坐标
                rel_x = region[0] - win_x
                rel_y = region[1] - win_y
                self.relative_region = (rel_x, rel_y, region[2], region[3])
                self.log(f"已更新相对区域: {self.relative_region}")
            except Exception as e:
                self.log(f"计算相对坐标失败: {e}")
        
        self.lbl_region_val.config(text=f"当前区域: {self.region}")
        self.log(f"区域已更新: {self.region}")

    def log(self, message):
        def _update():
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
        self.root.after(0, _update)

    def start_fishing(self):
        tess_cmd = self.tesseract_path.get()
        if not os.path.exists(tess_cmd):
            messagebox.showerror("错误", "找不到 Tesseract 执行文件，请检查路径！")
            return
            
        pytesseract.pytesseract.tesseract_cmd = tess_cmd
        
        if self.background_mode.get() and not self.target_hwnd:
            messagebox.showerror("错误", "后台模式需要先选择窗口！")
            return

        self.running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.log("正在启动监听线程...")
        if self.background_mode.get():
            self.log("后台模式已开启，你可以最小化游戏或遮挡它。")
        else:
            self.log("请切换回游戏，确保字幕已开启。")
        
        self.thread = threading.Thread(target=self.fishing_loop)
        self.thread.daemon = True
        self.thread.start()

    def stop_fishing(self):
        self.running = False
        self.log("正在停止...")
        self.btn_start.config(state="normal")
        self.btn_stop.config(state="disabled")

    def process_image(self, image):
        """图像预处理"""
        img_np = np.array(image)
        # 如果是 RGBA (win32 截图可能带 alpha)，转 RGB
        if img_np.shape[2] == 4:
            img_np = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
            
        gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        
        # Tesseract 更喜欢白底黑字，所以反转颜色，这通常能提高识别率
        thresh = cv2.bitwise_not(thresh)
        
        scale = 2
        width = int(thresh.shape[1] * scale)
        height = int(thresh.shape[0] * scale)
        dim = (width, height)
        # 使用最近邻插值 (INTER_NEAREST) 速度最快，对于二值图像效果通常也不错
        resized = cv2.resize(thresh, dim, interpolation=cv2.INTER_NEAREST)
        return resized

    def capture_window(self, hwnd, region):
        """
        使用 win32 API 截取指定窗口的指定区域
        region: (x, y, w, h) 相对于窗口左上角
        """
        try:
            # 获取窗口设备上下文
            wDC = win32gui.GetWindowDC(hwnd)
            dcObj = win32ui.CreateDCFromHandle(wDC)
            cDC = dcObj.CreateCompatibleDC()
            
            x, y, w, h = region
            
            # 创建位图
            dataBitMap = win32ui.CreateBitmap()
            dataBitMap.CreateCompatibleBitmap(dcObj, w, h)
            
            cDC.SelectObject(dataBitMap)
            
            # 截图 (BitBlt)
            # 注意：对于某些硬件加速窗口，如果被遮挡，BitBlt 可能会截取到黑色或遮挡物
            # PrintWindow 是另一种选择，但速度较慢且可能不兼容
            # 这里使用 BitBlt，它通常对 Minecraft 有效
            cDC.BitBlt((0, 0), (w, h), dcObj, (x, y), win32con.SRCCOPY)
            
            # 转换为 PIL Image
            bmpinfo = dataBitMap.GetInfo()
            bmpstr = dataBitMap.GetBitmapBits(True)
            
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1)
                
            # 清理资源
            win32gui.DeleteObject(dataBitMap.GetHandle())
            cDC.DeleteDC()
            dcObj.DeleteDC()
            win32gui.ReleaseDC(hwnd, wDC)
            
            return img
        except Exception as e:
            # self.log(f"截图失败: {e}") # 避免刷屏
            return None

    def send_click(self, hwnd):
        """发送后台右键点击"""
        # WM_RBUTTONDOWN = 0x0204
        # WM_RBUTTONUP = 0x0205
        # MK_RBUTTON = 0x0002
        try:
            win32api.PostMessage(hwnd, win32con.WM_RBUTTONDOWN, win32con.MK_RBUTTON, 0)
            time.sleep(0.1)
            win32api.PostMessage(hwnd, win32con.WM_RBUTTONUP, 0, 0)
        except Exception as e:
            self.log(f"点击失败: {e}")

    def fishing_loop(self):
        last_action_time = time.time()
        
        try:
            while self.running:
                # 检查冷却
                if time.time() - last_action_time < COOLDOWN:
                    time.sleep(0.1)
                    continue

                screenshot = None
                
                # 截图逻辑
                if self.background_mode.get() and self.target_hwnd:
                    if self.relative_region:
                        screenshot = self.capture_window(self.target_hwnd, self.relative_region)
                    else:
                        # 如果没有相对区域，尝试使用默认的右下角估算
                        try:
                            rect = win32gui.GetWindowRect(self.target_hwnd)
                            w = rect[2] - rect[0]
                            h = rect[3] - rect[1]
                            # 估算右下角
                            est_x = int(w * 0.7)
                            est_y = int(h * 0.7)
                            est_w = int(w * 0.25)
                            est_h = int(h * 0.2)
                            screenshot = self.capture_window(self.target_hwnd, (est_x, est_y, est_w, est_h))
                        except:
                            pass
                else:
                    # 屏幕截图模式
                    try:
                        screenshot = ImageGrab.grab(bbox=(
                            self.region[0], 
                            self.region[1], 
                            self.region[0] + self.region[2], 
                            self.region[1] + self.region[3]
                        ))
                    except Exception as e:
                        self.log(f"截图失败: {e}")

                if screenshot is None:
                    time.sleep(1)
                    continue

                # 处理与识别
                processed_img = self.process_image(screenshot)
                
                # 调试模式：更新预览图
                if self.debug_mode.get():
                    def _update_preview(img_np):
                        try:
                            img_pil = Image.fromarray(img_np)
                            # 缩放以适应界面
                            img_pil.thumbnail((400, 200))
                            img_tk = ImageTk.PhotoImage(img_pil)
                            self.lbl_preview.config(image=img_tk, text="")
                            self.lbl_preview.image = img_tk # 保持引用
                        except Exception as e:
                            print(f"Preview error: {e}")
                    
                    self.root.after(0, _update_preview, processed_img)

                try:
                    # 优化配置:
                    # --psm 6: 假设是一个统一的文本块 (比默认分析全页要快)
                    # --oem 3: 默认 OCR 引擎模式
                    custom_config = r'--psm 6'
                    selected_lang = self.lang_var.get()
                    
                    text = pytesseract.image_to_string(processed_img, lang=selected_lang, config=custom_config)
                except pytesseract.TesseractError:
                    text = pytesseract.image_to_string(processed_img, lang='eng', config=r'--psm 6')
                except Exception as e:
                    # 可能是路径错误等
                    self.log(f"OCR 错误: {e}")
                    self.running = False
                    break

                # 调试模式：打印所有识别文本
                if self.debug_mode.get():
                    clean_text = text.replace('\n', ' ').strip()
                    if clean_text:
                        self.log(f"[调试] 识别结果: {clean_text}")

                # 匹配
                detected = False
                for keyword in KEYWORDS:
                    if keyword in text:
                        detected = True
                        self.log(f"检测到关键词: {keyword}")
                        # 显示识别到的完整文本，方便确认
                        clean_text = text.replace('\n', ' ').strip()
                        if clean_text:
                            self.log(f"识别文本: {clean_text}")
                        break
                
                if detected:
                    self.log("收杆！")
                    
                    if self.background_mode.get() and self.target_hwnd:
                        self.send_click(self.target_hwnd)
                    else:
                        pyautogui.click(button='right')
                    
                    self.log(f"等待 {RECAST_DELAY} 秒后重新抛竿...")
                    time.sleep(RECAST_DELAY)
                    
                    self.log("抛竿！")
                    if self.background_mode.get() and self.target_hwnd:
                        self.send_click(self.target_hwnd)
                    else:
                        pyautogui.click(button='right')
                    
                    last_action_time = time.time()
                
                time.sleep(0.1)
                
        except Exception as e:
            self.log(f"运行出错: {e}")
        finally:
            self.running = False
            # 在主线程更新UI
            self.root.after(0, lambda: self.btn_start.config(state="normal"))
            self.root.after(0, lambda: self.btn_stop.config(state="disabled"))
            self.log("监听已停止。")

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoFishApp(root)
    root.mainloop()
