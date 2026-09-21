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

class JavaMemberProxy(NullProxy):
    def __init__(self, name="member"):
        super().__init__(name)
    def setAccessible(self, value=True):
        return None
    def invoke(self, *args, **kwargs):
        return None
    def get(self, *args, **kwargs):
        return None
    def set(self, *args, **kwargs):
        return None

class JavaClassProxy(NullProxy):
    TYPE=object
    def __init__(self, name):
        super().__init__(name)
        self._class_name=name
    def getClass(self):
        return self
    def getName(self):
        return self._class_name
    def getDeclaredMethod(self, name, *args):
        return JavaMemberProxy(f"{self._class_name}.{name}")
    def getMethod(self, name, *args):
        return JavaMemberProxy(f"{self._class_name}.{name}")
    def getDeclaredField(self, name):
        return JavaMemberProxy(f"{self._class_name}.{name}")
    def getField(self, name):
        return JavaMemberProxy(f"{self._class_name}.{name}")
    def newInstance(self, *args, **kwargs):
        return NullProxy(self._class_name + ".instance")

def generic_class(name):
    class Generic(NullProxy):
        TYPE=object
        def __init__(self, *args, **kwargs): super().__init__(name)
        @classmethod
        def getInstance(cls, *args, **kwargs): return cls()
        @classmethod
        def getClass(cls): return JavaClassProxy(name)
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
    def add(self, *args):
        if len(args) == 1:
            self.append(args[0])
        elif len(args) == 2:
            self.insert(int(args[0]), args[1])
        else:
            raise TypeError("ArrayList.add expects value or index, value")
        return True
    def size(self): return len(self)
    def get(self, index): return self[index]
    def set(self, index, value):
        old=self[index]; self[index]=value; return old
    def isEmpty(self): return not self

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
    def __init__(self):
        self._classes = {}
    def __getattr__(self, name):
        value = self._classes.get(name)
        if value is None:
            value = generic_class("TLRPC."+name)
            self._classes[name] = value
        return value
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

class AlertDialog(NullProxy):
    def __init__(self, *args, **kwargs):
        super().__init__("AlertDialog")
    def setMessage(self, value): return self
    def show(self): return self
    def dismiss(self): return None

class ByteBuffer(bytearray):
    @classmethod
    def wrap(cls, data): return cls(data)

def install_compat_modules():
    java=_module("java", dynamic=True); java.__path__=[]
    java.jclass=lambda name: JavaClassProxy(name)
    java.cast=lambda _type,value:value
    java.dynamic_proxy=lambda base: base if isinstance(base,type) else object
    java.jint=int
    java.jlong=int
    java.jfloat=float
    java.jdouble=float
    java.jboolean=bool
    def _jarray(component):
        def create(value):
            if isinstance(value, int):
                default = False if component is bool else 0.0 if component is float else 0 if component is int else None
                return [default for _ in range(value)]
            return list(value)
        return create
    java.jarray=_jarray
    lang=_module("java.lang", {"Boolean":Boolean,"Integer":Integer,"Long":Long}, True); lang.__path__=[]
    util=_module("java.util", {"ArrayList":ArrayList,"HashMap":HashMap}, True); util.__path__=[]
    concurrent=_module("java.util.concurrent", {"ConcurrentHashMap":ConcurrentHashMap}, True)
    android=_module("android", dynamic=True); android.__path__=[]
    android_os=_module("android.os", {"Bundle":Bundle}, True)
    android_view=_module("android.view", {"View":View,"WindowManager":WindowManager}, True)
    android_content=_module("android.content", dynamic=True)
    android_util=_module("android.util", dynamic=True)
    android_text=_module("android.text", dynamic=True); android_text.__path__=[]
    android_text_style=_module("android.text.style", dynamic=True)
    android_graphics=_module("android.graphics", dynamic=True); android_graphics.__path__=[]
    android_graphics_drawable=_module("android.graphics.drawable", dynamic=True)
    android_widget=_module("android.widget", dynamic=True)
    android_app=_module("android.app", {"Activity":generic_class("android.app.Activity")}, True)
    java_nio=_module("java.nio", {"ByteBuffer":ByteBuffer}, True)
    java_lang_ref=_module("java.lang.ref", dynamic=True)
    java_net=_module("java.net", dynamic=True)
    dalvik=_module("dalvik"); dalvik.__path__=[]
    dalvik_system=_module("dalvik.system", {
        "InMemoryDexClassLoader":generic_class("dalvik.system.InMemoryDexClassLoader"),
        "DexClassLoader":generic_class("dalvik.system.DexClassLoader"),
    }, True)
    org=_module("org"); org.__path__=[]
    telegram=_module("org.telegram"); telegram.__path__=[]
    messenger=_module("org.telegram.messenger", {
        "LocaleController":LocaleController, "UserConfig":UserConfig,
        "MessagesController":MessagesController, "Utilities":Utilities,
    }, True)
    tgnet=_module("org.telegram.tgnet", {"TLObject":TLObject,"TLRPC":TLRPC}, True)
    telegram_ui=_module("org.telegram.ui", dynamic=True); telegram_ui.__path__=[]
    telegram_actionbar=_module("org.telegram.ui.ActionBar", {"AlertDialog":AlertDialog}, True)
    telegram_components=_module("org.telegram.ui.Components", dynamic=True)
    xposed_root=_module("de"); xposed_root.__path__=[]
    xposed_robv=_module("de.robv"); xposed_robv.__path__=[]
    xposed_android=_module("de.robv.android"); xposed_android.__path__=[]
    xposed=_module("de.robv.android.xposed", dynamic=True)
    com=_module("com"); com.__path__=[]
    exteragram=_module("com.exteragram", dynamic=True); exteragram.__path__=[]
    for name,module in {
        "java":java,"java.lang":lang,"java.util":util,"java.util.concurrent":concurrent,
        "android":android,"android.os":android_os,"android.view":android_view,
        "android.content":android_content,"android.util":android_util,"android.text":android_text,
        "android.text.style":android_text_style,"android.graphics":android_graphics,
        "android.graphics.drawable":android_graphics_drawable,"android.widget":android_widget,
        "android.app":android_app,"java.nio":java_nio,"java.lang.ref":java_lang_ref,"java.net":java_net,
        "dalvik":dalvik,"dalvik.system":dalvik_system,
        "org":org,"org.telegram":telegram,"org.telegram.messenger":messenger,"org.telegram.tgnet":tgnet,
        "org.telegram.ui":telegram_ui,"org.telegram.ui.ActionBar":telegram_actionbar,
        "org.telegram.ui.Components":telegram_components,
        "de":xposed_root,"de.robv":xposed_robv,"de.robv.android":xposed_android,
        "de.robv.android.xposed":xposed,
        "com":com,"com.exteragram":exteragram,
    }.items():
        sys.modules.setdefault(name,module)
