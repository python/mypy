# This module contains the API for using mypy as a module inside a tool written in Python,
# rather than from the command line or as a separate process
#
# Being an interface, it attempts to be thin, stable and self-explanatory
# Since the guts of mypy are bound to change, it doesn't depend too much upon them
# Rather it uses its own 'outside view' concepts
#
# It exports a singleton type_validator along with two error types
# All fields of these error types become evident by reading through their constructors

from typing import Any, List, Dict
from mypy import build, errors, options

# Validate errors are all errors produced by the validator
# Having a common base class allows easy specification of polymorphic lists
class ValidationError:
	pass

# Type errors are static typing inconsistencies in the code that is being validated
class StaticTypingError (ValidationError):
	def __init__ (self, error_info: errors.ErrorInfo):
		self._error_info = error_info
		self.import_context = self._error_info.import_ctx
		self.in_source_file_name = self._error_info.file
		self.in_class = self._error_info.type
		self.in_function = self._error_info.function_or_member
		self.in_line_nr = self._error_info.line
		self.error_severity_key = self._error_info.severity
		self.error_description = self._error_info.message
		self.report_once = self._error_info.only_once

# Compile errors all other errors occuring during validation
class CompilationError (ValidationError):
	def	__init__ (self, compile_error: errors.CompileError) -> None:
		self._compile_error = compile_error
		self.error_messages = self.compile_error.messages
		
# Validator options are those options in options.Options that are meant for production use
class ValidatorOptions (options.Options):
	def __init__ (self,
        build_type = BuildType.STANDARD
        python_version = defaults.PYTHON3_VERSION
        platform = sys.platform
        custom_typing_module = None # type: str
        report_dirs = {} # type: Dict[str, str]
        silent_imports = False
        almost_silent = False
        disallow_untyped_calls = False				# Disallow calling untyped functions from typed ones
        disallow_untyped_defs = False				# Disallow defining untyped (or incompletely typed) functions
        check_untyped_defs = False					# Type check unannotated functions
        warn_incomplete_stub = False				# Also check typeshed for missing annotations
        warn_redundant_casts = False				# Warn about casting an expression to its inferred type
        warn_unused_ignores = False					# Warn about unused '# type: ignore' comments
	):
		params = locals () .keys ()
		self._options = options.Options ()
		for param in params:
			setattr (self._options, *param)
			
# Private class, to warant a singleton instance
class _TypingValidator:
	def __init__ (self) -> None:
		self.options = options.Options ()
		self.validation_resuls = []
		
	# Options are given as a dictionary	
	def set_options_dict (self, options_dict: Dict [string, Any]) -> None :	
		for option_item in option_dict.items ():
			if option_item [0] in self.public_options:
				setattr (self.options, option_item)	# While setattr currently doesn't do any typechecking, it's anticipated to do so in the future
			else:
				raise 
		
	def validate_types (self, source_paths: string) -> List [ValidationError]:			
		try:
			build_result = build.build (
				[build.BuildSource (source_path, None, None) for source_path in source_paths],
				None,
				self.options
			)
			self.validation_results += [ValidationError (error_info) for error_info in build_result.manager.errors]
		except CompileError as compile_eror:
			self.validation_results.append (CompilationError (compile_error))

# Singleton representing the mypy in any 3rd party tools that it's part of
typing_validator = _TypingValidator ()

