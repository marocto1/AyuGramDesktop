import threading

STAGE_QUEUE = "stageQueue"
GLOBAL_QUEUE = "globalQueue"
CACHE_CLEAR_QUEUE = "cacheClearQueue"
SEARCH_QUEUE = "searchQueue"
PHONE_BOOK_QUEUE = "phoneBookQueue"
THEME_QUEUE = "themeQueue"
EXTERNAL_NETWORK_QUEUE = "externalNetworkQueue"
PLUGINS_QUEUE = "pluginsQueue"

def run_on_queue(callback, queue=PLUGINS_QUEUE, delay=0):
    timer = threading.Timer(max(0, delay) / 1000.0, callback)
    timer.daemon = True
    timer.start()
    return timer

def get_queue_by_name(name):
    allowed = {STAGE_QUEUE, GLOBAL_QUEUE, CACHE_CLEAR_QUEUE, SEARCH_QUEUE,
        PHONE_BOOK_QUEUE, THEME_QUEUE, EXTERNAL_NETWORK_QUEUE, PLUGINS_QUEUE}
    return name if name in allowed else None

def _unsupported(name):
    raise NotImplementedError(
        f"client_utils.{name} needs the Telegram Desktop bridge and is not available in this build yet"
    )

def send_request(*args, **kwargs): return _unsupported("send_request")
def send_text(*args, **kwargs): return _unsupported("send_text")
def send_photo(*args, **kwargs): return _unsupported("send_photo")
def send_document(*args, **kwargs): return _unsupported("send_document")
def send_video(*args, **kwargs): return _unsupported("send_video")
def send_audio(*args, **kwargs): return _unsupported("send_audio")
def send_message(*args, **kwargs): return _unsupported("send_message")

def get_last_fragment(): return None
def get_account_instance(account=None): return None
def get_messages_controller(account=None): return None
def get_contacts_controller(account=None): return None
def get_media_data_controller(account=None): return None
def get_connections_manager(account=None): return None
def get_location_controller(account=None): return None
def get_notifications_controller(account=None): return None
def get_messages_storage(account=None): return None
def get_send_messages_helper(account=None): return None
def get_file_loader(account=None): return None
def get_secret_chat_helper(account=None): return None
def get_download_controller(account=None): return None
def get_notifications_settings(account=None): return None
def get_notification_center(account=None): return None
def get_media_controller(): return None
def get_user_config(account=None): return None
