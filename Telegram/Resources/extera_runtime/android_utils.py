import threading

def log(message):
    print(f"[plugin] {message}")

def run_on_ui_thread(callback, delay=0):
    if delay and delay > 0:
        timer = threading.Timer(delay / 1000.0, callback)
        timer.daemon = True
        timer.start()
        return timer
    return callback()

def run_on_ui_thread_delayed(callback, delay=0):
    return run_on_ui_thread(callback, delay)

def copy_to_clipboard(*args, **kwargs):
    raise NotImplementedError("Clipboard bridge is not available in Desktop API 2 yet")
