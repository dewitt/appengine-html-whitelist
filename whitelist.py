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
    content = self.request.get('content')
    if not content:
      url = self.request.get('url')
      if not url:
        return self._error('either content or url required')
      content = self._get_url(url)
    as_json = self.request.get('json')
    json_callback = self.request.get('callback')
    content = self._whitelist(content)
    self._print(content, as_json, json_callback)

  def post(self):
    """Whitelists the content included in the post body."""
    content = self._whitelist(self.request.body)
    as_json = self.request.get('json')
    json_callback = self.request.get('callback')
    self._print(content, as_json, json_callback)

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

  def _error(self, message):
    """Prints an error message as type text/plain.

    Args:
      error: The plain text error message.
    """
    logging.error(message)
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(message)
    self.response.out.write("\n")
    return None

  def _whitelist(self, content):
    """Runs the content through an HTML parser and filter.

    Args:
      content: The content to be whitelisted.
    """
    parser = html5lib.HTMLParser(tokenizer=sanitizer.HTMLSanitizer,
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
        return self._error('could not fetch %s' % url)
      content = result.content
      if not memcache.add(url, content, 60):
        logging.error("Memcache set of %s failed." % url)
    return content

application = webapp.WSGIApplication([('/whitelist/?', HtmlWhitelist),
                                      ('/', Usage)],
                                     debug=True)


def main():
  run_wsgi_app(application)


if __name__ == "__main__":
  main()
