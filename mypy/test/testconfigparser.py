import os
import tempfile
from unittest import TestCase, main
from mypy.options import Options
from mypy.config_parser import parse_config_file

class TestConfigParser(TestCase):
    def test_parse_config_file_with_single_file(self) -> None:
        """A single file should be correctly parsed."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            config_path = os.path.join(tmpdirname, "test_config.ini")

            with open(config_path, "w") as f:
                f.write(
                    """
                    [mypy]
                    files = file1.py
                    """
                )

            options = Options()

            parse_config_file(
                options,
                lambda: None,
                config_path,
                stdout=None,
                stderr=None,
            )

            self.assertEqual(options.files, ["file1.py"])

    def test_parse_config_file_with_no_spaces(self) -> None:
        """Files listed without spaces should be correctly parsed."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            config_path = os.path.join(tmpdirname, "test_config.ini")

            with open(config_path, "w") as f:
                f.write(
                    """
                    [mypy]
                    files =file1.py,file2.py,file3.py
                    """
                )

            options = Options()

            parse_config_file(
                options,
                lambda: None,
                config_path,
                stdout=None,
                stderr=None,
            )

            self.assertEqual(options.files, ["file1.py", "file2.py", "file3.py"])

    def test_parse_config_file_with_extra_spaces(self) -> None:
        """Files with extra spaces should be correctly parsed."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            config_path = os.path.join(tmpdirname, "test_config.ini")

            with open(config_path, "w") as f:
                f.write(
                    """
                    [mypy]
                    files =  file1.py ,   file2.py  ,   file3.py   
                    """
                )

            options = Options()

            parse_config_file(
                options,
                lambda: None,
                config_path,
                stdout=None,
                stderr=None,
            )

            self.assertEqual(options.files, ["file1.py", "file2.py", "file3.py"])

    def test_parse_config_file_with_empty_files_key(self) -> None:
        """An empty files key should result in an empty list."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            config_path = os.path.join(tmpdirname, "test_config.ini")

            with open(config_path, "w") as f:
                f.write(
                    """
                    [mypy]
                    files = 
                    """
                )

            options = Options()

            parse_config_file(
                options,
                lambda: None,
                config_path,
                stdout=None,
                stderr=None,
            )

            self.assertEqual(options.files, [])

    def test_parse_config_file_with_only_comma(self) -> None:
        """A files key with only a comma should raise an error."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            config_path = os.path.join(tmpdirname, "test_config.ini")

            with open(config_path, "w") as f:
                f.write(
                    """
                    [mypy]
                    files = ,
                    """
                )

            options = Options()

            with self.assertRaises(ValueError) as cm:
                parse_config_file(
                    options,
                    lambda: None,
                    config_path,
                    stdout=None,
                    stderr=None,
                )

            self.assertIn("Invalid config", str(cm.exception))

    def test_parse_config_file_with_only_whitespace(self) -> None:
        """A files key with only whitespace should result in an empty list."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            config_path = os.path.join(tmpdirname, "test_config.ini")

            with open(config_path, "w") as f:
                f.write(
                    """
                    [mypy]
                    files =    
                    """
                )

            options = Options()

            parse_config_file(
                options,
                lambda: None,
                config_path,
                stdout=None,
                stderr=None,
            )

            self.assertEqual(options.files, [])

    def test_parse_config_file_with_mixed_valid_and_invalid_entries(self) -> None:
        """Mix of valid and invalid filenames should raise an error."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            config_path = os.path.join(tmpdirname, "test_config.ini")

            with open(config_path, "w") as f:
                f.write(
                    """
                    [mypy]
                    files = file1.py, , , file2.py
                    """
                )

            options = Options()

            with self.assertRaises(ValueError) as cm:
                parse_config_file(
                    options,
                    lambda: None,
                    config_path,
                    stdout=None,
                    stderr=None,
                )

            self.assertIn("Invalid config", str(cm.exception))

    def test_parse_config_file_with_newlines_between_files(self) -> None:
        """Newlines between file entries should be correctly handled."""
        with tempfile.TemporaryDirectory() as tmpdirname:
            config_path = os.path.join(tmpdirname, "test_config.ini")

            with open(config_path, "w") as f:
                f.write(
                    """
                    [mypy]
                    files = file1.py,
                            file2.py,
                            file3.py
                    """
                )

            options = Options()

            parse_config_file(
                options,
                lambda: None,
                config_path,
                stdout=None,
                stderr=None,
            )

            self.assertEqual(options.files, ["file1.py", "file2.py", "file3.py"])

if __name__ == "__main__":
    main()
