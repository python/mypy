lib_prefix: get_module_group_prefix -> context.group_map -> modify context.group_deps when necessary

private_name: NameGenerator translations/module_map

this also helps to solve native_function_name(which depends on NameGenerator)

cast type generation

remaining `LoadStatic`:

load_globals_dict
  return self.add(LoadStatic(dict_rprimitive, 'globals', self.module_name))

gen_arg_defaults
  return builder.add(LoadStatic(target.type, name, builder.module_name))

allocate_class:

template = builder.add(LoadStatic(object_rprimitive, cdef.name + "_template", builder.module_name, NAMESPACE_TYPE))

load_static_checked:
value = self.add(LoadStatic(typ, identifier, module_name, namespace, line=line))

def load_module(self, name: str) -> Value:
      return self.add(LoadStatic(object_rprimitive, name, namespace=NAMESPACE_MODULE))

def load_native_type_object(self, fullname: str) -> Value:
    module, name = fullname.rsplit('.', 1)
    return self.add(LoadStatic(object_rprimitive, name, module, NAMESPACE_TYPE))