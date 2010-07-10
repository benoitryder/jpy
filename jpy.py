#!/usr/bin/env python
# vim: fileencoding=utf-8

import sqlite3, re, os

import pygtk
pygtk.require('2.0')
import gtk, pango


class JpyApp:

  def __init__(self, db=None):
    self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
    self.window.set_resizable(True)
    self.window.set_size_request(350,350)
    self.window.set_title('jpy')
    self.window.connect('delete_event', lambda w,e: gtk.main_quit())

    box = gtk.VBox(False, 0)
    self.window.add(box)

    self.w_search = gtk.combo_box_entry_new_text()
    self.w_search.child.connect('activate', lambda w: self.display_results(w.get_text()))
    self.w_search.child.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
    self.w_search.child.modify_font(pango.FontDescription('sans 12'))
    box.pack_start(self.w_search, expand=False, fill=False)

    # Tags (customize style of displayed text here)
    tagtable = gtk.TextTagTable()
    tag = gtk.TextTag('jap')
    tag.set_property('foreground', 'darkblue')
    tag.set_property('size-points', 14)
    tag.set_property('pixels-above-lines', 8)
    #tag.set_property('weight', pango.WEIGHT_BOLD)
    tagtable.add(tag)
    tag = gtk.TextTag('pos')
    tag.set_property('foreground', 'darkred')
    tagtable.add(tag)
    tag = gtk.TextTag('attr')
    tag.set_property('foreground', 'purple')
    tagtable.add(tag)
    tag = gtk.TextTag('sense-num')
    tag.set_property('foreground', 'darkgreen')
    tagtable.add(tag)
  
    self.w_result = gtk.TextView(gtk.TextBuffer(tagtable))
    self.w_result.set_editable(False)
    self.w_result.set_cursor_visible(False)
    self.w_result.set_wrap_mode(gtk.WRAP_WORD)
    self.w_result.set_justification(gtk.JUSTIFY_LEFT)
    self.w_result.modify_text(gtk.STATE_NORMAL, gtk.gdk.color_parse('black'))
    self.w_result.modify_font(pango.FontDescription('sans 12'))

    self.w_display = gtk.ScrolledWindow()
    self.w_display.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
    self.w_display.add_with_viewport(self.w_result)
    box.pack_start(self.w_display, expand=True, fill=True)

    box.show()
    self.w_search.show()
    self.w_result.show()
    self.w_display.show()
    self.window.show()

    # Connect to SQLite database
    if db is None:
      db = os.path.join(os.path.dirname(__file__),'jpy.db')
    Query.connect(db)


  def main(self):
    gtk.main()


  def display_results(self, txt):
    buffer = self.w_result.get_buffer()
    buffer.set_text('')
    if len(txt) == 0:
      return

    result = Query(txt, limit=50).execute()

    self.w_search.child.select_region(0,-1)
    self.w_search.prepend_text(txt)
    self.w_search.remove_text(10)
    iter = buffer.get_end_iter()

    # Format results (customize display format here)
    for e in result:
      s = ', '.join(e.reb)
      if len(e.keb):
        s = ', '.join(e.keb) + ' / ' + s
      buffer.insert_with_tags_by_name(iter, s+"\n", 'jap')
      for i,s in enumerate(e.sense):
        buffer.insert_with_tags_by_name(iter, "%d) "%(i+1), 'sense-num')
        if len(s[0]) > 0:
          buffer.insert_with_tags_by_name(iter, ' '.join(s[0])+'  ', 'pos')
        if len(s[1]) > 0:
          buffer.insert_with_tags_by_name(iter, '['+' '.join(s[1])+'] ', 'attr')
        buffer.insert(iter, ', '.join(s[2])+'\n')

    # Scroll at the top
    self.w_display.get_vadjustment().set_value(0)


class Query():
  """Search query and database connection.

  Instance attributes:
    to_jp -- search for Japanese translation (default: False)
    pattern -- search pattern, with (converted) wildcards
    limit -- maximum number of results (no limit: negative number, the default)

  Instance methods:
    build -- build a query from an ordinary search string
    execute -- execute the query and return the result Entry list

  Class method:
    connect -- initialize the SQLite DB connection
  
  Class attribute:
    conn -- SQLite Connection object

  Instance attribute:

  """

  conn = None

  def __init__(self, s=None, to_jp=False, limit=None):
    """Build a query.
    Arguments values may be overwritten by special tags in search string.

    """

    self.to_jp = to_jp
    self.limit = limit
    self.pattern = None
    if s is not None:
      self.build(s)

  def build(self, s):
    """Build a query from an ordinary search string.

    If there is no special character, 'pat' is equivalent to 'pat%'.

    Special characters:
      *, % : 0 or more characters
      ?, _ : single character
      / as first character : translate to Japanese
    
    """

    if len(s) == 0:
      return ''

    s = unicode(s)
    if s[0] == '/':
      self.to_jp = True
      s = s[1:]
    s = re.sub(ur'[*＊％]', '%', s)
    s = re.sub(ur'[?？＿]', '_', s)
    if re.search(r'[_%]', s) is None:
      self.pattern = s + '%'
    else:
      self.pattern = s

  def execute(self):
    """Execute the query and return the result Entry list."""

    cursor = self.conn.cursor()
    limit = self.limit
    if limit is None:
      limit = -1

    # Get ent_id to display
    if self.to_jp:
      # To Japanese
      tables, fields = ('gloss',), ('gloss',)
    elif re.match('^[ -~]*$', self.pattern):
      # ASCII only: romaji
      tables, fields = ('reading',), ('romaji',)
    else:
      # Unicode: first kanji, then kana
      tables, fields = ('kanji','reading',), ('keb','reb',)
    # Fetch results
    query = "SELECT DISTINCT ent_id FROM %s WHERE %s LIKE ? ORDER BY length(%s) LIMIT ?"
    for t,f in zip(tables,fields):
      cursor.execute(query % (t, f, f), (self.pattern,limit))
      ent_id = tuple( x[0] for x in cursor )
      if len(ent_id) != 0:
        break

    ent_id_list = '(%s)' % ','.join(str(i) for i in ent_id)

    # Note: a dictionary is not sorted
    # Entry order is still obtained from ent_id.
    result = dict( (e,Entry(e)) for e in ent_id )

    cursor.execute("SELECT ent_id, keb FROM kanji WHERE ent_id IN %s" % ent_id_list)
    for s in cursor:
      result[s[0]].keb.append(s[1])
    cursor.execute("SELECT ent_id, reb FROM reading WHERE ent_id IN %s" % ent_id_list)
    for s in cursor:
      result[s[0]].reb.append(s[1])
    cursor.execute("SELECT ent_id, sense_num, pos, attr FROM sense WHERE ent_id IN %s ORDER BY ent_id, sense_num" % ent_id_list)
    for s in cursor:
      result[s[0]].sense.append( (filter(None, s[2].split(',')), filter(None, s[3].split(',')), []) )
    cursor.execute("SELECT ent_id, sense_num, gloss FROM gloss WHERE ent_id IN %s" % ent_id_list)
    for s in cursor:
      result[s[0]].sense[s[1]-1][2].append( s[2] )

    return tuple( result[e] for e in ent_id )

  @classmethod
  def connect(cls, dbfile):
    cls.conn = sqlite3.connect(dbfile)


class Entry:
  """Dictionary entry.

  Attributes:
    seq -- entry seq ID
    keb -- kanji writings
    reb -- kana writings
    sense -- definition list (pos list, attr. list, gloss list)
  
  """

  def __init__(self, seq):
    self.seq = seq
    self.keb, self.reb, self.sense = [], [], []



if __name__ == '__main__':
  from optparse import OptionParser

  parser = OptionParser(
      description="PyGTK interface for JMdict.",
      usage="%prog [OPTIONS] [SEARCH]"
      )
  parser.add_option('-d', dest='db', metavar='FILE',
      help="SQLite database to use")
  (opts, args) = parser.parse_args()

  app = JpyApp(opts.db)
  if len(args) > 0:
    app.w_search.child.set_text(args[0])
    app.w_search.child.activate()
  app.main()

