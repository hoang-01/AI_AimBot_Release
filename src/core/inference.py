import os
import sys
import time
import numpy as np
import onnxruntime as ort
import cv2
import queue
import traceback
from src.utils.logger import Logger

# --- DLL FIX IMPORTS ---
def setup_dll_paths():
    """Configures DLL search paths for CUDA/TensorRT to avoid ImportErrors."""
    try:
        # 1. Local Path (zlibwapi.dll)
        # We assume zlibwapi.dll is next to the executable or in the current working directory
        cwd = os.getcwd()
        os.add_dll_directory(cwd)
        Logger.info(f"✅ Loaded Local DLL Path: {cwd}")
        
        # 2. Nvidia PIP Packages
        for search_path in sys.path:
            if not os.path.exists(search_path): continue
            packages = ["nvidia/cudnn", "nvidia/cublas", "tensorrt_libs", "tensorrt_cu13_libs"]
            subfolders = ["", "bin", "lib"]
            for pkg in packages:
                for sub in subfolders:
                    dll_path = os.path.join(search_path, pkg, sub)
                    if os.path.exists(dll_path):
                         # Check if any DLL exists here to avoid adding empty paths
                        if any(f.endswith(".dll") for f in os.listdir(dll_path)):
                            os.add_dll_directory(dll_path)
                            # Logger.info(f"✅ Added Lib Path: {dll_path}")

        # 3. System CUDA (Backup)
        cuda_candidates = [
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.3\bin",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2\bin",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1\bin",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0\bin",
        ]
        for path in cuda_candidates:
            if os.path.exists(path):
                os.add_dll_directory(path)
                Logger.info(f"✅ Added System CUDA: {path}")
                
    except Exception as e:
        Logger.warning(f"DLL Setup Warning: {e}")

# Call setup immediately
setup_dll_paths()

class AIInference:
    def __init__(self, cfg, capture_queue, result_queue):
        self.cfg = cfg
        self.capture_queue = capture_queue
        self.result_queue = result_queue
        self.session = None
        self.io_binding = None
        self.is_running = False
        self.last_target = None
        self.last_t = 0
        self.model_w = 640
        self.model_h = 640
        
        self._init_session()

    def _init_session(self):
        Logger.info("🧠 [THREAD] AI Engine Active...")
        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        # Priority List
        provider_sets = [
            ("TensorRT", [
                ('TensorrtExecutionProvider', {
                    'device_id': 0,
                    'trt_max_workspace_size': 2147483648,
                    'trt_fp16_enable': True,
                    'trt_engine_cache_enable': True,
                    'trt_engine_cache_path': 'trt_cache'
                }),
                ('CUDAExecutionProvider', {
                    'device_id': 0, 'arena_extend_strategy': 'kNextPowerOfTwo',
                    'cudnn_conv_algo_search': 'HEURISTIC', 'do_copy_in_default_stream': True,
                })
            ]),
            ("CUDA", [
                ('CUDAExecutionProvider', {
                    'device_id': 0, 'arena_extend_strategy': 'kNextPowerOfTwo',
                    'cudnn_conv_algo_search': 'HEURISTIC', 'do_copy_in_default_stream': True,
                })
            ]),
            ("DirectML", ['DmlExecutionProvider']),
            ("CPU", ['CPUExecutionProvider'])
        ]
        
        self.active_provider = "Unknown"
        
        model_source = self.cfg.get_model_data()
        if model_source is None:
            Logger.error("FATAL: Could not load model data (weights/best.onnx missing?)")
            return
            
        # Filter providers based on Config
        target = getattr(self.cfg, "AI_PROVIDER", "Auto")
        if target != "Auto":
            Logger.info(f"⚙️ User forced AI Provider: {target}")
            provider_sets = [p for p in provider_sets if p[0] == target]
            
        for name, providers in provider_sets:
            try:
                Logger.info(f"👉 Attempting to load AI with {name}...")
                self.session = ort.InferenceSession(model_source, sess_options=opts, providers=providers)
                
                # Test IO Binding if CUDA or TensorRT
                if name in ["CUDA", "TensorRT"]:
                    try:
                        self.io_binding = self.session.io_binding()
                        self.io_binding.bind_output('output0', 'cuda')
                        Logger.info(f"⚡ IO Binding Activated ({name})")
                    except Exception as e:
                        Logger.warning(f"Could not bind output for {name}: {e}. Falling back to standard path.")
                        self.io_binding = None
                else:
                    self.io_binding = None # No IO Binding for CPU/DML yet to keep it simple
                    
                self.active_provider = name
                Logger.info(f"✅ AI Engine Initialized successfully with {name}!")
                
                # Get input dimensions from the model dynamically
                try:
                    input_shape = self.session.get_inputs()[0].shape
                    # Format: [batch, channels, height, width]
                    self.model_h = int(input_shape[2])
                    self.model_w = int(input_shape[3])
                except Exception as e:
                    Logger.warning(f"Could not parse model input shape: {e}. Defaulting to 640x640")
                    self.model_h = 640
                    self.model_w = 640
                Logger.info(f"🧠 Model expects input size: {self.model_w}x{self.model_h}")
                return
                
            except Exception as e:
                Logger.warning(f"⚠️ {name} Initialization Failed: {e}")
                continue
                
        Logger.error("❌ ALL PROVIDERS FAILED! AI WILL NOT RUN.")
        self.session = None

    def reload(self):
        """Reloads the AI model from Config"""
        Logger.info("♻️ Reloading AI Engine...")
        if self.session:
            del self.session
            self.session = None
        import gc
        gc.collect()
        self._init_session()
        # NOTE: Do NOT call start() here - thread is already running


    def start(self):
        self.is_running = True
        self._loop()

    def _loop(self):
        if not self.session: return
        
        while self.is_running:
            try:
                img = self.capture_queue.get(timeout=1)
                
                cx, cy = self.cfg.FOV_WIDTH // 2, self.cfg.FOV_HEIGHT // 2
                
                # Snapshot for debug
                if not hasattr(self, "saved_debug"):
                    cv2.imwrite("debug_view_new.jpg", img)
                    Logger.info("📸 SNAPSHOT SAVED: 'debug_view_new.jpg'")
                    self.saved_debug = True
                
                t1 = time.perf_counter()
                
                # Preprocess: Pad/Crop to preserve native 1:1 details in ROI
                h_img, w_img = img.shape[:2]
                th, tw = self.model_h, self.model_w
                
                offset_x = 0
                offset_y = 0
                
                if h_img == th and w_img == tw:
                    img_input = cv2.dnn.blobFromImage(img, 1.0/255.0, (tw, th), swapRB=True, crop=False)
                elif h_img <= th and w_img <= tw:
                    # Pad smaller images
                    pad_h = th - h_img
                    pad_w = tw - w_img
                    top = pad_h // 2
                    bottom = pad_h - top
                    left = pad_w // 2
                    right = pad_w - left
                    padded_img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=[114, 114, 114])
                    img_input = cv2.dnn.blobFromImage(padded_img, 1.0/255.0, (tw, th), swapRB=True, crop=False)
                    offset_x = -left
                    offset_y = -top
                else:
                    # Crop larger or mixed size images
                    start_y = max(0, (h_img - th) // 2)
                    start_x = max(0, (w_img - tw) // 2)
                    cropped_img = img[start_y:start_y+th, start_x:start_x+tw]
                    ch, cw = cropped_img.shape[:2]
                    if ch < th or cw < tw:
                        pad_h = th - ch
                        pad_w = tw - cw
                        top = pad_h // 2
                        bottom = pad_h - top
                        left = pad_w // 2
                        right = pad_w - left
                        cropped_img = cv2.copyMakeBorder(cropped_img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=[114, 114, 114])
                        offset_x = start_x - left
                        offset_y = start_y - top
                    else:
                        offset_x = start_x
                        offset_y = start_y
                    img_input = cv2.dnn.blobFromImage(cropped_img, 1.0/255.0, (tw, th), swapRB=True, crop=False)
                
                t2 = time.perf_counter()
                
                # Inference
                if self.io_binding:
                    # CUDA Optimized Path
                    self.io_binding.bind_cpu_input('images', img_input)
                    self.session.run_with_iobinding(self.io_binding)
                    outputs = self.io_binding.copy_outputs_to_cpu()
                else:
                    # Standard Path (CPU / DirectML)
                    # ONNX Runtime expects input dict for run()
                    outputs = self.session.run(None, {'images': img_input})

                t3 = time.perf_counter()
                
                # Postprocess
                preds = outputs[0][0].T
                
                if np.isnan(preds).any():
                    continue

                scores = np.max(preds[:, 4:], axis=1)
                mask = scores > self.cfg.CONF_THRESHOLD
                
                t4 = time.perf_counter()
                stats = {
                    "pre_ms": (t2 - t1) * 1000,
                    "infer_ms": (t3 - t2) * 1000,
                    "post_ms": (t4 - t3) * 1000,
                    "ai_ms": (t4 - t1) * 1000
                }
                Logger.log_fps(stats)

                if not np.any(mask):
                    if self.result_queue.full(): self.result_queue.get_nowait()
                    self.result_queue.put(None); continue
                    
                boxes, classes = preds[mask, :4], np.argmax(preds[mask, 4:], axis=1)
                tx, ty = boxes[:, 0] + offset_x, boxes[:, 1] + offset_y
                w, h = boxes[:, 2], boxes[:, 3]
                
                # Target Selection Logic
                dists = np.sqrt((tx - cx)**2 + (ty - cy)**2)
                weights = dists.copy()
                
                # Dynamic Priority & Offset Logic for PUBG
                import ctypes
                click_on = (ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
                game_mode = getattr(self.cfg, "GAME_MODE", "PUBG")
                
                if not hasattr(self, "fire_start"): self.fire_start = 0
                
                if click_on:
                    if self.fire_start == 0: self.fire_start = time.time()
                    duration = time.time() - self.fire_start
                else:
                    self.fire_start = 0
                    duration = 0

                if game_mode == "PUBG":
                    if duration > 0.2:
                        # After 0.2s spraying -> Lock BODY (1), aim at center
                        weights[classes == 1] -= 1000
                        # Ensure body targets aim at center
                        if np.any(classes == 1):
                            idx = (classes == 1)
                            h_scaled = h[idx]
                            ty[idx] = (ty[idx] - h_scaled/2) + (h_scaled * 50 / 100)
                    else:
                        # 0-0.2s: Prioritize Head, aim at center (no offset)
                        weights[classes == 0] -= 500
                        # No offset needed - aim at head center
                else:
                    # Default: Head Priority (Valorant, etc)
                    weights[classes == 0] -= 500 
                
                now = time.time()
                if self.last_target and (now - self.last_t < 0.5):
                    prev_dist = np.sqrt((tx - self.last_target[0])**2 + (ty - self.last_target[1])**2)
                    weights[prev_dist < 40] -= self.cfg.TARGET_LOCK_STRENGTH
                
                best = np.argmin(weights)
                self.last_target = (tx[best], ty[best]); self.last_t = now
                
                if self.result_queue.full(): self.result_queue.get_nowait()
                # PASS CLASS ID to MouseController
                self.result_queue.put((tx[best], ty[best], w[best], h[best], classes[best]))

            except queue.Empty:
                continue
            except Exception as e:
                Logger.error(f"AI LOOP ERROR: {e}")
                time.sleep(0.01)

    def stop(self):
        self.is_running = False
