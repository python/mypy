# Stubs for weakref

# NOTE: These are incomplete!

class ReferenceType<t>:
    # TODO members
    pass

ReferenceType<t> ref<t>(t o,
                        func<any(ReferenceType<t>)> callback=None): pass

# TODO callback
t proxy<t>(t object): pass

class WeakValueDictionary<kt, vt>:
    # TODO tuple iterable argument?
    void __init__(self): pass
    void __init__(self, Mapping<kt, vt> map): pass
    
    int __len__(self): pass    
    vt __getitem__(self, kt k): pass
    void __setitem__(self, kt k, vt v): pass
    void __delitem__(self, kt v): pass
    bool __contains__(self, object o): pass
    Iterator<kt> __iter__(self): pass
    str __str__(self): pass
    
    void clear(self): pass
    dict<kt, vt> copy(self): pass
    vt get(self, kt k): pass
    vt get(self, kt k, vt default): pass
    vt pop(self, kt k): pass
    vt pop(self, kt k, vt default): pass
    tuple<kt, vt> popitem(self): pass
    vt setdefault(self, kt k): pass
    vt setdefault(self, kt k, vt default): pass    
    void update(self, Mapping<kt, vt> m): pass
    void update(self, Iterable<tuple<kt, vt>> m): pass
    # NOTE: incompatible with Mapping
    Iterator<kt> keys(self): pass
    Iterator<vt> values(self): pass
    Iterator<tuple<kt, vt>> items(self): pass

    # TODO return type
    Iterable<any> valuerefs(self): pass
