"""Facilities and constants for generating error messages during type checking.

The type checker itself does not deal with message string literals to
improve code clarity and to simplify localization (in the future)."""

import re

from mypy.errors import Errors
from mypy.types import (
    Type, Callable, Instance, TypeVar, TupleType, Void, NoneTyp, AnyType,
    Overloaded, FunctionLike
)
from mypy.nodes import (
    TypeInfo, Context, op_methods, FuncDef, reverse_type_aliases
)


# Constants that represent simple type checker error message, i.e. messages
# that do not have any parameters.

NO_RETURN_VALUE_EXPECTED = 'No return value expected'
INCOMPATIBLE_RETURN_VALUE_TYPE = 'Incompatible return value type'
RETURN_VALUE_EXPECTED = 'Return value expected'
BOOLEAN_VALUE_EXPECTED = 'Boolean value expected'
BOOLEAN_EXPECTED_FOR_IF = 'Boolean value expected for if condition'
BOOLEAN_EXPECTED_FOR_WHILE = 'Boolean value expected for while condition'
BOOLEAN_EXPECTED_FOR_UNTIL = 'Boolean value expected for until condition'
BOOLEAN_EXPECTED_FOR_NOT = 'Boolean value expected for not operand'
INVALID_EXCEPTION_TYPE = 'Invalid exception type'
INVALID_RETURN_TYPE_FOR_YIELD = \
                         'Iterator function return type expected for "yield"'
INCOMPATIBLE_TYPES = 'Incompatible types'
INCOMPATIBLE_TYPES_IN_ASSIGNMENT = 'Incompatible types in assignment'
INIT_MUST_NOT_HAVE_RETURN_TYPE = 'Cannot define return type for "__init__"'
GETTER_TYPE_INCOMPATIBLE_WITH_SETTER = \
                                     'Type of getter incompatible with setter'
TUPLE_INDEX_MUST_BE_AN_INT_LITERAL = 'Tuple index must an integer literal'
TUPLE_INDEX_OUT_OF_RANGE = 'Tuple index out of range'
TYPE_CONSTANT_EXPECTED = 'Type "Constant" or initializer expected'
INCOMPATIBLE_PAIR_ITEM_TYPE = 'Incompatible Pair item type'
INVALID_TYPE_APPLICATION_TARGET_TYPE = 'Invalid type application target type'
INCOMPATIBLE_TUPLE_ITEM_TYPE = 'Incompatible tuple item type'
INCOMPATIBLE_KEY_TYPE = 'Incompatible dictionary key type'
INCOMPATIBLE_VALUE_TYPE = 'Incompatible dictionary value type'
NEED_ANNOTATION_FOR_VAR = 'Need type annotation for variable'
ITERABLE_EXPECTED = 'Iterable expected'
INCOMPATIBLE_TYPES_IN_FOR = 'Incompatible types in for statement'
INCOMPATIBLE_ARRAY_VAR_ARGS = 'Incompatible variable arguments in call'
INVALID_SLICE_INDEX = 'Slice index must be an integer or None'
CANNOT_INFER_LAMBDA_TYPE = 'Cannot infer type of lambda'
CANNOT_ACCESS_INIT = 'Cannot access "__init__" directly'
CANNOT_ASSIGN_TO_METHOD = 'Cannot assign to a method'
CANNOT_ASSIGN_TO_TYPE = 'Cannot assign to a type'
INCONSISTENT_ABSTRACT_OVERLOAD = \
              'Overloaded method has both abstract and non-abstract variants'


class MessageBuilder:
    """Helper class for reporting type checker error messages with parameters.
    The methods of this class need to be provided with the context within a
    file; the errors member manages the wider context.
    
    IDEA: Support a 'verbose mode' that includes full information about types
          in error messages and that may otherwise produce more detailed error
          messages.
    """
    # Report errors using this instance. It knows about the current file and
    # import context.
    Errors errors
    # Number of times errors have been disabled.
    int disable_count
    
    void __init__(self, Errors errors):
        self.errors = errors
        self.disable_count = 0

    #
    # Helpers
    #

    void disable_errors(self):
        self.disable_count += 1

    void enable_errors(self):
        self.disable_count -= 1
    
    void fail(self, str msg, Context context):
        """Report an error message (unless disabled)."""
        if self.disable_count <= 0:
            self.errors.report(context.get_line(), msg.strip())
    
    str format(self, Type typ):
        """Convert a type to a relatively short string that is
        suitable for error messages. Mostly behave like format_simple
        below, but never return an empty string.
        """
        s = self.format_simple(typ)
        if s != '':
            # If format_simple returns a non-trivial result, use that.
            return s
        elif isinstance(typ, FunctionLike):
            func = (FunctionLike)typ
            if func.is_type_obj():
                # The type of a type object type can be derived from the
                # return type (this always works).
                itype = (Instance)func.items()[0].ret_type
                return self.format(itype)                
            else:
                # Use a simple representation for function types; proper
                # function types may result in long and difficult-to-read
                # error messages.
                return 'function'
        else:
            # Default case; we simply have to return something meaningful here.
            return 'object'
    
    str format_simple(self, Type typ):
        """Convert simple types to string that is suitable for error messages,
        otherwise return "". Try to keep the length of the result relatively
        short to avoid overly long error messages.
        
        Examples:
          builtins.int -> 'int'
          Any type -> 'Any'
          void -> None
          function type -> "" (empty string)
        """
        if isinstance(typ, Instance):
            itype = (Instance)typ
            # Get the short name of the type.
            base_str = itype.type.name()
            if itype.args == []:
                # No type arguments. Place the type name in quotes to avoid
                # potential for confusion: otherwise, the type name could be
                # interpreted as a normal word.
                return '"{}"'.format(base_str)
            elif itype.type.fullname() in reverse_type_aliases:
                alias = reverse_type_aliases[itype.type.fullname()]
                alias = alias.split('.')[-1]
                items = [strip_quotes(self.format(arg)) for arg in itype.args]
                return '{}[{}]'.format(alias, ', '.join(items))
            else:
                # There are type arguments. Convert the arguments to strings
                # (using format() instead of format_simple() to avoid empty
                # strings). If the result is too long, replace arguments
                # with [...].
                str[] a = []
                for arg in itype.args:
                    a.append(strip_quotes(self.format(arg)))
                s = ', '.join(a)
                if len((base_str + s)) < 25:
                    return '{}[{}]'.format(base_str, s)
                else:
                    return '{}[...]'.format(base_str)
        elif isinstance(typ, TypeVar):
            # This is similar to non-generic instance types.
            return '"{}"'.format(((TypeVar)typ).name)
        elif isinstance(typ, TupleType):
            items = []
            for t in ((TupleType)typ).items:
                items.append(strip_quotes(self.format(t)))
            s = '"Tuple[{}]"'.format(', '.join(items))
            if len(s) < 30:
                return s
            else:
                return 'tuple'
        elif isinstance(typ, Void):
            return 'None'
        elif isinstance(typ, NoneTyp):
            return 'None'
        elif isinstance(typ, AnyType):
            return '"Any"'
        elif typ is None:
            raise RuntimeError('Type is None')
        else:
            # No simple representation for this type that would convey very
            # useful information. No need to mention the type explicitly in a
            # message.
            return ''

    #
    # Specific operations
    #
    
    # The following operations are for genering specific error messages. They
    # get some information as arguments, and they build an error message based
    # on them.
    
    Type has_no_attr(self, Type typ, str member, Context context):
        """Report a missing or non-accessible member.  The type
        argument is the base type. If member corresponds to an
        operator, use the corresponding operator name in the
        messages. Return type Any.
        """
        if (isinstance(typ, Instance) and
                ((Instance)typ).type.has_readable_member(member)):
            self.fail('Member "{}" is not assignable'.format(member), context)
        elif isinstance(typ, Void):
            self.check_void(typ, context)
        elif member == '__contains__':
            self.fail('Unsupported right operand type for in ({})'.format(
                self.format(typ)), context)
        elif member in op_methods.values():
            # Access to a binary operator member (e.g. _add). This case does
            # not handle indexing operations.
            for op, method in op_methods.items():
                if method == member:
                    self.unsupported_left_operand(op, typ, context)
                    break
        elif member == '__neg__':
            self.fail('Unsupported operand type for unary - ({})'.format(
                self.format(typ)), context)
        elif member == '__invert__':
            self.fail('Unsupported operand type for ~ ({})'.format(
                self.format(typ)), context)
        elif member == '__getitem__':
            # Indexed get.
            self.fail('Value of type {} is not indexable'.format(
                self.format(typ)), context)
        elif member == '__setitem__':
            # Indexed set.
            self.fail('Unsupported target for indexed assignment', context)
        else:
            # The non-special case: a missing ordinary attribute.
            self.fail('{} has no attribute "{}"'.format(self.format(typ),
                                                        member), context)
        return AnyType()
    
    void unsupported_operand_types(self, str op, any left_type, any right_type,
                                   Context context):
        """Report unsupported operand types for a binary operation.
        Types can be Type objects or strings.
        """
        if isinstance(left_type, Void) or isinstance(right_type, Void):
            self.check_void(left_type, context)
            self.check_void(right_type, context)
            return 
        
        str left_str
        if isinstance(left_type, str):
            left_str = left_type
        else:
            left_str = self.format(left_type)
        
        str right_str
        if isinstance(right_type, str):
            right_str = right_type
        else:
            right_str = self.format(right_type)
        
        msg = 'Unsupported operand types for {} ({} and {})'.format(
                                                    op, left_str, right_str)
        self.fail(msg, context)
    
    void unsupported_left_operand(self, str op, Type typ, Context context):
        if not self.check_void(typ, context):
            self.fail('Unsupported left operand type for {} ({})'.format(
                op, self.format(typ)), context)
    
    void type_expected_as_right_operand_of_is(self, Context context):
        self.fail('Type expected as right operand of "is"', context)
    
    Type not_callable(self, Type typ, Context context):
        self.fail('{} not callable'.format(self.format(typ)), context)
        return AnyType()
    
    void incompatible_argument(self, int n, Callable callee, Type arg_type,
                               Context context):
        """Report an error about an incompatible type arg_type for
        argument n when calling a value with type callee. If the
        callee represents a method that corresponds to an operator,
        use the corresponding operator name in the messages.
        """
        target = ''
        if callee.name:
            name = callee.name
            base = extract_type(name)
            
            for op, method in op_methods.items():
                if name.startswith('"{}" of'.format(method)):
                    if op == 'in':
                        self.unsupported_operand_types(op, arg_type, base,
                                                       context)
                    else:
                        self.unsupported_operand_types(op, base, arg_type,
                                                       context)
                    return 
            
            if name.startswith('"__getitem__" of'):
                self.invalid_index_type(arg_type, base, context)
                return 
            
            if name.startswith('"__setitem__" of'):
                if n == 1:
                    self.invalid_index_type(arg_type, base, context)
                else:
                    self.fail(INCOMPATIBLE_TYPES_IN_ASSIGNMENT, context)
                return 
            
            target = 'to {} '.format(name)
        
        str msg
        if callee.name == '<list>':
            name = callee.name[1:-1]
            msg = '{} item {} has incompatible type {}'.format(
                name[0].upper() + name[1:], n, self.format_simple(arg_type))
        elif callee.name == '<list-comprehension>':
            msg = 'List comprehension has incompatible type {}[]'.format(
                                  strip_quotes(self.format_simple(arg_type)))
        elif callee.name == '<generator>':
            msg = 'Generator has incompatible item type {}'.format(
                                              self.format_simple(arg_type))
        else:
            msg = 'Argument {} {}has incompatible type {}'.format(
                n, target, self.format_simple(arg_type))
        self.fail(msg, context)
    
    void invalid_index_type(self, Type index_type, str base_str,
                            Context context):
        self.fail('Invalid index type {} for {}'.format(
            self.format(index_type), base_str), context)
    
    void invalid_argument_count(self, Callable callee, int num_args,
                                Context context):
        if num_args < len(callee.arg_types):
            self.too_few_arguments(callee, context)
        else:
            self.too_many_arguments(callee, context)
    
    void too_few_arguments(self, Callable callee, Context context):
        msg = 'Too few arguments'
        if callee.name:
            msg += ' for {}'.format(callee.name)
        self.fail(msg, context)
    
    void too_many_arguments(self, Callable callee, Context context):
        msg = 'Too many arguments'
        if callee.name:
            msg += ' for {}'.format(callee.name)
        self.fail(msg, context)
    
    void too_many_positional_arguments(self, Callable callee, Context context):
        msg = 'Too many positional arguments'
        if callee.name:
            msg += ' for {}'.format(callee.name)
        self.fail(msg, context)

    void unexpected_keyword_argument(self, Callable callee, str name,
                                     Context context):
        msg = 'Unexpected keyword argument "{}"'.format(name)
        if callee.name:
            msg += ' for {}'.format(callee.name)
        self.fail(msg, context)            

    void duplicate_argument_value(self, Callable callee, int index,
                                  Context context):
        f = 'Function'
        if callee.name:
            f = '{}'.format(callee.name)
        self.fail('{} gets multiple values for keyword argument "{}"'.
                  format(f, callee.arg_names[index]), context)
    
    void does_not_return_value(self, Type void_type, Context context):
        """Report an error about a void type in a non-void
        context. The first argument must be a void type. If the void
        type has a source in it, report it in the error message. This
        allows giving messages such as 'Foo does not return a value'.
        """
        if ((Void)void_type).source is None:
            self.fail('Function does not return a value', context)
        else:
            self.fail('{} does not return a value'.format(
                capitalize(((Void)void_type).source)), context)
    
    void no_variant_matches_arguments(self, Overloaded overload,
                                      Context context):
        if overload.name():
            self.fail('No overload variant of {} matches argument types'
                      .format(overload.name()), context)
        else:
            self.fail('No overload variant matches argument types', context)
    
    void function_variants_overlap(self, int n1, int n2, Context context):
        self.fail('Function signature variants {} and {} overlap'.format(
            n1 + 1, n2 + 1), context)
    
    void invalid_cast(self, Type target_type, Type source_type,
                      Context context):
        if not self.check_void(source_type, context):
            self.fail('Cannot cast from {} to {}'.format(
                self.format(source_type), self.format(target_type)), context)
    
    void incompatible_operator_assignment(self, str op, Context context):
        self.fail('Result type of {} incompatible in assignment'.format(op),
                  context)
    
    void incompatible_value_count_in_assignment(self, int lvalue_count,
                                                int rvalue_count,
                                                Context context):
        if rvalue_count < lvalue_count:
            self.fail('Need {} values to assign'.format(lvalue_count), context)
        elif rvalue_count > lvalue_count:
            self.fail('Too many values to assign', context)
    
    void type_incompatible_with_supertype(self, str name, TypeInfo supertype,
                                          Context context):
        self.fail('Type of "{}" incompatible with supertype "{}"'.format(
            name, supertype.name), context)
    
    void signature_incompatible_with_supertype(self, str name, str supertype,
                                               Context context):
        self.fail('Signature of "{}" incompatible with supertype "{}"'.format(
            name, supertype), context)
    
    void argument_incompatible_with_supertype(self, int arg_num, str name,
                                              str supertype, Context context):
        self.fail('Argument {} of "{}" incompatible with supertype "{}"'
                  .format(arg_num, name, supertype), context)
    
    void return_type_incompatible_with_supertype(self, str name, str supertype,
                                                 Context context):
        self.fail('Return type of "{}" incompatible with supertype "{}"'
                  .format(name, supertype), context)
    
    void method_expected_as_operator_implementation(self, Type typ, str member,
                                                    Context context):
        self.fail('Expected operator method "{}" in {}'.format(
            member, self.format(typ)), context)
    
    void boolean_return_value_expected(self, str method, Context context):
        self.fail('Boolean return value expected for method "{}"'.format(
            method), context)
    
    void incompatible_type_application(self, int expected_arg_count,
                                       int actual_arg_count, Context context):
        if expected_arg_count == 0:
            self.fail('Type application targets a non-generic function',
                      context)
        elif actual_arg_count > expected_arg_count:
            self.fail('Type application has too many types ({} expected)'
                      .format(expected_arg_count), context)
        else:
            self.fail('Type application has too few types ({} expected)'
                      .format(expected_arg_count), context)
    
    void incompatible_array_item_type(self, Type typ, int index,
                                      Context context):
        self.fail('Array item {} has incompatible type {}'.format(
            index, self.format(typ)), context)
    
    void could_not_infer_type_arguments(self, Callable callee_type, int n,
                                        Context context):
        if callee_type.name and n > 0:
            self.fail('Cannot infer type argument {} of {}'.format(
                n, callee_type.name), context)
        else:
            self.fail('Cannot infer function type argument', context)
    
    void invalid_var_arg(self, Type typ, Context context):
        self.fail('List or tuple expected as variable arguments', context)
    
    void invalid_keyword_var_arg(self, Type typ, Context context):
        if isinstance(typ, Instance) and (
                ((Instance)typ).type.fullname() == 'builtins.dict'):
            self.fail('Keywords must be strings', context)
        else:
            self.fail('Argument after ** must be a dictionary',
                      context)
    
    void incomplete_type_var_match(self, str member, Context context):
        self.fail('"{}" has incomplete match to supertype type variable'
                  .format(member), context)
    
    Type not_implemented(self, str msg, Context context):
        self.fail('Feature not implemented yet ({})'.format(msg), context)
        return AnyType()
    
    void undefined_in_superclass(self, str member, Context context):
        self.fail('"{}" undefined in superclass'.format(member), context)
    
    bool check_void(self, Type typ, Context context):
        """If type is void, report an error such as '.. does not
        return a value' and return True. Otherwise, return False.
        """
        if isinstance(typ, Void):
            self.does_not_return_value(typ, context)
            return True
        else:
            return False

    void cannot_determine_type(self, str name, Context context):
        self.fail("Cannot determine type of '%s'" % name, context)

    void invalid_method_type(self, Callable sig, Context context):
        self.fail('Invalid method type', context)

    void incompatible_conditional_function_def(self, FuncDef defn):
        self.fail('All conditional function variants must have identical '
                  'signatures', defn)

    void cannot_instantiate_abstract_class(self, str class_name,
                                           str[] abstract_attributes,
                                           Context context):
        attrs = format_string_list("'%s'" % a for a in abstract_attributes[:5])
        self.fail("Cannot instantiate abstract class '%s' with abstract "
                  "method%s %s" % (class_name, plural_s(abstract_attributes),
                                   attrs),
                  context)


str capitalize(str s):
    """Capitalize the first character of a string."""
    if s == '':
        return ''
    else:
        return s[0].upper() + s[1:]


str extract_type(str name):
    """If the argument is the name of a method (of form C.m), return
    the type portion in quotes (e.g. "y"). Otherwise, return the string
    unmodified.
    """
    name = re.sub('^"[a-zA-Z0-9_]+" of ', '', name)
    return name


str strip_quotes(str s):
    """Strip a double quote at the beginning and end of the string, if any."""
    s = re.sub('^"', '', s)
    s = re.sub('"$', '', s)
    return s


str plural_s(Sequence s):
    if len(s) > 1:
        return 's'
    else:
        return ''


str format_string_list(Iterable<str> s):
    l = list(s)
    assert len(l) > 0
    if len(l) == 1:
        return l[0]
    else:
        return '%s and %s' % (', '.join(l[:-1]), l[-1])
