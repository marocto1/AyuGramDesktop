from android_utils import log
class BulletinHelper:
    @staticmethod
    def show_error(text, fragment=None): log(f"[bulletin:error] {text}")
    @staticmethod
    def show_info(text, fragment=None): log(f"[bulletin:info] {text}")
    @staticmethod
    def show_success(text, fragment=None): log(f"[bulletin:success] {text}")
