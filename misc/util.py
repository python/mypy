import os
import sys

def delete_folder(folder_path: str) -> None:
    if sys.platform.startswith('win'):
        shutil.rmtree(folder_path, ignore_errors=True)
    else:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)
