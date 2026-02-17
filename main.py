import tkinter as tk
from tkinter import messagebox
import keyboard
import PIL.ImageGrab, PIL.Image, PIL.ImageTk
from google import genai
import sympy
from sympy import sympify, symbols, expand, factor, solve, latex, diff, integrate
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import threading
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_ID = "gemini-2.5-flash-lite" 

class MathSnipper:
    def __init__(self):
        # 1. Setup API
        if not API_KEY:
            # Fallback (Delete this if you have .env working)
            self.client = genai.Client(api_key="YOUR_KEY_HERE")
        else:
            self.client = genai.Client(api_key=API_KEY)
            
        self.current_expr = None
        self.X = symbols('X')
        
        self.root = tk.Tk()
        self.root.withdraw() 
        self.is_snipping = False
        
        print(f"[{MODEL_ID}] Math Lens Active.")
        print("Waiting for shortcut: Shift + Alt + Q")

    def start_snip(self):
        if self.is_snipping: return
        self.is_snipping = True
        
        self.snip_win = tk.Toplevel(self.root)
        self.snip_win.attributes('-fullscreen', True)
        self.snip_win.attributes('-alpha', 0.3)
        self.snip_win.attributes("-topmost", True)
        self.snip_win.config(cursor="cross")
        
        self.canvas = tk.Canvas(self.snip_win, cursor="cross", bg="black")
        self.canvas.pack(fill="both", expand=True)
        
        self.start_x = 0
        self.start_y = 0
        self.rect = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.snip_win.update()

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='cyan', width=2)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        # 1. Coordinates
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        
        self.snip_win.destroy()
        self.is_snipping = False
        
        if (x2 - x1) < 10 or (y2 - y1) < 10: return

        # 2. DPI FIX (Manual Calculation)
        try:
            root_w = self.root.winfo_screenwidth()
            full_screen = PIL.ImageGrab.grab(all_screens=True)
            real_w, _ = full_screen.size
            scale = real_w / root_w
            
            # Apply Scale
            bbox = (int(x1 * scale), int(y1 * scale), int(x2 * scale), int(y2 * scale))
            img = full_screen.crop(bbox)
            self.process_capture(img)
        except Exception as e:
            print(f"Screenshot Error: {e}")

    def sanitize_math(self, raw_str):
        """Cleans up the AI output to prevent SymPy crashes."""
        # Remove Code Blocks
        clean = raw_str.replace("```python", "").replace("```", "").replace("`", "").strip()
        
        # If AI returns "z = ...", take only the right side
        if "=" in clean:
            clean = clean.split("=")[-1].strip()
            
        # Fix common AI notation mistakes
        clean = clean.replace("^", "**") # Python uses ** for power
        clean = clean.replace("i", "I")  # SymPy needs capital I for imaginary
        
        return clean

    def process_capture(self, img):
        def worker():
            try:
                # Prompt optimized for Python Syntax
                prompt = (
                    "OCR this math. Output ONLY the raw Python math string. "
                    "Use 'X' for variables and 'I' for imaginary numbers. "
                    "Do NOT write 'z =' or 'y =', just the expression."
                    "On a new line, suggest one action: SOLVE, EXPAND, FACTOR."
                )
                
                response = self.client.models.generate_content(
                    model=MODEL_ID,
                    contents=[prompt, img]
                )
                
                text = response.text.strip()
                lines = text.split('\n')
                
                # SANITIZE THE INPUT
                math_str = self.sanitize_math(lines[0])
                suggestion = lines[-1].strip().upper() if len(lines) > 1 else "ANALYZE"
                
                print(f"Debug - Cleaned Math: {math_str}")
                
                self.current_expr = sympify(math_str)
                self.root.after(0, lambda: self.show_dashboard(img, suggestion))
                
            except Exception as e:
                print(f"Error: {e}")
                # Fixed the NameError bug here
                err_msg = str(e)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {err_msg}"))

        threading.Thread(target=worker, daemon=True).start()

    def show_dashboard(self, img, suggestion):
        dash = tk.Toplevel(self.root)
        dash.title("Math Lens Dashboard")
        dash.geometry("1000x600")
        
        # Left Panel
        left_frame = tk.Frame(dash, width=300, bg="#f0f0f0")
        left_frame.pack(side="left", fill="y", padx=10, pady=10)
        
        img_disp = img.copy()
        img_disp.thumbnail((280, 280))
        photo = PIL.ImageTk.PhotoImage(img_disp)
        lbl_img = tk.Label(left_frame, image=photo, bg="#f0f0f0")
        lbl_img.image = photo 
        lbl_img.pack(pady=20)
        
        tk.Label(left_frame, text="AI Suggestion:", bg="#f0f0f0").pack()
        tk.Label(left_frame, text=suggestion, bg="lightgreen", font=("Arial", 14, "bold"), width=15).pack(pady=5)

        # Right Panel
        right_frame = tk.Frame(dash, bg="white")
        right_frame.pack(side="right", fill="both", expand=True)
        
        self.fig, self.ax = plt.subplots(figsize=(6, 3))
        self.canvas_widget = FigureCanvasTkAgg(self.fig, master=right_frame)
        self.canvas_widget.get_tk_widget().pack(fill="x", padx=10, pady=10)
        self.render_latex(self.current_expr, "Detected Expression")
        
        btn_frame = tk.Frame(right_frame, bg="white")
        btn_frame.pack(pady=10)
        
        def run_op(func, name):
            try:
                if func == solve: res = solve(self.current_expr, self.X)
                elif func == diff: res = diff(self.current_expr, self.X)
                else: res = func(self.current_expr)
                
                self.render_latex(res, f"Result: {name}")
                self.txt_out.delete("1.0", tk.END)
                self.txt_out.insert("1.0", str(res))
            except Exception as e: messagebox.showerror("Error", str(e))

        def do_graph():
            try: sympy.plot(self.current_expr, show=True)
            except: messagebox.showerror("Graph Error", "Cannot graph this expression.")

        ops = [("EXPAND", expand), ("FACTOR", factor), ("SOLVE (X=0)", solve), ("DERIVATIVE", diff), ("INTEGRATE", integrate)]
        for name, func in ops:
            tk.Button(btn_frame, text=name, command=lambda f=func, n=name: run_op(f, n), bg="#e1e1e1").pack(side="left", padx=5)
        tk.Button(btn_frame, text="GRAPH", command=do_graph, bg="orange").pack(side="left", padx=5)

        self.txt_out = tk.Text(right_frame, height=8, font=("Consolas", 11))
        self.txt_out.pack(fill="both", expand=True, padx=20, pady=20)

    def render_latex(self, expr, title):
        self.ax.clear()
        self.ax.axis("off")
        self.ax.text(0.5, 0.5, f"${latex(expr)}$", ha='center', va='center', fontsize=20)
        self.ax.set_title(title, fontsize=10, color="gray")
        self.canvas_widget.draw()

if __name__ == "__main__":
    app = MathSnipper()
    keyboard.add_hotkey('shift+alt+q', app.start_snip)
    app.root.mainloop()