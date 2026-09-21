import locale
import sys
import types

class NullProxy:
    def __init__(self, name="proxy", **values):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_values", dict(values))
    def __getattr__(self, key):
        values=object.__getattribute__(self, "_values")
        if key in values: return values[key]
        return NullProxy(f"{self._name}.{key}")
    def __setattr__(self, key, value):
        if key.startswith("_"): object.__setattr__(self, key, value)
        else: object.__getattribute__(self, "_values")[key]=value
    def __call__(self, *args, **kwargs): return NullProxy(self._name)
    def __iter__(self): return iter(())
    def __len__(self): return 0
    def __bool__(self): return False
    def __int__(self): return 0
    def __index__(self): return 0
    def __str__(self): return ""
    def __repr__(self): return f"<DesktopProxy {self._name}>"
    def clear(self): object.__getattribute__(self, "_values").clear()
    def size(self): return len(self)
    def get(self, key, default=None): return object.__getattribute__(self, "_values").get(key, default)

def generic_class(name):
    class Generic(NullProxy):
        TYPE=object
        def __init__(self, *args, **kwargs): super().__init__(name)
        @classmethod
        def getInstance(cls, *args, **kwargs): return None
    Generic.__name__=name.rsplit(".",1)[-1].replace("$","_")
    return Generic

class Boolean:
    TYPE=bool
    def __new__(cls, value=False): return bool(value)
class Integer:
    TYPE=int; MAX_VALUE=2**31-1; MIN_VALUE=-(2**31)
    def __new__(cls, value=0): return int(value)
class Long:
    TYPE=int; MAX_VALUE=2**63-1; MIN_VALUE=-(2**63)
    def __new__(cls, value=0): return int(value)

class ArrayList(list):
    def add(self, value): self.append(value); return True
    def size(self): return len(self)
    def get(self, index): return self[index]
    def set(self, index, value):
        old=self[index]; self[index]=value; return old

class HashMap(dict):
    def put(self, key, value):
        old=self.get(key); self[key]=value; return old
    def containsKey(self, key): return key in self
    def keySet(self): return list(self.keys())
    def size(self): return len(self)
class ConcurrentHashMap(HashMap): pass

class Bundle(dict):
    def putString(self, key, value): self[key]=str(value)
    def getString(self, key, default=None): return self.get(key, default)
    def putInt(self, key, value): self[key]=int(value)
    def getInt(self, key, default=0): return int(self.get(key, default))

class _Locale:
    def __init__(self, language=None):
        detected=(language or locale.getdefaultlocale()[0] or "en").split("_")[0]
        self._language=detected
    def getLanguage(self): return self._language
class LocaleController:
    _instance=None
    @classmethod
    def getInstance(cls):
        if cls._instance is None: cls._instance=cls()
        return cls._instance
    def getCurrentLocale(self): return _Locale()
    def getCurrentLocaleInfo(self): return NullProxy("LocaleInfo", pluralLangCode=_Locale().getLanguage())
class UserConfig:
    MAX_ACCOUNT_COUNT=4
    @classmethod
    def getInstance(cls, account=0): return NullProxy("UserConfig")
class MessagesController:
    @classmethod
    def getInstance(cls, account=0): return None
class Utilities:
    class Callback: pass

class TLObject:
    def __init__(self, *args, **kwargs):
        for key,value in kwargs.items(): setattr(self,key,value)
class _TLRPC:
    def __getattr__(self, name): return generic_class("TLRPC."+name)
TLRPC=_TLRPC()

class View:
    VISIBLE=0; INVISIBLE=4; GONE=8
class _LayoutParams:
    FLAG_SECURE=0x00002000
class WindowManager:
    LayoutParams=_LayoutParams

def _module(name, attrs=None, dynamic=False):
    module=types.ModuleType(name)
    module.__dict__.update(attrs or {})
    if dynamic:
        def __getattr__(key):
            value=generic_class(name+"."+key)
            module.__dict__[key]=value
            return value
        module.__getattr__=__getattr__
    return module

def install_compat_modules():
    java=_module("java", dynamic=True); java.__path__=[]
    java.jclass=lambda name: generic_class(name)
    java.cast=lambda _type,value:value
    java.dynamic_proxy=lambda base: base if isinstance(base,type) else object
    java.jint=int
    lang=_module("java.lang", {"Boolean":Boolean,"Integer":Integer,"Long":Long}, True)
    util=_module("java.util", {"ArrayList":ArrayList,"HashMap":HashMap}, True); util.__path__=[]
    concurrent=_module("java.util.concurrent", {"ConcurrentHashMap":ConcurrentHashMap}, True)
    android=_module("android", dynamic=True); android.__path__=[]
    android_os=_module("android.os", {"Bundle":Bundle}, True)
    android_view=_module("android.view", {"View":View,"WindowManager":WindowManager}, True)
    android_content=_module("android.content", dynamic=True)
    android_util=_module("android.util", dynamic=True)
    android_text=_module("android.text", dynamic=True)
    org=_module("org"); org.__path__=[]
    telegram=_module("org.telegram"); telegram.__path__=[]
    messenger=_module("org.telegram.messenger", {
        "LocaleController":LocaleController, "UserConfig":UserConfig,
        "MessagesController":MessagesController, "Utilities":Utilities,
    }, True)
    tgnet=_module("org.telegram.tgnet", {"TLObject":TLObject,"TLRPC":TLRPC}, True)
    for name,module in {
        "java":java,"java.lang":lang,"java.util":util,"java.util.concurrent":concurrent,
        "android":android,"android.os":android_os,"android.view":android_view,
        "android.content":android_content,"android.util":android_util,"android.text":android_text,
        "org":org,"org.telegram":telegram,"org.telegram.messenger":messenger,"org.telegram.tgnet":tgnet,
    }.items():
        sys.modules.setdefault(name,module)
