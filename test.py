class GoodFormat:
    def __format__(self, format_spec):
        return f"<Formatted:{format_spec}>"
"{:*^15}".format(GoodFormat())
class Foo1:
    def __str__(self): return "hello"
"{:*^15}".format(Foo1())