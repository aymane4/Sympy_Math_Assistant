import tkinter as tk
from tkinter import messagebox, ttk
import keyboard
import PIL.ImageGrab, PIL.Image, PIL.ImageTk
import threading
import os
import ctypes
import sys
from dotenv import load_dotenv

# Math & Visualization
import sympy
from sympy import sympify, symbols, expand, factor, solve, latex, diff, integrate
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

# Lazy Load Placeholders
genai = None
LatexOCR = None
latex2sympy = None

# --- CONFIG & DPI FIX ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

# --- COLORS & THEME ---
THEME = {
    "bg": "#1e1e1e",           # Dark Background
    "fg": "#dfe6e9",           # Light Text
    "accent": "#00cec9",       # Cyan Accent
    "panel": "#2d3436",        # Darker Panel
    "btn_online": "#0984e3",   # Blue
    "btn_offline": "#d63031",  # Red
    "btn_action": "#6c5ce7",   # Purple
    "btn_exit": "#636e72"      # Grey
}

# --- THE MASTER CONTROLLER ---
class AppLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SymPy Math Assistant")
        self.root.geometry("600x500")
        self.root.configure(bg=THEME["bg"])
        self.root.resizable(False, False)
        
        load_dotenv()
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.snipper = None
        
        self.setup_ui()
        self.root.mainloop()

    def setup_ui(self):
        tk.Label(self.root, text="MATH LENS", font=("Segoe UI", 28, "bold"), 
                 bg=THEME["bg"], fg=THEME["accent"]).pack(pady=(50, 5))
        
        tk.Label(self.root, text="AI-Powered Symbolic Solver", font=("Segoe UI", 12), 
                 bg=THEME["bg"], fg="#b2bec3").pack(pady=(0, 30))

        btn_frame = tk.Frame(self.root, bg=THEME["bg"])
        btn_frame.pack(pady=20)

        self.create_btn(btn_frame, "🌐 Online Mode\n(Gemini 2.5)", THEME["btn_online"], self.start_online)
        self.create_btn(btn_frame, "✈️ Offline Mode\n(Local Pix2Tex)", THEME["btn_offline"], self.start_offline)

        tk.Button(self.root, text="EXIT APP", font=("Segoe UI", 10, "bold"),
                  bg=THEME["btn_exit"], fg="white", width=20, relief="flat", cursor="hand2",
                  command=self.exit_app).pack(side="bottom", pady=30)
        
        self.status_lbl = tk.Label(self.root, text="Select a mode to begin", bg=THEME["bg"], fg="gray")
        self.status_lbl.pack(side="bottom", pady=5)

    def create_btn(self, parent, text, color, cmd):
        btn = tk.Button(parent, text=text, font=("Segoe UI", 12, "bold"),
                        bg=color, fg="white", width=18, height=3, relief="flat", 
                        cursor="hand2", command=cmd)
        btn.pack(side="left", padx=15)

    def start_online(self):
        if not self.api_key:
            messagebox.showerror("Error", "GEMINI_API_KEY missing from .env file!")
            return
        self.status_lbl.config(text="Initializing Cloud AI...", fg=THEME["accent"])
        self.root.update()
        try:
            global genai
            from google import genai
            self.launch_snipper("ONLINE")
        except Exception as e:
            messagebox.showerror("Error", f"Online Init Failed:\n{e}")

    def start_offline(self):
        self.status_lbl.config(text="Loading Neural Network...", fg=THEME["btn_offline"])
        self.root.update()
        try:
            global LatexOCR, latex2sympy
            from pix2tex.cli import LatexOCR
            from latex2sympy2 import latex2sympy
            self.launch_snipper("OFFLINE")
        except ImportError:
            messagebox.showerror("Error", "Run: pip install pix2tex latex2sympy2 torch")

    def launch_snipper(self, mode):
        self.root.withdraw()
        if self.snipper: self.snipper.stop_listening()
        self.snipper = MathSnipper(self.root, mode, self.api_key)

    def exit_app(self):
        if self.snipper: self.snipper.stop_listening()
        self.root.destroy()
        sys.exit()


# --- THE WORKER LOGIC ---
class MathSnipper:
    def __init__(self, master_root, mode, api_key):
        self.master = master_root
        self.mode = mode
        self.api_key = api_key
        self.model = None
        self.client = None
        
        if mode == "ONLINE":
            self.client = genai.Client(api_key=api_key)
        else:
            self.model = LatexOCR()

        self.hotkey = 'shift+alt+q'
        keyboard.add_hotkey(self.hotkey, self.start_snip)
        print(f"[{mode}] Listening on {self.hotkey}...")
        self.is_snipping = False

    def stop_listening(self):
        try: keyboard.remove_hotkey(self.hotkey)
        except: pass

    def start_snip(self):
        if self.is_snipping: return
        self.is_snipping = True
        
        self.snip_win = tk.Toplevel()
        self.snip_win.attributes('-fullscreen', True, '-alpha', 0.3, '-topmost', True)
        self.snip_win.config(cursor="cross")
        
        self.canvas = tk.Canvas(self.snip_win, cursor="cross", bg="black")
        self.canvas.pack(fill="both", expand=True)
        
        self.start_x = 0; self.start_y = 0; self.rect = None
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.snip_win.update()

    def on_press(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline=THEME["accent"], width=2)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        self.snip_win.destroy()
        self.is_snipping = False
        
        if (x2 - x1) < 10 or (y2 - y1) < 10: return

        try:
            root_w = self.master.winfo_screenwidth()
            full = PIL.ImageGrab.grab(all_screens=True)
            scale = full.size[0] / root_w
            bbox = (int(x1 * scale), int(y1 * scale), int(x2 * scale), int(y2 * scale))
            img = full.crop(bbox)
            self.process_image(img)
        except Exception as e:
            print(e)

    # --- THIS IS THE FIXED FUNCTION ---
    def process_image(self, img):
        def worker():
            try:
                math_str = ""
                if self.mode == "ONLINE":
                    # 1. Ask Gemini
                    prompt = "OCR this math image into a raw Python SymPy string (use X and I). Do NOT write 'y='."
                    res = self.client.models.generate_content(model="gemini-2.5-flash-lite", contents=[prompt, img])
                    
                    # 2. Cleanup
                    math_str = res.text.replace("```python", "").replace("```", "").replace("`", "").strip()
                    
                    # 3. FIX: Remove "y =" or "f(x) =" if Gemini hallucinated it
                    if "=" in math_str:
                        math_str = math_str.split("=")[-1].strip()
                        
                    # 4. FIX: Ensure exponents use ** not ^
                    math_str = math_str.replace("^", "**")

                    expr = sympify(math_str)
                else:
                    latex_str = self.model(img)
                    expr = latex2sympy(latex_str)
                
                self.master.after(0, lambda: MathDashboard(self.master, img, expr, self.mode))
            except Exception as e:
                print(e)
                self.master.after(0, lambda: messagebox.showerror("Error", f"Failed: {e}"))
        
        threading.Thread(target=worker, daemon=True).start()


# --- THE MODERN DASHBOARD ---
class MathDashboard:
    def __init__(self, master_root, img, expr, mode):
        self.root = tk.Toplevel(master_root)
        self.root.title(f"Math Lens - {mode}")
        self.root.geometry("1100x650")
        self.root.configure(bg=THEME["bg"])
        self.root.state('zoomed')
        
        self.expr = expr
        self.master_root = master_root

        top_bar = tk.Frame(self.root, bg=THEME["panel"], height=50)
        top_bar.pack(fill="x")
        tk.Label(top_bar, text="Result Analysis", bg=THEME["panel"], fg="white", font=("Segoe UI", 12, "bold")).pack(side="left", padx=20, pady=10)
        
        tk.Button(top_bar, text="⬅ Back to Menu", bg=THEME["btn_exit"], fg="white", relief="flat",
                  command=self.back_to_menu).pack(side="right", padx=10, pady=5)

        content = tk.Frame(self.root, bg=THEME["bg"])
        content.pack(fill="both", expand=True, padx=20, pady=20)

        left_frame = tk.Frame(content, bg=THEME["bg"], width=300)
        left_frame.pack(side="left", fill="y", padx=(0, 20))
        
        img_disp = img.copy()
        img_disp.thumbnail((300, 300))
        self.photo = PIL.ImageTk.PhotoImage(img_disp)
        tk.Label(left_frame, text="Captured Input", bg=THEME["bg"], fg="gray").pack(anchor="w")
        tk.Label(left_frame, image=self.photo, bg="black", bd=2, relief="solid").pack(pady=5)

        right_frame = tk.Frame(content, bg=THEME["bg"])
        right_frame.pack(side="right", fill="both", expand=True)

        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(8, 3))
        self.fig.patch.set_facecolor(THEME["panel"])
        self.ax.set_facecolor(THEME["panel"])
        self.canvas = FigureCanvasTkAgg(self.fig, master=right_frame)
        self.canvas.get_tk_widget().pack(fill="x", pady=(0, 20))
        self.render_latex(expr, "Detected Expression")

        self.txt_out = tk.Text(right_frame, height=8, bg=THEME["panel"], fg=THEME["fg"], 
                               font=("Consolas", 12), relief="flat", insertbackground="white")
        self.txt_out.pack(fill="both", expand=True)

        btn_frame = tk.Frame(self.root, bg=THEME["bg"])
        btn_frame.pack(fill="x", padx=20, pady=20)

        ops = [("EXPAND", expand), ("FACTOR", factor), ("SOLVE", solve), ("DERIVATIVE", diff), ("INTEGRATE", integrate)]
        for name, func in ops:
            tk.Button(btn_frame, text=name, bg=THEME["panel"], fg="white", font=("Segoe UI", 10),
                      relief="flat", height=2, width=15, command=lambda f=func, n=name: self.run_op(f, n)
                      ).pack(side="left", padx=5)

        tk.Button(btn_frame, text="GRAPH", bg=THEME["accent"], fg="black", font=("Segoe UI", 10, "bold"),
                  relief="flat", height=2, width=15, command=self.do_graph).pack(side="left", padx=5)

    def render_latex(self, expr, title):
        self.ax.clear()
        self.ax.axis("off")
        self.ax.text(0.5, 0.5, f"${latex(expr)}$", ha='center', va='center', fontsize=20, color="white")
        self.ax.set_title(title, fontsize=10, color=THEME["accent"])
        self.canvas.draw()

    def run_op(self, func, name):
        try:
            if func in [solve, diff, integrate]:
                syms = self.expr.free_symbols
                var = list(syms)[0] if syms else symbols('x')
                res = func(self.expr, var)
            else: res = func(self.expr)
            self.render_latex(res, name)
            self.txt_out.delete("1.0", tk.END); self.txt_out.insert("1.0", str(res))
        except Exception as e: messagebox.showerror("Math Error", str(e))

    def do_graph(self):
        try: sympy.plot(self.expr, show=True)
        except: messagebox.showerror("Error", "Cannot graph.")

    def back_to_menu(self):
        self.root.destroy()
        self.master_root.deiconify()

if __name__ == "__main__":
    AppLauncher()