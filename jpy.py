#!/usr/bin/env python
# vim: fileencoding=utf-8

import os
import re
import sqlite3

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango


class JpyApp:

  def __init__(self, db=None):
    self.window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
    self.window.set_resizable(True)
    self.window.set_size_request(400, 500)
    self.window.set_title('jpy')
    self.window.connect('delete_event', lambda w,e: Gtk.main_quit())

    box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    self.window.add(box)

    self.w_search = Gtk.ComboBoxText.new_with_entry()
    self.w_search.get_child().connect('activate', lambda w: self.display_results(w.get_text()))
    self.w_search.get_child().modify_text(Gtk.StateType.NORMAL, Gdk.color_parse('black'))
    self.w_search.get_child().modify_font(Pango.FontDescription('sans 12'))
    box.pack_start(self.w_search, False, False, 0)

    # Tags (customize style of displayed text here)
    tagtable = Gtk.TextTagTable()
    tag = Gtk.TextTag(name='jap')
    tag.set_property('foreground', 'darkblue')
    tag.set_property('size-points', 14)
    tag.set_property('pixels-above-lines', 8)
    tagtable.add(tag)
    tag = Gtk.TextTag(name='pos')
    tag.set_property('foreground', 'darkred')
    tagtable.add(tag)
    tag = Gtk.TextTag(name='attr')
    tag.set_property('foreground', 'purple')
    tagtable.add(tag)
    tag = Gtk.TextTag(name='sense-num')
    tag.set_property('foreground', 'darkgreen')
    tagtable.add(tag)

    self.w_result = Gtk.TextView(buffer=Gtk.TextBuffer(tag_table=tagtable))
    self.w_result.set_editable(False)
    self.w_result.set_cursor_visible(False)
    self.w_result.set_wrap_mode(Gtk.WrapMode.WORD)
    self.w_result.set_justification(Gtk.Justification.LEFT)
    self.w_result.set_left_margin(6)
    self.w_result.modify_text(Gtk.StateType.NORMAL, Gdk.color_parse('black'))
    self.w_result.modify_font(Pango.FontDescription('sans 12'))

    self.w_display = Gtk.ScrolledWindow()
    self.w_display.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    self.w_display.add_with_viewport(self.w_result)
    box.pack_start(self.w_display, True, True, 0)

    box.show()
    self.w_search.show()
    self.w_result.show()
    self.w_display.show()
    self.window.show()

    # Connect to SQLite database
    if not os.path.isfile(db):
      raise ValueError("database file not found: %s"%db)
    Query.connect(db)


  def main(self):
    Gtk.main()


  def display_results(self, txt):
    buf = self.w_result.get_buffer()
    buf.set_text('')
    if len(txt) == 0:
      return

    result = Query(txt, limit=50).execute()

    self.w_search.get_child().select_region(0, -1)
    self.w_search.prepend_text(txt)
    self.w_search.remove(10)
    it = buf.get_end_iter()

    # Format results (customize display format here)
    for e in result:
      s = ', '.join(e.reb)
      if len(e.keb):
        s = '%s / %s' % (', '.join(e.keb), s)
      buf.insert_with_tags_by_name(it, "%s\n" % s, 'jap')
      for i,s in enumerate(e.sense):
        buf.insert_with_tags_by_name(it, "%d) " % (i+1), 'sense-num')
        if len(s[0]):
          buf.insert_with_tags_by_name(it, '%s  ' % ' '.join(s[0]), 'pos')
        if len(s[1]):
          buf.insert_with_tags_by_name(it, '[%s] ' % ' '.join(s[1]), 'attr')
        buf.insert(it, '%s\n' % ', '.join(s[2]))

    # Scroll at the top
    self.w_display.get_vadjustment().set_value(0)


class Query:
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

    if not s:
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
      tables, fields = ('kanji', 'reading',), ('keb', 'reb',)
    # Fetch results
    query = "SELECT DISTINCT ent_id FROM %s WHERE %s LIKE ? ORDER BY length(%s) LIMIT ?"
    for t,f in zip(tables, fields):
      cursor.execute(query % (t, f, f), (self.pattern, limit))
      ent_id = [x[0] for x in cursor]
      if ent_id:
        break

    ent_id_list = '(%s)' % ','.join(str(i) for i in ent_id)

    # Dictionary is not sorted,
    # Entry order is still obtained from ent_id.
    result = {e: Entry(e) for e in ent_id}

    cursor.execute("SELECT ent_id, keb FROM kanji WHERE ent_id IN %s" % ent_id_list)
    for s in cursor:
      result[s[0]].keb.append(s[1])
    cursor.execute("SELECT ent_id, reb FROM reading WHERE ent_id IN %s" % ent_id_list)
    for s in cursor:
      result[s[0]].reb.append(s[1])
    cursor.execute("SELECT ent_id, sense_num, pos, attr FROM sense WHERE ent_id IN %s ORDER BY ent_id, sense_num" % ent_id_list)
    for s in cursor:
      result[s[0]].sense.append((filter(None, s[2].split(',')), filter(None, s[3].split(',')), []))
    cursor.execute("SELECT ent_id, sense_num, gloss FROM gloss WHERE ent_id IN %s" % ent_id_list)
    for s in cursor:
      result[s[0]].sense[s[1]-1][2].append(s[2])

    return [result[e] for e in ent_id]

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
    self.keb = []
    self.reb = []
    self.sense = []


def main():
  import argparse
  parser = argparse.ArgumentParser(description="GTK+ interface for JMdict.")
  parser.add_argument('-d', '--database', metavar='FILE',
      help="SQLite database to use")
  parser.add_argument('search', nargs='?',
      help="search text")
  args = parser.parse_args()

  if args.database is None:
    app_path = os.path.dirname(os.path.realpath(__file__))
    default_name = 'jpy.sqlite3'
    for f in (default_name, os.path.join(app_path, default_name)):
      if os.path.isfile(f):
        args.database = f
        break
    if args.database is None:
      parser.error("cannot find a database file, please use '-d' option")

  app = JpyApp(args.database)
  if args.search:
    app.w_search.get_child().set_text(args.search)
    app.w_search.get_child().activate()
  app.main()

if __name__ == '__main__':
  main()

