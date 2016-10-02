from typing import Iterator, List
import sys
import os
import os.path


class Chunk:
    def __init__(self, header_type: str, args: str) -> None:
        self.header_type = header_type
        self.args = args
        self.lines = []  # type: List[str]


def is_header(line: str) -> bool:
    return line.startswith('[') and line.endswith(']')


def normalize(lines: Iterator[str]) -> Iterator[str]:
    return (line.rstrip() for line in lines)


def produce_chunks(lines: Iterator[str]) -> Iterator[Chunk]:
    current_chunk = None  # type: Chunk
    for line in normalize(lines):
        if is_header(line):
            if current_chunk is not None:
                yield current_chunk
            parts = line[1:-1].split(' ', 1)
            args = parts[1] if len(parts) > 1 else ''
            current_chunk = Chunk(parts[0], args)
        else:
            current_chunk.lines.append(line)
    if current_chunk is not None:
        yield current_chunk


def write_out(filename: str, lines: List[str]) -> None:
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, 'w') as stream:
        stream.write('\n'.join(lines))


def write_tree(root: str, chunks: Iterator[Chunk]) -> None:
    init = next(chunks)
    assert init.header_type == 'case'
    
    root = os.path.join(root, init.args)
    write_out(os.path.join(root, 'main.py'), init.lines)

    for chunk in chunks:
        if chunk.header_type == 'file' and chunk.args.endswith('.py'):
            write_out(os.path.join(root, chunk.args), chunk.lines)


def help() -> None:
    print("Usage: python misc/test_case_to_actual.py test_file.txt root_path")


def main() -> None:
    if len(sys.argv) != 3:
        help()
        return

    test_file_path, root_path = sys.argv[1], sys.argv[2]
    with open(test_file_path, 'r') as stream:
        chunks = produce_chunks(iter(stream))
        write_tree(root_path, chunks)


if __name__ == '__main__':
    main()
