from mypy.plugin import CallableType, MethodSigContext, Plugin

class FullyQualifiedTestPlugin(Plugin):
    def get_method_signature_hook(self, fullname):
        # Ensure that all names are fully qualified
        if 'FullyQualifiedTest' in fullname:
            assert fullname.startswith('__main__.') and not ' of ' in fullname, fullname
            return my_hook
    
        return None

def my_hook(ctx: MethodSigContext) -> CallableType:
    return ctx.default_signature.copy_modified(ret_type=ctx.api.named_generic_type('builtins.int', []))

def plugin(version):
    return FullyQualifiedTestPlugin
