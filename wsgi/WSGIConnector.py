#==============================================================================
#    Copyright 2005-2009, Tassos Koutsovassilis
#
#    This file is part of Porcupine.
#    Porcupine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published
#    by the Free Software Foundation; either version 2.1 of the License, or
#    (at your option) any later version.
#    Porcupine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#    You should have received a copy of the GNU Lesser General Public License
#    along with Porcupine; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#==============================================================================
"""Porcupine WSGI connector"""
import socket
import sys
import os
import re
import itertools
import time
import threading
from errno import EISCONN, EADDRINUSE

try:
    # python 2.6
    import Queue as queue
except ImportError:
    # python 3
    import queue

try:
    # python 3
    import configparser
except ImportError:
    # python 2.6
    import ConfigParser as configparser

try:
    # python 2.6
    from cPickle import dumps, loads
except ImportError:
    # python 3
    from pickle import dumps, loads

try:
    # python 2.6
    import httplib
except ImportError:
    # python 3
    import http.client as httplib

try:
    # python 2.6
    from urllib import unquote
except ImportError:
    # python 3
    from urllib.parse import unquote


class Host(object):
    port = itertools.cycle(range(65535, 40958, -1))

    def __init__(self, address):
        self.address = address
        self.connections = 0


class Site(object):
    rejoin_timeout = 60

    def __init__(self):
        self.is_populated = False
        self._hosts = []
        self.hosts = iter(self._hosts)
        self.inactive_nodes = queue.Queue(0)
        self._rejoin_thread = threading.Thread(target=self._rejoin_nodes)
        self._shutdown_event = threading.Event()
        self._rejoin_thread.start()

    def populate(self, ini_file):
        config = configparser.RawConfigParser()
        config.readfp(open(ini_file))

        # add hosts
        self._hosts = []
        hosts = config.get('config', 'hosts')
        hosts = hosts.split(',')
        for host in hosts:
            self.add_host(Host(self.get_address_from_string(host)))

        # configure rejoin_timeout
        try:
            rejoin_timeout = config.get('config', 'rejoin_timeout')
            self.rejoin_timeout = int(rejoin_timeout)
        except:
            pass

        self.is_populated = True

    def _rejoin_nodes(self):
        while not self._shutdown_event.is_set():
            host, downtime = self.inactive_nodes.get()
            if host is None:
                break
            time_delta = time.time() - downtime
            if time_delta < self.rejoin_timeout:
                self._shutdown_event.wait(self.rejoin_timeout - time_delta)
            # rejoin host
            self.add_host(host)

    def __len__(self):
        return len(self._hosts)

    def __iter__(self):
        return self.hosts

    def add_host(self, host):
        self._hosts.append(host)
        self.hosts = itertools.cycle(self._hosts)

    def remove_host(self, host):
        if len(self._hosts) > 1:
            try:
                self._hosts.remove(host)
                self.hosts = itertools.cycle(self._hosts)
                self.inactive_nodes.put((host, time.time()))
            except ValueError:
                pass

    @staticmethod
    def get_address_from_string(s):
        address = s.split(':')
        address[1] = int(address[1])
        return tuple(address)

    def shutdown(self):
        self._shutdown_event.set()
        self.inactive_nodes.put((None, None))
        self._rejoin_thread.join()


def application(environ, start_response):
    connector = WSGIConnector()
    return connector(environ, start_response)


def shutdown():
    WSGIConnector.site.shutdown()


class WSGIConnector(object):
    ip_address = socket.gethostbyname(socket.gethostname())
    buffer_size = 8 * 1024
    mobile_sig = re.compile('PMB|UNTRUSTED')
    error_page = '''<html><body><H3>Porcupine Server</H3><p><pre>
        ERROR

        %s</pre></p></body></html>'''
    site = Site()
    site.populate((os.path.dirname(__file__) or '.') + '/server.ini')

    def __call__(self, environment, start_response):
        response_headers = []
        length = 0
        if 'CONTENT_LENGTH' in environment and environment['CONTENT_LENGTH']:
            length = int(environment['CONTENT_LENGTH'])
        errors = environment.pop('wsgi.errors')

        host = None
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            if 'wsgi.input' in environment:
                wsgi_input = environment.pop('wsgi.input')
                if length > 0:
                    input = wsgi_input.read(length)
                else:
                    # chunked request
                    input = []
                    if ('HTTP_TRANSFER_ENCODING' in environment and
                        environment['HTTP_TRANSFER_ENCODING'] == 'chunked'):
                        chunk_size = int('0x' +
                            wsgi_input.readline().decode('utf-8'), 16)
                        while chunk_size > 0:
                            char = wsgi_input.read(1)
                            while char in b'\r\n':
                                char = wsgi_input.read(1)
                            input.append(char)
                            input.append(wsgi_input.read(chunk_size - 1))
                            char = wsgi_input.read(1).decode('utf-8')
                            while char in '\r\n':
                                char = wsgi_input.read(1).decode('utf-8')
                            chunk_size = int('0x' + char +
                                wsgi_input.readline().decode('utf-8'), 16)
                    input = b''.join(input)
            else:
                input = b''

            if 'wsgi.file_wrapper' in environment:
                del environment['wsgi.file_wrapper']
            environment["PATH_INFO"] = unquote(environment["PATH_INFO"])
            dct = {'if': 'WSGI',
                   'env': environment,
                   'inp': input}
            data = dumps(dct, 2)
            response = []
            num_of_hosts = len(self.site)
            i = 0

            for host in iter(self.site):
                err = s.connect_ex(host.address)
                while err and err not in (0, EISCONN):
                    #print >> sys.stderr, "connect_ex: %d" % err
                    if err == EADDRINUSE:
                        # address already in use
                        # the ephemeral port range is exhausted
                        s.bind((self.ip_address, next(host.port)))
                        err = s.connect_ex(host.address)
                    else:
                        # the host refuses connection or would block
                        self.site.remove_host(host)
                        i += 1
                        # break while
                        break
                else:
                    # we got a connection
                    host.connections += 1
                    # break for
                    break

                if i >= num_of_hosts:
                    raise socket.error

            # Send our request to Porcupine Server
            s.send(data)
            s.shutdown(socket.SHUT_WR)

            # Get the response object from Porcupine Server
            while True:
                rdata = s.recv(self.buffer_size)
                if not rdata:
                    break
                response.append(rdata)

            response = b''.join(response)
            ret_code, body, headers, cookies = loads(response)

            for cookie in cookies:
                response_headers.append(('Set-Cookie', cookie))

            if 'Location' not in headers:
                for header in headers.items():
                    response_headers.append(header)
            else:
                # it is a redirect
                if self.mobile_sig.search(environment['HTTP_USER_AGENT']):
                    # it is a mobile device
                    # handle redirect internally
                    url_scheme = environment['wsgi.url_scheme']
                    location = headers['Location']
                    if location[:len(url_scheme)] != url_scheme:
                        location = (url_scheme + '://' +
                                    environment['HTTP_HOST'] + location)

                    sHost = (environment['HTTP_HOST'] +
                             environment['SCRIPT_NAME'])
                    lstPath = location[location.index(sHost) +
                                       len(sHost):].split('?')

                    environment['PATH_INFO'] = lstPath[0]
                    if len(lstPath) == 2:
                        environment['QUERY_STRING'] = lstPath[1]
                    else:
                        environment['QUERY_STRING'] = ''

                    environment['wsgi.errors'] = errors
                    conn = WSGIConnector()
                    return conn(environment, start_response)
                else:
                    response_headers.append(('Location', headers['Location']))

        except socket.error:
            import traceback
            output = traceback.format_exception(*sys.exc_info())
            output = ''.join(output)
            self.write_errors(errors, output)
            ret_code = 503
            response_headers = [('Content-Type', 'text/html')]
            body = self.error_page % 'Service Temporarily Unavailable'

        except:
            import traceback
            output = traceback.format_exception(*sys.exc_info())
            output = ''.join(output)
            self.write_errors(errors, output)
            ret_code = 500
            response_headers = [('Content-Type', 'text/html')]
            body = self.error_page % output

        finally:
            s.close()
            if host is not None:
                host.connections -= 1

        response_headers.append(('Content-Length', str(len(body))))
        status = '%d %s' % (ret_code, httplib.responses[ret_code])

        start_response(status, response_headers)

        # we need to slice the body because
        # if not, the gzipped content
        # is not loaded on correctly on windows
        # when running the connector stand-alone
        return (body[i:i + 1024]
                for i in range(0, len(body), 1024))

    @staticmethod
    def write_errors(errors, output):
        try:
            errors.write(output)
        except TypeError:  # python 3
            errors.write(bytearray(output, 'utf-8'))
