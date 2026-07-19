import time

class Logger:
    @staticmethod
    def info(msg):
        print(f"INFO: {msg}")

    @staticmethod
    def warning(msg):
        print(f"⚠️ WARNING: {msg}")

    @staticmethod
    def error(msg):
        print(f"❌ ERROR: {msg}")

    @staticmethod
    def success(msg):
        print(f"✅ {msg}")

    @staticmethod
    def log_fps(stats):
        if time.time() % 3 < 0.1: # Throttle logs
             print(f"📊 [PROFILER] Pre:{stats.get('pre_ms',0):.1f} | Infer:{stats.get('infer_ms',0):.1f} | Post:{stats.get('post_ms',0):.1f} | Total:{stats.get('ai_ms',0):.1f}ms")
