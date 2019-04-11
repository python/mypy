two_types = (list, tuple)
third_type = str
if isinstance('text', *(str, int)):
    print('hello')
