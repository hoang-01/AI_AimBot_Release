import cv2
import queue
import time
from src.utils.logger import Logger

class Reflex:
    def __init__(self, cfg, reflex_queue, shared_state):
        self.cfg = cfg
        self.reflex_queue = reflex_queue
        self.state = shared_state
        self.is_running = False

    def start(self):
        self.is_running = True
        self._loop()

    def _loop(self):
        Logger.info("⚡ [THREAD] Reflex Trigger (Color) Active...")
        while self.is_running:
            try:
                # OPTIMIZED: 10ms timeout for instant reflex
                img = self.reflex_queue.get(timeout=0.01)
                hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                mask = cv2.inRange(hsv, self.cfg.PURPLE_LOW, self.cfg.PURPLE_HIGH)
                pixel_count = cv2.countNonZero(mask)
                
                if pixel_count > 0:
                    self.state["reflex_fire"] = True
                else:
                    self.state["reflex_fire"] = False
                    
            except queue.Empty:
                self.state["reflex_fire"] = False
                continue
            except Exception as e:
                Logger.error(f"REFLEX ERROR: {e}")
                time.sleep(0.01)

    def stop(self):
        self.is_running = False
