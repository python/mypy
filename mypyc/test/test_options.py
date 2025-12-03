# test/testopts.py (or similar file)

from mypy.errorcodes import error_codes, ErrorCode
from mypy.options import Options
import unittest # or another framework used by mypy

# Get the specific ErrorCode object we are testing
POSSIBLY_UNDEFINED = error_codes['possibly-undefined']

class OptionsPrecedenceSuite(unittest.TestCase):
    # ... other test methods ...

    # --- Your New Tests Below ---

    def test_global_disable_precedence(self) -> None:
        """
        Verify fix #1: Global disable via flag/config overrides global enable.
        (Tests Options.process_error_codes)
        """
        options = Options()
        # 1. Simulate both being set in config/command line
        options.enable_error_code = ['possibly-undefined']
        options.disable_error_code = ['possibly-undefined']

        # 2. Run the processing logic (this is where your fix lives)
        options.process_error_codes(error_callback=lambda x: None)

        # 3. Assert the result: DISABLE must win
        self.assertIn(POSSIBLY_UNDEFINED, options.disabled_error_codes)
        self.assertNotIn(POSSIBLY_UNDEFINED, options.enabled_error_codes)

    def test_per_module_disable_precedence(self) -> None:
        """
        Verify fix #2: Per-module disable overrides global enable.
        (Tests Options.apply_changes)
        """
        base_options = Options()
        
        # 1. Setup the global options to ENABLE the code
        base_options.enable_error_code = ['possibly-undefined']
        base_options.process_error_codes(error_callback=lambda x: None)
        
        # 2. Setup a per-module override to DISABLE the code
        per_module_changes: dict[str, object] = { 
            'disable_error_code': ['possibly-undefined'],
            'enable_error_code': [], 
        }
        
        # 3. Apply the per-module changes (this is where your fix lives)
        # We don't care about the module name here, just the application of changes.
        module_options = base_options.apply_changes(per_module_changes)
        
        # 4. Assert the result: DISABLE must win at the module level
        self.assertIn(POSSIBLY_UNDEFINED, module_options.disabled_error_codes)
        self.assertNotIn(POSSIBLY_UNDEFINED, module_options.enabled_error_codes)