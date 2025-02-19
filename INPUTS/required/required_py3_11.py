import typing

class Movie(typing.TypedDict):
    title: str
    year: typing.NotRequired[int]

m = Movie(title='The Matrix')
print(m)
