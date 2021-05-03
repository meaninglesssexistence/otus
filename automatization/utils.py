# -*- coding: utf-8 -*-

from email.utils import formatdate
from datetime import datetime
from time import mktime
from urllib.parse import unquote


def get_mime_type(ext):
    """ Return mime type for the file extension. """
    mime_types = {
        '.txt':  'text/plain',
        '.html': 'text/html',
        '.css':  'text/css',
        '.js':   'text/javascript',
        '.jpg':  'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png':  'image/png',
        '.gif':  'image/gif',
        '.swf':  'application/x-shockwave-flash'}
    return mime_types.get(ext, 'application/octet-stream')


def get_http_code_status(code):
    """ Return text status for HTTP code """
    statuses = {
        200: 'OK',
        400: 'Bad Request',
        403: 'Forbidden',
        404: 'Not Found',
        405: 'Method Not Allowed'
    }
    return statuses.get(code, '')


def get_uri_path(uri):
    """ Get path part from URI. """
    uri = uri.split('?')[0]
    uri = uri.split('#')[0]
    return unquote(uri)


def get_http_timestamp():
    """ Return current timestamp formatted for HTTP request. """
    return formatdate(timeval=mktime(datetime.now().timetuple()),
                      localtime=False, usegmt=True)
