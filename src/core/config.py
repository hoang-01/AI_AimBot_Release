import json
import os
import numpy as np

class Config:
    def __init__(self):
        # Default Settings
        # Default Settings
        self.MODEL_PATH = r"models/best_480_fp16.onnx"  # FP16 optimized for speed
        self.HARDWARE_KEY = "HS_GOLD_V4_8822"
        self.FOV_WIDTH = 480     
        self.FOV_HEIGHT = 480     
        self.CONF_THRESHOLD = 0.60
        self.GAME_MODE = "PUBG" # PUBG, VALORANT, CUSTOM

        
        # TUNED FOR RESPONSIVENESS
        self.PID_KP = 0.5
        self.PID_KD = 0.35    
        self.SMOOTHING = 0.35
        self.MOUSE_BRAKE_FORCE = 0.0 # 0.0 - 1.0 (Braking power)
        
        self.AIM_KEY = 0x02         # Right Click
        self.AUTO_FIRE_KEY = 0x05    # Mouse 4 (AI Trigger)
        self.REFLEX_KEY = 0x06       # Mouse 5 (Color Trigger)
        self.TOGGLE_KEY = 0x2D       # Insert Key (Default)
        
        self.AIM_OFFSET_Y = 15       
        self.TARGET_LOCK_STRENGTH = 250
        self.DEADZONE_X = 0.75   
        self.DEADZONE_Y = 0.75     
        
        # --- RECOIL CONTROL SYSTEM (RCS) ---
        self.RCS_STRENGTH_VAL = 1.0  # Multiplier for Y-Pull (1.0 = Default)
        self.RCS_TIMING_VAL = 1.0    # Multiplier for Time (1.0 = Default)
        
        # Format: (Thời gian giây, Offset X, Offset Y)
        self.RCS_PATTERN = [] 
        
        # DEFINED RECOIL PATTERNS
        self.RECOIL_PATTERNS = {
            "None (Aim Only)": [],
            
            "Valorant - Vandal/Phantom": [
                (0.0, 0, 0),   # 0s: Head
                (0.5, 0, 15),  # 0.5s: Neck
                (1.0, 0, 25),  # 1.0s: Chest
                (2.0, 0, 28)   # Spray
            ],
            
            "PUBG - AKM/Beryl": [
                (0.0, 0, 0),
                (0.3, 0, 30),  # High vertical recoil
                (0.6, 0, 50),
                (1.5, 0, 40)
            ],
            
            "Apex - R301/Flatline": [
                (0.0, 0, 0),
                (0.5, 0, 10),  # Smooth recoil
                (1.5, 0, 20)
            ]
        }
        
        self.ACTIVE_RECOIL_PROFILE = "None (Aim Only)"
        self.AIM_PATTERN = self.RECOIL_PATTERNS[self.ACTIVE_RECOIL_PROFILE]
        self.MOUSE_BRAKE_FORCE = 20.0 
        
        self.TRIGGER_ZONE = 0.3      
        self.TRIGGER_DELAY = 0.050   # 50ms (semi-auto)
        
        # --- REFLEX (COLOR) CONFIG ---
        self.REFLEX_ZONE_W = 7       
        self.REFLEX_ZONE_H = 3       
        self.PURPLE_LOW = np.array([140, 110, 110])
        self.PURPLE_HIGH = np.array([160, 255, 255])
        
        # --- EXTREME PERFORMANCE ---
        self.POLLING_RATE_HZ = 1000   
        self.MAX_INFERENCE_FPS = 1000  
        self.SHOW_LOGS = True
        
        # --- UI PERSONALIZATION ---
        self.UI_THEME = "Red Devil" # Options: Red Devil, Minty Fresh, Deep Sea, Purple Rain
        self.UI_BG_PATH = ""        # Path to background image
        
        # --- ADVANCED SYSTEM ---
        self.AI_PROVIDER = "Auto"   # Auto, CUDA, DirectML, CPU
        self.APP_LANGUAGE = "English" # Default Language


    def load(self, path="config/settings.json"):
        """Load configuration from a JSON file."""
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    
                    # Handle converting lists back to numpy arrays if needed
                    if "PURPLE_LOW" in data:
                        data["PURPLE_LOW"] = np.array(data["PURPLE_LOW"])
                    if "PURPLE_HIGH" in data:
                        data["PURPLE_HIGH"] = np.array(data["PURPLE_HIGH"])
                        
                    self.__dict__.update(data)
                    
                    # Sync Recoil Pattern
                    if hasattr(self, "ACTIVE_RECOIL_PROFILE") and self.ACTIVE_RECOIL_PROFILE in self.RECOIL_PATTERNS:
                        self.AIM_PATTERN = self.RECOIL_PATTERNS[self.ACTIVE_RECOIL_PROFILE]
                        
                print(f"📂 Config loaded from {path}")
            except Exception as e:
                print(f"⚠️ Failed to load config: {e}")
        else:
            print("⚠️ Config file not found, using defaults.")

    def save(self, path="config/settings.json"):
        """Save current configuration to JSON."""
        try:
            # Create config dir if not exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            data = self.__dict__.copy()
            # Convert numpy arrays to lists for JSON serialization
            if isinstance(data.get("PURPLE_LOW"), np.ndarray):
                data["PURPLE_LOW"] = data["PURPLE_LOW"].tolist()
            if isinstance(data.get("PURPLE_HIGH"), np.ndarray):
                data["PURPLE_HIGH"] = data["PURPLE_HIGH"].tolist()
            
            with open(path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"💾 Config saved to {path}")
        except Exception as e:
            print(f"⚠️ Failed to save config: {e}")

    def get_model_data(self):
        """Load model securely from disk (handles both raw .onnx and encrypted .bin)"""
        # Note: In the refactored version, we might pass the full path or handle relative paths intelligently
        # Assuming MODEL_PATH is relative to project root or absolute
        
        if not os.path.exists(self.MODEL_PATH):
             # Try looking in assets/models if not found directly
             alt_path = os.path.join("assets", "models", os.path.basename(self.MODEL_PATH))
             if os.path.exists(alt_path):
                 self.MODEL_PATH = alt_path

        if self.MODEL_PATH.endswith(".bin"):
            try:
                print(f"🔐 Loading Protected Model: {self.MODEL_PATH}")
                with open(self.MODEL_PATH, 'rb') as f:
                    content = f.read()
                
                # Check Signature
                if content.startswith(b'AILOCK'):
                    # Strip Header & Decrypt
                    data = bytearray(content[6:])
                    key = 0xAB # Matching Key
                    for i in range(len(data)):
                        data[i] ^= key
                    return bytes(data)
                else:
                    print("❌ Invalid Model Format")
                    return None
            except Exception as e:
                print(f"❌ Load Error: {e}")
                return None
        else:
            # Normal ONNX File
            return self.MODEL_PATH

# Global instance for easy access if needed, though dependency injection is preferred
cfg = Config()
