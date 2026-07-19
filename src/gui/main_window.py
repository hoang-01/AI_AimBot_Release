import customtkinter as ctk
import threading
import time
import ctypes
import queue
import sys
import os
import shutil
from PIL import Image, ImageFilter, ImageDraw
import onnxruntime as ort

# Ensure src is in path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from src.core.config import cfg
from src.core.camera import DXCamera
from src.core.inference import AIInference
from src.core.reflex import Reflex
from src.core.mouse import MouseController
from src.core.mouse import MouseController
from src.utils.logger import Logger
import src.utils.i18n as i18n

# --- THEME DEFINITIONS ---
THEMES = {
    "Red Devil": {
        "bg": "#050505", "panel": "#141414", "transparent_panel": "transparent", "accent": "#ff3030", "accent_hover": "#c0392b",
        "text": "#b2bec3", "text_hi": "#ffffff", "danger": "#ff0000"
    },
    "Minty Fresh": {
        "bg": "#141414", "panel": "#202020", "transparent_panel": "transparent", "accent": "#00b894", "accent_hover": "#00a884",
        "text": "#dfe6e9", "text_hi": "#ffffff", "danger": "#d63031"
    },
    "Deep Sea": {
        "bg": "#0a192f", "panel": "#112240", "transparent_panel": "transparent", "accent": "#64ffda", "accent_hover": "#52e0c4",
        "text": "#8892b0", "text_hi": "#ccd6f6", "danger": "#ff5555"
    },
    "Purple Rain": {
        "bg": "#1a1025", "panel": "#2d1b42", "transparent_panel": "transparent", "accent": "#a29bfe", "accent_hover": "#6c5ce7",
        "text": "#dcdde1", "text_hi": "#f5f6fa", "danger": "#e84393"
    }
}

ctk.set_appearance_mode("Dark")

# MAP VK CODES
VK_MAP = {
    0x01: "Left Click", 0x02: "Right Click", 0x04: "Middle Click",
    0x05: "Mouse 4", 0x06: "Mouse 5", 0x08: "Backspace", 0x09: "Tab",
    0x0D: "Enter", 0x10: "Shift", 0x11: "Ctrl", 0x12: "Alt", 0x14: "Caps Lock",
    0x1B: "Esc", 0x20: "Space", 0x25: "Left", 0x26: "Up", 0x27: "Right", 0x28: "Down",
    0x2D: "Insert", 0x2E: "Delete",
    0xA0: "L Shift", 0xA1: "R Shift", 0xA2: "L Ctrl", 0xA3: "R Ctrl", 0xA4: "L Alt", 0xA5: "R Alt"
}

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # 1. Load Config & Theme
        self.cfg = cfg 
        self.cfg.load()
        
        current_theme_name = getattr(self.cfg, "UI_THEME", "Red Devil")
        self.colors = THEMES.get(current_theme_name, THEMES["Red Devil"])
        
        # 2. Setup Window
        self.title(f"🔥 FIRE.AI - DEMON MASH ")
        self.geometry("1100x780")
        # self.attributes("-alpha", 0.98) # REMOVED: Causes transparency through to desktop
        self.configure(fg_color=self.colors["bg"])
        
        if os.path.exists("assets/images/icon.ico"):
            self.iconbitmap("assets/images/icon.ico")
            
        # 3. Background Image
        self.setup_background()
            
        # 4. Show Loading Screen
        self.setup_loading_screen()
        
        # 5. Start Async Initialization (Schedule after MainLoop start)
        self.after(200, self.start_init_thread)

    def start_init_thread(self):
        threading.Thread(target=self.init_system, daemon=True).start()

    def setup_background(self):
        # Background disabled by user request
        pass

    def create_glass_image(self, width, height, radius=20, opacity=50):
        """Generates a semi-transparent 'glass' PNG in memory."""
        # 1. Create a blank RGBA image
        glass = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(glass)
        
        # 2. Draw the rounded rectangle with alpha
        # Black (0, 0, 0) with 'opacity'
        draw.rounded_rectangle(
            [(0, 0), (width, height)], 
            radius=radius, 
            fill=(0, 0, 0, opacity)
        )
        return ctk.CTkImage(light_image=glass, dark_image=glass, size=(width, height))
    
    def setup_loading_screen(self):
        self.loading_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.loading_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Logo
        logo_path = "assets/images/logo.png"
        if os.path.exists(logo_path):
            try:
                pil_img = Image.open(logo_path)
                resized = pil_img.resize((150, 150))
                tk_img = ctk.CTkImage(light_image=resized, dark_image=resized, size=(150, 150))
                ctk.CTkLabel(self.loading_frame, image=tk_img, text="").pack(pady=20)
            except: pass
            
        ctk.CTkLabel(self.loading_frame, text="🔥 FIRE.AI 🔥\nDEMON MASH", font=("Impact", 40), text_color=self.colors["accent"]).pack()
        self.status_lbl = ctk.CTkLabel(self.loading_frame, text="Igniting Core Systems...", text_color=self.colors["text"])
        self.status_lbl.pack(pady=10)
        
        self.progress = ctk.CTkProgressBar(self.loading_frame, width=400, mode="indeterminate", progress_color=self.colors["accent"])
        self.progress.pack(pady=10)
        self.progress.start()

    def init_system(self):
        try:
            self.update_status("Loading Configuration...")
            time.sleep(0.5) 
            
            # Resources
            self.capture_queue = queue.Queue(maxsize=1)
            self.result_queue = queue.Queue(maxsize=1)
            self.reflex_queue = queue.Queue(maxsize=1)
            self.fire_queue = queue.Queue(maxsize=1)
            self.shared_state = {"active": False, "reflex_fire": False}
            
            self.update_status("Initializing DXCam...")
            self.camera = DXCamera(self.cfg, self.capture_queue, self.reflex_queue)
            
            self.update_status("Loading AI Model...")
            self.ai = AIInference(self.cfg, self.capture_queue, self.result_queue)
            
            self.update_status("Connecting HID...")
            self.reflex = Reflex(self.cfg, self.reflex_queue, self.shared_state)
            self.mouse = MouseController(self.cfg, self.result_queue, self.fire_queue, self.shared_state)
            
            self.update_status("System Ready!")
            time.sleep(0.5)
            self.after(0, self.launch_main_ui)
            
        except Exception as e:
            self.update_status(f"Error: {e}")
            
    def update_status(self, text):
        self.after(0, lambda: self.status_lbl.configure(text=text))

    def launch_main_ui(self):
        self.loading_frame.destroy()
        
        self.geometry("1100x780")
        
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.setup_sidebar()
        
        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        # GLASS PANEL (CONTENT) - Created First (Layer 1)
        # Approx size: 1100 - 240(side) - 40(pad) = 820 width
        # Approx height: 780 - 40(pad) = 740 height
        # Opacity 20% ~ 51/255 (Restored Golden Standard)
        self.glass_main = self.create_glass_image(820, 740, radius=20, opacity=51)
        self.glass_main_lbl = ctk.CTkLabel(self.content_area, image=self.glass_main, text="")
        self.glass_main_lbl.place(x=0, y=0, relwidth=1, relheight=1)
        self.glass_main_lbl.lower() # Push to background layer
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)
        
        # Loader Frame
        self.tab_loader = ctk.CTkFrame(self.content_area, fg_color="transparent")
        ctk.CTkLabel(self.tab_loader, text="LOADING...", font=("Impact", 30), text_color=self.colors["accent"]).place(relx=0.5, rely=0.5, anchor="center")
        self.tab_loader_prog = ctk.CTkProgressBar(self.tab_loader, width=200, progress_color=self.colors["accent"], mode="indeterminate")
        self.tab_loader_prog.place(relx=0.5, rely=0.6, anchor="center")
        
        # Tab Frames
        self.frames = {} 
        for name in ["Dashboard", "Aim Settings", "TriggerBot", "System"]:
        # Set bg_color="transparent" and style scrollbars
            fr = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent", bg_color="transparent",
                                        scrollbar_fg_color="#222", scrollbar_button_color="#444", scrollbar_button_hover_color=self.colors["accent"])
            self.frames[name] = fr
        
        self.setup_dashboard(self.frames["Dashboard"])
        self.setup_aim_settings(self.frames["Aim Settings"])
        self.setup_triggerbot(self.frames["TriggerBot"])
        self.setup_system(self.frames["System"])
        
        self.setup_footer()
        
        self.show_frame("Dashboard")
        self.running = False 

    def setup_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color="transparent")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # GLASS PANEL (SIDEBAR) - Created First (Layer 1)
        # Full height (780), Width 240
        # Opacity 28% ~ 71/255
        self.glass_side = self.create_glass_image(240, 780, radius=0, opacity=71)
        self.glass_side_lbl = ctk.CTkLabel(self.sidebar, image=self.glass_side, text="")
        self.glass_side_lbl.place(x=0, y=0, relwidth=1, relheight=1)
        self.glass_side_lbl.lower() # Push to background layer
        
        
        # LOGO
        self.logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        # Add padx=20 to shift logo inside the glass box (which starts at x=10)
        self.logo_frame.pack(pady=(30, 20), padx=20)
        logo_path = "assets/images/logo.png"
        if os.path.exists(logo_path):
            try:
                pil_img = Image.open(logo_path)
                resized = pil_img.resize((150, 150))
                self.logo_img = ctk.CTkImage(light_image=resized, dark_image=resized, size=(150, 150))
                ctk.CTkLabel(self.logo_frame, image=self.logo_img, text="").pack()
            except: pass
        else:
            ctk.CTkLabel(self.logo_frame, text="FIRE.AI\nDEMON MASH", font=("Impact", 30), text_color=self.colors["accent"]).pack()
            
        # NAVIGATION
        self.nav_btns = {}
        # Key to display map
        self.menu_keys = {
            "Dashboard": "dashboard",
            "Aim Settings": "aim_settings", 
            "TriggerBot": "triggerbot",
            "Visuals": "visuals",
            "System": "system"
        }
        menus = ["Dashboard", "Aim Settings", "TriggerBot", "System"]
        lang = getattr(self.cfg, "APP_LANGUAGE", "en")
        
        for name in menus:
            display_text = i18n.tr(self.menu_keys[name], lang)
            btn = ctk.CTkButton(self.sidebar, text=f"  {display_text}", anchor="w",
                                fg_color="transparent", hover_color=self.colors["panel"],
                                text_color=self.colors["text"],
                                font=ctk.CTkFont(size=14, weight="bold"), height=45,
                                command=lambda n=name: self.safe_switch_tab(n))
            # Increased padx to 20 to fit inside the new box
            btn.pack(fill="x", padx=20, pady=2) 
            self.nav_btns[name] = btn
            
    def safe_switch_tab(self, name):
        for n, f in self.frames.items(): f.grid_forget()
        self.tab_loader.grid(row=0, column=0, sticky="nsew")
        self.tab_loader_prog.start()
        
        for n in self.frames.keys():
             self.nav_btns[n].configure(fg_color="transparent", text_color=self.colors["text"])
        self.nav_btns[name].configure(fg_color=self.colors["panel"], text_color=self.colors["accent"])
        
        self.after(200, lambda: self.show_frame(name))
        
    def show_frame(self, name):
        self.tab_loader.grid_forget()
        self.tab_loader_prog.stop()
        self.frames[name].grid(row=0, column=0, sticky="nsew")

    # --- TABS ---
    
    def setup_dashboard(self, parent):
        lang = getattr(self.cfg, "APP_LANGUAGE", "en")
        
        self.lbl_header = ctk.CTkLabel(parent, text=i18n.tr("mission_control", lang), font=("Arial", 24, "bold"), text_color=self.colors["text_hi"])
        self.lbl_header.pack(anchor="w", pady=10)
        
        self.btn_power = ctk.CTkButton(parent, text=i18n.tr("launch_system", lang), height=60, font=("Arial", 20, "bold"),
                                       fg_color=self.colors.get("transparent_panel", "transparent"), border_width=2, border_color=self.colors["accent"],
                                       hover_color="#333", corner_radius=20, # Rounded
                                       command=lambda: self.toggle_engine())
        self.btn_power.pack(fill="x", pady=20)
        
        self.create_bind_btn(parent, i18n.tr("toggle_key", lang), "TOGGLE_KEY")
        self.create_game_selector(parent)
        
        # Transparent Frame for Stats
        stat_frame = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=15)
        stat_frame.pack(fill="x", pady=20)
        
        # Get actual active provider from AI instance if running, else check availability
        gpu_text = i18n.tr("initializing", lang)
        if hasattr(self, "ai") and hasattr(self.ai, "active_provider"):
             gpu_text = f"ACTIVE: {self.ai.active_provider}"
             if self.ai.active_provider == "CPU":
                 gpu_text += f" ({i18n.tr('safe_mode', lang)})"
        else:
             providers = ort.get_available_providers()
             gpu_text = "NVIDIA CUDA" if "CUDAExecutionProvider" in providers else "CPU (Slow)"
        
        self.create_stat(stat_frame, i18n.tr("processing_unit", lang), gpu_text, 0, 0, self.colors["accent"])
        self.create_stat(stat_frame, i18n.tr("security_status", lang), "ENCRYPTED + HWID LOCK", 0, 1, self.colors["accent"])
        self.create_stat(stat_frame, i18n.tr("theme", lang), self.cfg.UI_THEME, 1, 0, self.colors["text"])
        
        threading.Thread(target=self.dashboard_key_listener, daemon=True).start()

    def setup_aim_settings(self, parent):
        lang = getattr(self.cfg, "APP_LANGUAGE", "en")
        # Header with Help Button
        h_frame = ctk.CTkFrame(parent, fg_color="transparent")
        h_frame.pack(fill="x", pady=10)
        ctk.CTkLabel(h_frame, text=i18n.tr("aim_config", lang), font=("Arial", 24, "bold"), text_color=self.colors["text_hi"]).pack(side="left")
        ctk.CTkButton(h_frame, text=i18n.tr("help", lang), width=80, height=25, fg_color="#333", hover_color="#444", 
                      command=self.show_aim_help).pack(side="left", padx=15)
        
        # 1. SLIDERS (Moved to Top)
        self.create_slider(parent, i18n.tr("confidence", lang), 0.1, 1.0, "CONF_THRESHOLD")
        self.create_slider(parent, i18n.tr("fov_size", lang) + " (X)", 50, 640, "FOV_WIDTH")
        self.create_slider(parent, i18n.tr("fov_size", lang) + " (Y)", 50, 640, "FOV_HEIGHT")
        self.create_slider(parent, i18n.tr("smoothing", lang), 0.01, 1.0, "SMOOTHING")
        self.create_slider(parent, i18n.tr("mouse_brake", lang), 0.0, 1.0, "MOUSE_BRAKE_FORCE")
        self.create_slider(parent, "Deadzone X", 0.0, 10.0, "DEADZONE_X")
        self.create_slider(parent, "Deadzone Y", 0.0, 10.0, "DEADZONE_Y")
        self.create_slider(parent, i18n.tr("speed", lang), 0.1, 2.0, "PID_KP")
        self.create_slider(parent, i18n.tr("stability", lang), 0.0, 0.5, "PID_KD")
        
        ctk.CTkLabel(parent, text=i18n.tr("activation_key", lang), font=("Arial", 16, "bold"), text_color="#aaa").pack(anchor="w", pady=(20, 10))
        self.create_bind_btn(parent, "Aim Lock Key", "AIM_KEY")

        # 2. RECOIL CONTROL (Moved to Bottom)
        ctk.CTkLabel(parent, text="RECOIL CONTROL SYSTEM (RCS)", font=("Arial", 16, "bold"), text_color=self.colors["text_hi"]).pack(anchor="w", pady=(30, 10))
        
        f_recoil = ctk.CTkFrame(parent, fg_color=self.colors.get("transparent_panel", "transparent"), corner_radius=8, border_width=1, border_color="#333")
        f_recoil.pack(fill="x", pady=5)
        ctk.CTkLabel(f_recoil, text=i18n.tr("recoil_profile", lang), text_color=self.colors["text"]).pack(side="left", padx=20)
        
        profiles = ["None (Aim Only)", "Valorant - Vandal/Phantom", "PUBG - No Logic (Empty)"]
        combo_recoil = ctk.CTkOptionMenu(f_recoil, values=profiles, command=self.change_recoil_profile)
        
        # Consistent Profile Loading
        curr = getattr(self.cfg, "ACTIVE_RECOIL_PROFILE", "None (Aim Only)")
        if curr not in profiles: curr = "None (Aim Only)"
        combo_recoil.set(curr)
        combo_recoil.pack(side="right", padx=20, pady=15)
        
        # Recoil Customization (Only shows if valid profile)
        if "Valorant" in curr:
             self.create_recoil_editor(parent, "Valorant - Vandal/Phantom")

    def create_recoil_editor(self, parent, profile_name):
        lang = getattr(self.cfg, "APP_LANGUAGE", "en")
        f = ctk.CTkFrame(parent, fg_color=self.colors.get("transparent_panel", "transparent"), corner_radius=8, border_width=1, border_color=self.colors["accent"])
        f.pack(fill="x", pady=5)
        ctk.CTkLabel(f, text=i18n.tr("edit_recoil", lang), font=("Arial", 12, "bold"), text_color=self.colors["accent"]).pack(pady=5)
        
        # Get current pattern
        pat = self.cfg.RECOIL_PATTERNS.get(profile_name, [])
        if len(pat) < 4: return # Safety check
        
        # Stage 1: Neck (Index 1)
        self.create_stage_slider(f, "Step 1: Neck", pat, 1, 0.1, 1.0, 10, 30)
        # Stage 2: Chest (Index 2)
        self.create_stage_slider(f, "Step 2: Chest", pat, 2, 0.5, 2.0, 20, 50)
        # Stage 3: Spray (Index 3)
        self.create_stage_slider(f, "Step 3: Spray", pat, 3, 1.5, 3.0, 25, 60)

    def create_stage_slider(self, parent, label, pattern, idx, t_min, t_max, y_min, y_max):
        cur_t, _, cur_y = pattern[idx]
        
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(row, text=label, width=80, anchor="w", text_color="#aaa").pack(side="left")
        
        # Time Slider
        var_t = ctk.StringVar(value=f"{cur_t:.2f}s")
        s_t = ctk.CTkSlider(row, from_=t_min, to=t_max, width=100, number_of_steps=20,
                            command=lambda v: self.update_recoil_stage(pattern, idx, 0, v, var_t, "s"))
        s_t.set(cur_t)
        s_t.pack(side="left", padx=5)
        ctk.CTkLabel(row, textvariable=var_t, width=40, text_color=self.colors["accent"]).pack(side="left")
        
        # Y Slider
        var_y = ctk.StringVar(value=f"{cur_y}px")
        s_y = ctk.CTkSlider(row, from_=y_min, to=y_max, width=100, number_of_steps=20,
                            command=lambda v: self.update_recoil_stage(pattern, idx, 2, v, var_y, "px"))
        s_y.set(cur_y)
        s_y.pack(side="left", padx=5)
        ctk.CTkLabel(row, textvariable=var_y, width=40, text_color=self.colors["accent"]).pack(side="left")

    def update_recoil_stage(self, pattern, idx, tuple_idx, val, var_lbl, unit):
        # Update tuple in list (tuples are immutable so replace)
        old = pattern[idx]
        new_list = list(old)
        new_list[tuple_idx] = float(val) if tuple_idx == 0 else int(val)
        pattern[idx] = tuple(new_list)
        
        # Update Label
        var_lbl.set(f"{new_list[tuple_idx]:.2f}{unit}" if tuple_idx == 0 else f"{new_list[tuple_idx]}{unit}")
        
        # Force Update Active Pattern
        if self.cfg.ACTIVE_RECOIL_PROFILE == "Valorant - Vandal/Phantom":
            self.cfg.AIM_PATTERN = pattern
            
    def change_recoil_profile(self, choice):
        self.cfg.ACTIVE_RECOIL_PROFILE = choice
        self.cfg.AIM_PATTERN = self.cfg.RECOIL_PATTERNS.get(choice, [])
        self.cfg.save()
        self.safe_switch_tab("Aim Settings")

    def setup_triggerbot(self, parent):
        lang = getattr(self.cfg, "APP_LANGUAGE", "en")
        ctk.CTkLabel(parent, text=i18n.tr("triggerbot", lang), font=("Arial", 24, "bold"), text_color=self.colors["text_hi"]).pack(anchor="w", pady=10)
        self.create_slider(parent, i18n.tr("trigger_zone", lang), 0.1, 1.0, "TRIGGER_ZONE")
        self.create_slider(parent, i18n.tr("reaction_delay", lang), 0.0, 0.5, "TRIGGER_DELAY")
        ctk.CTkLabel(parent, text=i18n.tr("activation_key", lang), font=("Arial", 16, "bold"), text_color="#aaa").pack(anchor="w", pady=(30, 10))
        self.create_bind_btn(parent, i18n.tr("trigger_key", lang), "AUTO_FIRE_KEY")
        self.create_bind_btn(parent, i18n.tr("reflex_key", lang), "REFLEX_KEY")
        
    def setup_visuals(self, parent):
        lang = getattr(self.cfg, "APP_LANGUAGE", "en")
        ctk.CTkLabel(parent, text=i18n.tr("visuals", lang), font=("Arial", 24, "bold"), text_color=self.colors["text_hi"]).pack(anchor="w", pady=10)
        # Placeholder for ESP drawing (Needs Overlay implementation)
        self.create_placeholder(parent, "Overlay ESP drawing coming in v3.0")

    def setup_system(self, parent):
        lang = getattr(self.cfg, "APP_LANGUAGE", "en")
        ctk.CTkLabel(parent, text=i18n.tr("system", lang), font=("Arial", 24, "bold"), text_color=self.colors["text_hi"]).pack(anchor="w", pady=10)
        
        # 1. THEME SELECTOR
        frame_theme = ctk.CTkFrame(parent, fg_color=self.colors.get("transparent_panel", "transparent"), corner_radius=8, border_width=1, border_color="#333")
        frame_theme.pack(fill="x", pady=10)
        ctk.CTkLabel(frame_theme, text=i18n.tr("theme", lang) + f" ({i18n.tr('restart_required', lang)})", font=("Arial", 12), text_color=self.colors["text"]).pack(side="left", padx=20)
        
        themes = list(THEMES.keys())
        combo_theme = ctk.CTkOptionMenu(frame_theme, values=themes, command=self.change_theme)
        combo_theme.set(getattr(self.cfg, "UI_THEME", "Red Devil"))
        combo_theme.pack(side="right", padx=20, pady=15)

        # 2. AI PROCESSING UNIT (NEW)
        frame_gpu = ctk.CTkFrame(parent, fg_color=self.colors.get("transparent_panel", "transparent"), corner_radius=15, border_width=1, border_color="#333")
        frame_gpu.pack(fill="x", pady=10)
        ctk.CTkLabel(frame_gpu, text=i18n.tr("processing_unit", lang) + f" ({i18n.tr('restart_required', lang)})", font=("Arial", 12), text_color=self.colors["text"]).pack(side="left", padx=20)
        
        providers = ["Auto", "TensorRT", "CUDA", "DirectML", "CPU"]
        combo_gpu = ctk.CTkOptionMenu(frame_gpu, values=providers, command=self.change_provider)
        combo_gpu.set(getattr(self.cfg, "AI_PROVIDER", "Auto"))
        combo_gpu.pack(side="right", padx=20, pady=15)
        
        # 3. LANGUAGE SELECTOR (NEW)
        frame_lang = ctk.CTkFrame(parent, fg_color=self.colors.get("transparent_panel", "transparent"), corner_radius=15, border_width=1, border_color="#333")
        frame_lang.pack(fill="x", pady=10)
        ctk.CTkLabel(frame_lang, text=i18n.tr("language", lang) + f" ({i18n.tr('restart_required', lang)})", font=("Arial", 12), text_color=self.colors["text"]).pack(side="left", padx=20)
        
        langs = list(i18n.LANGUAGES.keys())
        combo_lang = ctk.CTkOptionMenu(frame_lang, values=langs, command=self.change_language)
        # Reverse lookup to find name from code
        current_code = getattr(self.cfg, "APP_LANGUAGE", "en")
        current_name = "English"
        for name, code in i18n.LANGUAGES.items():
            if code == current_code or name == current_code:
                current_name = name
                break
        
        combo_lang.set(current_name)
        combo_lang.pack(side="right", padx=20, pady=15)

        # 3. OPEN FOLDER BUTTON
        ctk.CTkButton(parent, text=i18n.tr("open_folder", lang), fg_color="#333", 
                      command=lambda: os.startfile(os.path.join(os.getcwd(), "assets", "backgrounds"))).pack(pady=10)

    def change_theme(self, choice):
        self.cfg.UI_THEME = choice
        self.cfg.save()
        self.ask_restart()
        

        
    def change_provider(self, choice):
        self.cfg.AI_PROVIDER = choice
        self.cfg.save()
        self.ask_restart()

    def change_language(self, choice):
        code = i18n.LANGUAGES.get(choice, "en")
        self.cfg.APP_LANGUAGE = code
        self.cfg.save()
        self.ask_restart()

    def ask_restart(self):
        lang = getattr(self.cfg, "APP_LANGUAGE", "en")
        # MessageBox Yes/No (Type 4 = YesNo)
        resp = ctypes.windll.user32.MessageBoxW(0, i18n.tr("restart_confirm", lang), "Settings Changed", 4)
        if resp == 6: # 6 = Yes
            self.restart_app()

    def restart_app(self):
        self.running = False
        if hasattr(self, "ai"): self.ai.stop()
        self.destroy()
        # Restart
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def show_aim_help(self):
        msg = (
            "🎯 AIM SETTINGS GUIDE:\n\n"
            "• AI Confidence (0.1 - 1.0): Minimum certainty required to aim. Higher = Less false positives but might miss heads.\n"
            "• FOV Width/Height: The scanning area box size in the center of screen.\n"
            "• Smoothing (0.01 - 1.0): Lower = Robot/Snappy. Higher = Human/Slow. Rec: 0.2-0.4 for smooth legit aim.\n"
            "• Aim Speed (P): How fast the crosshair moves to head. High P = Fast Snap.\n"
            "• Stability (D): Prevents shaking/overshooting. Increase if aiming vibrates."
        )
        ctypes.windll.user32.MessageBoxW(0, msg, "Aim Assist Help", 0)

    def setup_footer(self):
        lang = getattr(self.cfg, "APP_LANGUAGE", "en")
        self.footer = ctk.CTkFrame(self, height=40, width=500, fg_color="transparent", corner_radius=0)
        self.footer.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        # GLASS PANEL (FOOTER) - Layer 1
        # Full width (1100), Height 40
        # Opacity 32% ~ 82/255
        self.glass_footer = self.create_glass_image(1100, 40, radius=0, opacity=82)
        self.glass_footer_lbl = ctk.CTkLabel(self.footer, image=self.glass_footer, text="")
        self.glass_footer_lbl.place(x=0, y=0, relwidth=1, relheight=1)
        self.glass_footer_lbl.lower()
        
        self.lbl_status = ctk.CTkLabel(self.footer, text=i18n.tr("waiting", lang), text_color=self.colors["text"])
        self.lbl_status.place(relx=0.5, rely=0.5, anchor="center")
        
        # Right Side Buttons
        ctk.CTkButton(self.footer, text=i18n.tr("save_config", lang), width=120, fg_color=self.colors["accent"], 
                      text_color="white", command=self.save_cfg).pack(side="right", padx=10, pady=5)

        ctk.CTkButton(self.footer, text=i18n.tr("restart_btn", lang), width=100, fg_color="#333", 
                      hover_color="#c0392b", text_color="white", 
                      command=self.restart_app).pack(side="right", padx=10, pady=5)

    # --- HELPERS ---
    def create_game_selector(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(fill="x", pady=10)
        
        # Header Row
        header = ctk.CTkFrame(f, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(header, text="GAME PROFILE", font=("Arial", 12, "bold"), text_color=self.colors["text"]).pack(side="left", padx=10)
        
        # Helper Text
        self.lbl_profile_status = ctk.CTkLabel(header, text="", font=("Arial", 10, "italic"), text_color=self.colors["accent"])
        self.lbl_profile_status.pack(side="right", padx=10)

        # Control Row
        row = ctk.CTkFrame(f, fg_color="transparent", corner_radius=15, border_width=1, border_color="#333")
        row.pack(fill="x", pady=5)
        
        # Combo (Only 2 games)
        self.game_var = ctk.StringVar(value="PUBG Mobile")
        self.combo_game = ctk.CTkComboBox(
            row, 
            values=["PUBG Mobile", "Valorant"],
            variable=self.game_var,
            width=180,
            command=self.on_game_change,
            fg_color="#222", border_color="#444", button_color=self.colors["panel"], button_hover_color=self.colors["accent"]
        )
        self.combo_game.pack(side="left", padx=15, pady=10)
        
        # Active Model Info (Small)
        self.model_var = ctk.StringVar(value=os.path.basename(self.cfg.MODEL_PATH))
        self.lbl_model_name = ctk.CTkLabel(row, textvariable=self.model_var, font=("Arial", 10), text_color="#666")
        self.lbl_model_name.pack(side="left", padx=10)
        
        # Load Model Button (Separate)
        btn_load = ctk.CTkButton(row, text="LOAD MODEL", width=100, fg_color="#333", hover_color="#444", corner_radius=15, command=self.select_model)
        btn_load.pack(side="right", padx=10, pady=10)
        
        # Initial status update
        if "best" in self.cfg.MODEL_PATH.lower():
             self.lbl_profile_status.configure(text="AI: YOLO nano (640x640)")
        else:
             self.lbl_profile_status.configure(text="AI: Custom Model")

        if self.cfg.GAME_MODE == "PUBG":
             self.combo_game.set("PUBG Mobile")
        elif self.cfg.GAME_MODE == "VALORANT":
             self.combo_game.set("Valorant")

    def on_game_change(self, choice):
        if "PUBG" in choice:
            self.cfg.GAME_MODE = "PUBG"
            self.cfg.MODEL_PATH = r"models/best_fp16.onnx"
            self.cfg.FOV_WIDTH = 640
            self.cfg.FOV_HEIGHT = 640
            self.cfg.CONF_THRESHOLD = 0.60
            self.lbl_profile_status.configure(text="AI: YOLO nano (640x640)")
            
        elif "Valorant" in choice:
            self.cfg.GAME_MODE = "VALORANT"
            self.cfg.MODEL_PATH = r"models/best_fp16.onnx"
            self.cfg.FOV_WIDTH = 640
            self.cfg.FOV_HEIGHT = 640
            self.cfg.CONF_THRESHOLD = 0.50
            self.lbl_profile_status.configure(text="AI: YOLO nano (640x640)")
            
        self.model_var.set(os.path.basename(self.cfg.MODEL_PATH))
        self.save_cfg()
        self.restart_ai()

    def restart_ai(self):
        """Hot-reloads the AI engine"""
        if hasattr(self, 'ai'):
            try:
                self.ai.reload()
                # If running, log it
                if self.ai.is_running:
                    print("AI Reloaded while running.")
            except Exception as e:
                print(f"Error reloading AI: {e}")

    def select_model(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(filetypes=[("AI Model", "*.onnx *.bin")])
        if path:
            self.cfg.MODEL_PATH = path
            self.cfg.GAME_MODE = "CUSTOM"  # Set to custom mode
            self.model_var.set(os.path.basename(path))
            self.lbl_profile_status.configure(text="AI: Custom Model")
            self.save_cfg()
            self.restart_ai()  # Reload AI with new model

    def create_stat(self, parent, label, val, r, c, val_color):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=r, column=c, sticky="ew", padx=20, pady=15)
        ctk.CTkLabel(f, text=label, text_color="#888", font=("Arial", 11)).pack(anchor="w")
        ctk.CTkLabel(f, text=val, font=("Arial", 14, "bold"), text_color=val_color).pack(anchor="w")
        parent.grid_columnconfigure(c, weight=1)
        
    def create_slider(self, parent, label, v_min, v_max, cfg_attr):
        f = ctk.CTkFrame(parent, fg_color=self.colors.get("transparent_panel", "transparent"), corner_radius=8)
        f.pack(fill="x", pady=5)
        val_var = ctk.StringVar(value=str(round(getattr(self.cfg, cfg_attr), 3)))
        ctk.CTkLabel(f, text=label, text_color=self.colors["text"]).pack(side="left", padx=20)
        ctk.CTkLabel(f, textvariable=val_var, width=50, text_color=self.colors["accent"]).pack(side="right", padx=10)
        s = ctk.CTkSlider(f, from_=v_min, to=v_max, command=lambda v: self.update_cfg(cfg_attr, v, val_var))
        s.set(getattr(self.cfg, cfg_attr))
        s.configure(progress_color=self.colors["accent"], button_color="white", fg_color="#333", button_hover_color="#eee")
        s.pack(side="right", fill="x", expand=True, padx=10)

    def update_cfg(self, attr, val, var_lbl):
        val = int(val) if val > 10 else round(val, 3)
        var_lbl.set(str(val))
        setattr(self.cfg, attr, val)

    def create_bind_btn(self, parent, label, cfg_attr):
        f = ctk.CTkFrame(parent, fg_color=self.colors.get("transparent_panel", "transparent"), corner_radius=8)
        f.pack(fill="x", pady=5)
        curr_code = getattr(self.cfg, cfg_attr)
        curr_name = "NONE" if not curr_code else VK_MAP.get(curr_code, f"KEY {curr_code}")
        col = "#333" if curr_code else "#444"
        ctk.CTkLabel(f, text=label, text_color=self.colors["text"]).pack(side="left", padx=20)
        btn = ctk.CTkButton(f, text=f"[{curr_name}]", width=150, fg_color=col, hover_color="#555",
                            command=lambda: self.start_binding(cfg_attr, btn))
        btn.pack(side="right", padx=20, pady=10)

    def start_binding(self, attr, btn):
        btn.configure(text="PRESS ANY KEY...", fg_color="#e67e22")
        self.update_idletasks()
        threading.Thread(target=self.scan_key, args=(attr, btn), daemon=True).start()
        
    def scan_key(self, attr, btn):
        time.sleep(0.3)
        found = None
        start_t = time.time()
        while time.time() - start_t < 5:
            if ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000:
                setattr(self.cfg, attr, None)
                btn.configure(text="[ NONE ]", fg_color="#444")
                return
            for vk in range(1, 255):
                if vk == 0x1B: continue
                if ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000:
                    found = vk
                    break
            if found: break
            time.sleep(0.01)
        if found:
            setattr(self.cfg, attr, found)
            name = VK_MAP.get(found, f"KEY {found}")
            btn.configure(text=f"[{name}]", fg_color="#333")
        else:
            curr = getattr(self.cfg, attr)
            btn.configure(text=f"[{VK_MAP.get(curr, f'KEY {curr}') if curr else 'NONE'}]", fg_color="#333" if curr else "#444")

    def dashboard_key_listener(self):
        while True:
            t_key = getattr(self.cfg, "TOGGLE_KEY", None)
            if t_key and (ctypes.windll.user32.GetAsyncKeyState(t_key) & 0x8000):
                self.toggle_engine()
                time.sleep(0.5)
            time.sleep(0.1)

    def save_cfg(self):
        self.cfg.save()
        ctypes.windll.user32.MessageBoxW(0, "✅ Config Saved!", "SYSTEM", 0)

    def toggle_engine(self):
        if not self.running:
            self.running = True
            self.btn_power.configure(text="TERMINATE SYSTEM", fg_color=self.colors["danger"], hover_color="#c0392b")
            self.lbl_status.configure(text="ACTIVE - SCANNING", text_color=self.colors["accent"])
            with self.capture_queue.mutex: self.capture_queue.queue.clear()
            self.camera.is_running = self.ai.is_running = False
            threading.Thread(target=self.camera.start, daemon=True).start()
            threading.Thread(target=self.ai.start, daemon=True).start()
            threading.Thread(target=self.reflex.start, daemon=True).start()
            threading.Thread(target=self.mouse.start, daemon=True).start()
            threading.Thread(target=self.mouse._fire_loop, daemon=True).start()
        else:
            self.running = False
            self.btn_power.configure(text="LAUNCH SYSTEM", fg_color=self.colors["panel"], hover_color="#333")
            self.lbl_status.configure(text="STANDBY", text_color="#888")
            self.camera.stop()
            self.ai.stop()
            self.reflex.stop()
            self.mouse.stop()
            
    def create_placeholder(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=("Arial", 20), text_color="#444").place(relx=0.5, rely=0.5, anchor="center")

    def animate_pulse(self):
        """Background loop for visual effects (Fire/Breathing/Pulse)"""
        import time
        import random
        
        # Fire Palette
        fire_colors = [
            self.colors["accent"], # Red
            "#e74c3c", # Soft Red
            "#d35400", # Pumpkin
            "#e67e22", # Carrot (Orange)
            "#f39c12"  # Orange Yellow
        ]
        
        step = 0
        
        while True:
            try:
                if not self.winfo_exists(): break
                
                # 1. Fire Flicker Effect (Header & Power Button)
                if hasattr(self, 'lbl_header') and self.lbl_header.winfo_exists():
                    # Random flicker
                    if random.random() > 0.7:
                        col = random.choice(fire_colors)
                        self.lbl_header.configure(text_color=col)
                        
                if hasattr(self, 'btn_power') and self.btn_power.winfo_exists():
                     # Pulse Border
                     if not self.running:
                         bord_col = fire_colors[step % len(fire_colors)]
                         self.btn_power.configure(border_color=bord_col)
                
                # 2. Status Flicker when Running (Cyber/Glitch effect)
                if self.running and hasattr(self, 'lbl_status') and self.lbl_status.winfo_exists():
                    if random.random() > 0.85:
                        self.lbl_status.configure(text_color="#ffffff")
                    else:
                        self.lbl_status.configure(text_color=self.colors["accent"])
                        
                time.sleep(0.1)
                step += 1
            except Exception:
                break

def launch_gui():
    app = MainWindow()
    threading.Thread(target=app.animate_pulse, daemon=True).start()
    app.mainloop()
