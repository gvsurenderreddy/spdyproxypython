import re
import io

#extracted from https://github.com/simon-engledew/python-chunks

def from_pattern(pattern, type, *args):
    def coerce(value):
        value = str(value)
        match = pattern.search(value)
        if match is not None:
            return type(match.group(1), *args)
        raise ValueError('unable to coerce "%s" into a %s' % (value, type.__name__))
    return coerce

to_int = from_pattern(re.compile('([-+]?[0-9]+)', re.IGNORECASE), int)
to_hex = from_pattern(re.compile('([-+]?[0-9A-F]+)', re.IGNORECASE), int, 16)
to_float = from_pattern(re.compile('([-+]?[0-9]*\.?[0-9]+)'), float)
to_megabytes = lambda n: n * 1024 * 1024

def decode(fileobj, chunk_limit=to_megabytes(1)):
    while True:
        index = fileobj.readline(len('%x' % chunk_limit))
        if not index:
            raise EOFError('unexpected blank line')
        length = to_hex(index)
        if length > chunk_limit:
            raise OverflowError('invalid chunk size of "%d" requested, max is "%d"' % (length, chunk_limit))
        value = fileobj.read(length)
        assert len(value) == length
        yield value
        tail = fileobj.read(2)
        if not tail:
            raise ValueError('missing \\r\\n after chunk')
        assert tail == '\r\n', 'unexpected characters "%s" after chunk' % tail
        if not length:
            return

def decodeChunked(chunked):
    result = ''
    for chunk in decode(io.StringIO(chunked)):
        result += chunk
    return result

if __name__ == "__main__":
    content = "5\r\nwikie\r\n0\r\n\r\n"
    content = "891\r\n<!DOCTYPE html>\n<html>\n<head>\n<meta http-equiv=\"Content-Type\" content=\"text/html;charset=UTF-8\"/>\n<title>Asociaci&oacute;n M&eacute;dica de Luj&aacute;n</title>\n<link href=\"css/style.css\" rel=\"stylesheet\" type=\"text/css\">\n<!--[if lt IE 9]>\n<script src=\"http://html5shim.googlecode.com/svn/trunk/html5.js\"></script>\n<![endif]-->\n<script src=\"//ajax.googleapis.com/ajax/libs/jquery/1.7.1/jquery.min.js\"></script>\n<script>window.jQuery || document.write('<script src=\"js/libs/jquery-1.7.1.min.js\"><\\/script>')</script>\n<script type=\"text/javascript\" src=\"js/fancybox/jquery.mousewheel-3.0.4.pack.js\"></script>\n<script type=\"text/javascript\" src=\"js/fancybox/jquery.fancybox-1.3.4.pack.js\"></script>\n<link rel=\"stylesheet\" type=\"text/css\" href=\"js/fancybox/jquery.fancybox-1.3.4.css\" media=\"screen\" />\n<script type=\"text/javascript\" src=\"js/script.js\"></script>\n<!--<script type=\"text/javascript\" src=\"js/libs/snow.js\"></script>-->\n</head>\n\n<body>\n\t<header> \n    \t<img src=\"images/logoaml.png\" style=\"-webkit-opacity:0.8;-moz-opacity:0.8\"/>\n        <!--<img src=\"images/arbol.png\" height=\"140px\" style=\"-webkit-opacity:0.6;-moz-opacity:0.6\"/>-->\n    </header>\n    <nav id=\"menu\">\n    \t<ul>\n            <li><a href=\"#\" title=\"home\" class=\"active\">Home</a></li>\n            <li><a href=\"#\" title=\"novedades\">Novedades</a></li>\n            <li><a href=\"#\" title=\"socios\">Socios</a></li>\n            <li><a href=\"#\" title=\"planillas\">Planillas</a></li>\n            <li><a href=\"#\" title=\"informacion\">InformaciÃ³n</a></li>\n            <li><a href=\"#\" title=\"contacto\">Contacto</a></li>            \n         </ul>\n         <ul>\n         \t<li><a href=\"sections/prof.php\" id='link_prof' style=\"background: rgba(25,123,30,0.4);\">Profesionales</a></li>\n         </ul>\n    </nav>\n    <section id=\"main\">\n    \t\n    </section>\n        \n    <footer>\n\t\t<span style='color:gray'>Asociaci&oacute;n M&eacute;dica</span>\n        <p>Mariano Moreno 1460 Tel. (02323) 422293 / 420704 / 434250 C.P. 6700 Luj&aacute;n Pcia. de Buenos Aires, Argentina</p>\n\t\t<span style='color:gray'>IOMA</span>\n\t\t<p>Las Heras 509 Tel. (02323) 435862 C.P. 6700 Luj&aacute;n Pcia. de Buenos Aires, Argentina</p>\n\t</footer>\n</body>\n</html>\n\r\n0\r\n\r\n"
    print(decodeChunked(content))