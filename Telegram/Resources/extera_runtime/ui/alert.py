class AlertDialogBuilder:
    def __init__(self,*args,**kwargs): self.values={}
    def __getattr__(self,name):
        if name.startswith("set"):
            def setter(*args,**kwargs):
                self.values[name]=(args,kwargs); return self
            return setter
        raise AttributeError(name)
    def show(self): return self
