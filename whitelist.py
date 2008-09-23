#!/usr/bin/python2.5

from google.appengine.api import memcache
from google.appengine.api import urlfetch

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import html5lib
from html5lib import treebuilders, treewalkers, serializer
from html5lib import sanitizer

USAGE = '''<html><head><title>html-whitelist</html></head><body>
<h1>html-whitelist</h1>
<p>Wrapper around the html5lib sanitizer:</p>
<ul>
  <li><code>GET</code> <a href="/whitelist?url=http://appengine-html-whitelist.googlecode.com/svn/trunk/examples/clean.html">/whitelist?url=http://example.com/clean.html</a></li>
  <li><code>GET</code> <a href="/whitelist?url=http://appengine-html-whitelist.googlecode.com/svn/trunk/examples/dirty.html">/whitelist?url=http://example.com/dirty.html</a></li>
  <li><code>POST</code> /whitelist <em>(post body contains arbitrary HTML)</em></li>
</ul>
<p><a href="http://appengine-html-whitelist.googlecode.com/">Source</a></p>
</body></html>
'''

class Usage(webapp.RequestHandler):
  """Prints usage information in response to requests to '/'."""
  def get(self):
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write(USAGE)


class HtmlWhitelist(webapp.RequestHandler):
  """A request handler that whitelists arbitrary HTML."""

  def get(self):
    """Whitelists the content referred to by the 'url' param."""
    url = self.request.get('url')
    if not url:
      return self._error('url required')
    self.response.headers['Content-Type'] = 'text/html'
    content = memcache.get(url)
    if content is None:
      result = urlfetch.fetch(url)
      if result.status_code != 200:
        return self._error('could not fetch %s' % url)
      content = result.content
      if not memcache.add(url, content, 60):
        logging.error("Memcache set of %s failed." % url)
    self.response.out.write(self._whitelist(content))

  def post(self):
    """Whitelists the content included in the post body."""
    self.response.headers['Content-Type'] = 'text/html'
    self.response.out.write(self._whitelist(self.request.body))
    self.response.out.write("\n")

  def _error(self, message):
    """Prints an error message as type text/plain.

    Args:
      error: The plain text error message.
    """
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write(message)
    self.response.out.write("\n")

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
    

application = webapp.WSGIApplication([('/whitelist/?', HtmlWhitelist),
                                      ('/', Usage)], 
                                     debug=True)


def main():
  run_wsgi_app(application)


if __name__ == "__main__":
  main()
