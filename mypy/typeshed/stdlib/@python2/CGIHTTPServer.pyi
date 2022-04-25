import SimpleHTTPServer

class CGIHTTPRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    cgi_directories: list[str]
    def do_POST(self) -> None: ...
