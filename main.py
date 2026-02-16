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
import ctypes
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# --- CONFIGURATION ---
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_ID = "gemini-2.5-flash-lite" 

if not API_KEY:
    raise ValueError("API Key not found! Make sure you have a .env file with GEMINI_API_KEY inside.")



class MathSnipper:
    def __init__(self):
        self.client = genai.Client(api_key=API_KEY)
        self.current_expr = None
        self.X = symbols('X')
        
        # Hidden root window
        self.root = tk.Tk()
        self.root.withdraw() 
        self.is_snipping = False
        
        print(f"[{MODEL_ID}] Math Lens Active.")
        print("Waiting for shortcut: Shift + Alt + Q")

    def start_snip(self):
        if self.is_snipping: return
        self.is_snipping = True
        
        # Create a full-screen transparent window
        self.snip_win = tk.Toplevel(self.root)
        self.snip_win.attributes('-fullscreen', True)
        self.snip_win.attributes('-alpha', 0.3)
        self.snip_win.attributes("-topmost", True)
        self.snip_win.config(cursor="cross")
        
        # Grey overlay
        self.canvas = tk.Canvas(self.snip_win, cursor="cross", bg="black")
        self.canvas.pack(fill="both", expand=True)
        
        self.start_x = 0
        self.start_y = 0
        self.rect = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, 1, 1, outline='cyan', width=2)

    def on_drag(self, event):
        self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        # Get coordinates
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)
        
        self.snip_win.destroy()
        self.is_snipping = False
        
        # Ignore accidental tiny clicks
        if (x2 - x1) < 10 or (y2 - y1) < 10: return

        # Capture Screenshot (Now accurate thanks to DPI fix)
        # We assume primary monitor. If multi-monitor behaves oddly, use 'all_screens=True'
        img = PIL.ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
        self.process_capture(img)

    def process_capture(self, img):
        """Sends image to Gemini Flash-Lite"""
        def worker():
            try:
                # 1. Ask Gemini for Math AND a suggestion
                prompt = (
                    "OCR this math image into a raw SymPy string (use X and I). "
                    "Then, on a new line, write one word suggesting the best action: "
                    "SOLVE, EXPAND, FACTOR, or GRAPH."
                )
                
                response = self.client.models.generate_content(
                    model=MODEL_ID,
                    contents=[prompt, img]
                )
                
                text = response.text.strip()
                lines = text.split('\n')
                
                # Parse output
                math_str = lines[0].replace("```python", "").replace("```", "").strip()
                # Clean any lingering markdown code block syntax
                math_str = math_str.replace("`", "")
                
                suggestion = lines[-1].strip().upper() if len(lines) > 1 else "ANALYZE"
                
                # Convert to SymPy
                self.current_expr = sympify(math_str)
                
                # Open UI in main thread
                self.root.after(0, lambda: self.show_dashboard(img, suggestion))
                
            except Exception as e:
                print(e)
                self.root.after(0, lambda: messagebox.showerror("Error", f"Failed: {e}"))

        threading.Thread(target=worker, daemon=True).start()

    def show_dashboard(self, img, suggestion):
        dash = tk.Toplevel(self.root)
        dash.title("Math Lens Dashboard")
        dash.geometry("1000x600")
        
        # --- LEFT: Image & Suggestions ---
        left_frame = tk.Frame(dash, width=300, bg="#f0f0f0")
        left_frame.pack(side="left", fill="y", padx=10, pady=10)
        
        # Show Snip (Resize for display)
        img_disp = img.copy()
        img_disp.thumbnail((280, 280))
        photo = PIL.ImageTk.PhotoImage(img_disp)
        lbl_img = tk.Label(left_frame, image=photo, bg="#f0f0f0")
        lbl_img.image = photo # Keep reference
        lbl_img.pack(pady=20)
        
        tk.Label(left_frame, text="AI Suggestion:", bg="#f0f0f0", font=("Arial", 10)).pack()
        tk.Label(left_frame, text=suggestion, bg="lightgreen", font=("Arial", 14, "bold"), width=15).pack(pady=5)

        # --- RIGHT: Math Board ---
        right_frame = tk.Frame(dash, bg="white")
        right_frame.pack(side="right", fill="both", expand=True)
        
        # Matplotlib Figure for LaTeX
        self.fig, self.ax = plt.subplots(figsize=(6, 3))
        self.canvas_widget = FigureCanvasTkAgg(self.fig, master=right_frame)
        self.canvas_widget.get_tk_widget().pack(fill="x", padx=10, pady=10)
        self.render_latex(self.current_expr, "Detected Expression")
        
        # Buttons
        btn_frame = tk.Frame(right_frame, bg="white")
        btn_frame.pack(pady=10)
        
        # Define Operations
        def run_op(func, name):
            try:
                if func == solve:
                    res = solve(self.current_expr, self.X)
                elif func == diff:
                    res = diff(self.current_expr, self.X)
                else:
                    res = func(self.current_expr)
                
                self.render_latex(res, f"Result: {name}")
                self.txt_out.delete("1.0", tk.END)
                self.txt_out.insert("1.0", str(res))
            except Exception as e:
                messagebox.showerror("Error", str(e))

        def do_graph():
            try:
                sympy.plot(self.current_expr, show=True)
            except:
                messagebox.showerror("Graph Error", "Cannot graph this expression.")

        # Create Buttons
        ops = [
            ("EXPAND", expand), ("FACTOR", factor), 
            ("SOLVE (X=0)", solve), ("DERIVATIVE", diff), ("INTEGRATE", integrate)
        ]
        
        for name, func in ops:
            tk.Button(btn_frame, text=name, command=lambda f=func, n=name: run_op(f, n), 
                      font=("Segoe UI", 10), bg="#e1e1e1", width=12).pack(side="left", padx=5)

        tk.Button(btn_frame, text="GRAPH", command=do_graph, bg="orange", width=10).pack(side="left", padx=5)

        # Text Result Area
        self.txt_out = tk.Text(right_frame, height=8, font=("Consolas", 11))
        self.txt_out.pack(fill="both", expand=True, padx=20, pady=20)

    def render_latex(self, expr, title):
        self.ax.clear()
        self.ax.axis("off")
        # Render Math
        self.ax.text(0.5, 0.5, f"${latex(expr)}$", ha='center', va='center', fontsize=20)
        self.ax.set_title(title, fontsize=10, color="gray")
        self.canvas_widget.draw()

if __name__ == "__main__":
    app = MathSnipper()
    # Register Hotkey
    keyboard.add_hotkey('shift+alt+q', app.start_snip)
    # Start loop
    app.root.mainloop()