#!/usr/bin/python2.5

import html5lib
import logging
import os
import simplejson

from google.appengine.api import memcache
from google.appengine.api import urlfetch
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app

from html5lib import treebuilders, treewalkers, serializer
from html5lib import sanitizer


TEMPLATE_DIR = 'templates'

EXAMPLES_URL = 'http://appengine-html-whitelist.googlecode.com/svn/trunk/examples'


class AtwoodSanitizer(sanitizer.HTMLSanitizer):
  """A santizer that allows only a small subset of elements through.

  See the following blog post for details:
    http://refactormycode.com/codes/333-sanitize-html
  """
  allowed_elements = [
    'a', 'b', 'blockquote', 'br', 'code', 'em', 'h1', 'h2',  'h3', 'hr', 'i', 
    'img', 'li', 'ol', 'p', 'pre', 's', 'sub', 'sup', 'strike', 'strong', 'ul'
  ]


SANITIZING_TOKENIZERS = {'default': sanitizer.HTMLSanitizer,
                         'atwood': AtwoodSanitizer}


class ReportableError(Exception):
  """A class of exceptions that should be shown to the user."""
  message = None

  def __init__(self, message):
    """Constructs a new ReportableError.

    Args:
      message: The message to be logged and displayed to the user.
    """
    self.message = message


class UserError(ReportableError):
  """An 400 error caused by user behavior."""


class ServerError(ReportableError):
  """An 500 error caused by the server."""


class Usage(webapp.RequestHandler):
  """Prints usage information in response to requests to '/'."""
  def get(self):
    self.response.headers['Content-Type'] = 'text/html'
    path = os.path.join(os.path.dirname(__file__), TEMPLATE_DIR, 'usage.tmpl')
    template_vars = {'examples_url': EXAMPLES_URL}
    self.response.out.write(template.render(path, template_vars))


class HtmlWhitelist(webapp.RequestHandler):
  """A request handler that whitelists arbitrary HTML."""

  def get(self):
    """Whitelists the content referred to by the 'url' param."""
    content = self.request.get('content', default_value=None)
    if not content:
      url = self.request.get('url', default_value=None)
      if not url:
        raise UserError("Either a 'content' or 'url' parameter is required.")
      content = self._get_url(url)
    as_json = self._get_bool('json')
    json_callback = self.request.get('callback', default_value=None)
    mode = self.request.get('mode', default_value='default')
    content = self._whitelist(content, mode)
    self._print(content, as_json, json_callback)

  def post(self):
    """Whitelists the content included in the post body."""
    # If a 'content' element is present in either 'multipart/form-data'
    # or 'application/x-www-form-urlencoded' encodings, use that as the content
    # to be sanitized, otherwise use the entire body
    body = self.request.body
    content = self.request.get('content', default_value=None)
    if content is None:
      content = body
    as_json = self._get_bool('json')
    json_callback = self.request.get('callback', default_value=None)
    mode = self.request.get('mode', default_value='default')
    content = self._whitelist(content, mode)
    self._print(content, as_json, json_callback)

  def handle_exception(self, exception, debug_mode):
    if isinstance(exception, UserError):
      logging.error('ServerError: %s' % exception.message)
      self.error(400)
      self._print_error(exception.message)
    elif isinstance(exception, ServerError):
      logging.error('SeverError: %s' % exception.message)
      self.error(500)
      self._print_error(exception.message)
    else:
      super(HtmlWhitelist, self).handle_exception(exception, debug_mode)

  def _print(self, content, as_json, json_callback):
    if json_callback:
      mime_type = 'text/javascript'
      content = '%s(%s)' % (json_callback, simplejson.dumps({'html': content}))
    elif as_json:
      mime_type = 'text/javascript'
      content = simplejson.dumps({'html': content})
    else:
      mime_type = 'text/html'
    self.response.headers['Content-Type'] = mime_type
    self.response.out.write(content)
    self.response.out.write("\n")

  def _print_error(self, message):
    """Prints an error message as type text/plain.

    Args:
      error: The plain text error message.
    """
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(message)
    self.response.out.write("\n")

  def _whitelist(self, content, mode):
    """Runs the content through an HTML parser and filter.

    Args:
      content: The content to be whitelisted.
      mode: The name of the sanitizer to use.
    """
    try:
      sanitizing_tokenizer = SANITIZING_TOKENIZERS[mode]
    except KeyError:
      raise UserError("Unknown mode '%s'." % mode)
    parser = html5lib.HTMLParser(tokenizer=sanitizing_tokenizer,
                                 tree=treebuilders.getTreeBuilder("dom"))
    tree = parser.parse(content)
    body = tree.getElementsByTagName('body')[0]
    return ''.join([elem.toxml() for elem in body.childNodes])

  def _get_url(self, url):
    """Retrieves a URL and caches the results.

    Args:
      url: A url to be fetched
    """
    content = memcache.get(url)
    if content is None:
      result = urlfetch.fetch(url)
      if result.status_code != 200:
        raise ServerError("Could not fetch url '%s'." % url)
      content = result.content
      if not memcache.add(url, content, 60):
        logging.error("Memcache set of %s failed." % url)
    return content

  def _get_bool(self, key):
    """Return True if the request parameter is set to anything true-like.

    Args:
      key: The query parameter name
    """
    value = self.request.get(key, default_value=None)
    return value and value != '0' and value.lower() != 'false'


application = webapp.WSGIApplication([('/whitelist/?', HtmlWhitelist),
                                      ('/', Usage)],
                                     debug=True)


def main():
  run_wsgi_app(application)


if __name__ == "__main__":
  main()
