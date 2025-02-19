from typing import TypedDict, Tuple, Union
from typing_extensions import NotRequired, Required


# --- Class Based TypedDict ---
class Movie(TypedDict, total=False):
    title: Required[str]  # 5
    year: int


m = Movie(title='The Matrix', year=1999)
# m = Movie()
print(m)


# --- Assignment Based TypedDict ---
Movie2 = TypedDict('Movie2', {
    'title': Required[str],
    'year': int,
}, total=False)


m2 = Movie2(title='The Matrix Reloaded', year=2003)
# m2 = Movie2()
print(m2)


# --- Required[] outside of TypedDict (error) ---
x: int = 5
# x: Required[int] = 5


# --- Required[] inside other Required[] (error) ---
'''
Movie3 = TypedDict('Movie3', {
    'title': Required[Union[
        Required[str],
        bytes
    ]],
    'year': int,
}, total=False)
'''


# --- Required[] used within TypedDict but not at top level (error) ---
'''
Movie4 = TypedDict('Movie4', {
    'title': Union[
        Required[str],
        bytes
    ],
    'year': int,
}, total=False)
Movie5 = TypedDict('Movie5', {
    'title': Tuple[
        Required[str],
        bytes
    ],
    'year': int,
}, total=False)
'''


# ==============================================================================
# --- Class Based TypedDict ---
class MovieN(TypedDict):
    title: str
    year: NotRequired[int]


m = MovieN(title='The Matrix', year=1999)
# m = MovieN()
print(m)


# --- Assignment Based TypedDict ---
MovieN2 = TypedDict('MovieN2', {
    'title': str,
    'year': NotRequired[int],
})


m2 = MovieN2(title='The Matrix Reloaded', year=2003)
# m2 = MovieN2()
print(m2)