import time
import threading
import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import pyautogui
import pytesseract
import cv2
import numpy as np
from PIL import Image, ImageTk, ImageGrab
import os

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
        self.top.attributes('-alpha', 0.3) # 半透明，方便看到后面，但为了看清截图，最好是不透明然后画框
        # 实际上，为了模拟“截图选区”，我们应该显示静态截图
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
        self.root.geometry("600x700")
        
        # 变量
        self.tesseract_path = tk.StringVar(value=DEFAULT_TESSERACT_CMD)
        self.region = (1500, 800, 400, 250) # 默认值
        self.running = False
        self.thread = None
        self.debug_mode = tk.BooleanVar(value=False)
        self.lang_var = tk.StringVar(value="chi_sim+eng")
        
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
        
        # 2. 区域设置
        frame_region = tk.LabelFrame(self.root, text="识别区域", padx=10, pady=10)
        frame_region.pack(fill="x", padx=10, pady=5)
        
        self.lbl_region_val = tk.Label(frame_region, text=f"当前区域: {self.region}", font=("Consolas", 10))
        self.lbl_region_val.pack(pady=5)
        tk.Button(frame_region, text="选取屏幕区域", command=self.select_region, bg="#e1f5fe").pack(fill="x")
        
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

    def select_region(self):
        self.root.iconify() # 最小化主窗口
        # 延迟 200ms 等待窗口最小化动画完成，避免截取到主窗口
        self.root.after(200, lambda: RegionSelector(self.root, self.on_region_selected))
        
    def on_region_selected(self, region):
        self.region = region
        self.lbl_region_val.config(text=f"当前区域: {self.region}")
        self.root.deiconify() # 恢复主窗口
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
        
        self.running = True
        self.btn_start.config(state="disabled")
        self.btn_stop.config(state="normal")
        self.log("正在启动监听线程...")
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

    def fishing_loop(self):
        last_action_time = time.time()
        
        try:
            while self.running:
                # 检查冷却
                if time.time() - last_action_time < COOLDOWN:
                    time.sleep(0.1)
                    continue

                # 截图
                try:
                    screenshot = ImageGrab.grab(bbox=(
                        self.region[0], 
                        self.region[1], 
                        self.region[0] + self.region[2], 
                        self.region[1] + self.region[3]
                    ))
                except Exception as e:
                    self.log(f"截图失败: {e}")
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
                    pyautogui.click(button='right')
                    
                    self.log(f"等待 {RECAST_DELAY} 秒后重新抛竿...")
                    time.sleep(RECAST_DELAY)
                    
                    self.log("抛竿！")
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
