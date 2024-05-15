import tarfile

with tarfile.open("test.tar.xz", "w:xz") as tar:
    pass

# Test with valid preset values
tarfile.open("test.tar.xz", "w:xz", preset=0)
tarfile.open("test.tar.xz", "w:xz", preset=5)
tarfile.open("test.tar.xz", "w:xz", preset=9)

# Test with invalid preset values
tarfile.open("test.tar.xz", "w:xz", preset=-1)  # type: ignore
tarfile.open("test.tar.xz", "w:xz", preset=10)  # type: ignore
