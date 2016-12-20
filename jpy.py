#!/usr/bin/env python
# vim: fileencoding=utf-8

import os
import re
import sqlite3
import xml.sax
import gzip

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


class JMDictHandler(xml.sax.handler.ContentHandler):

  def __init__(self, db_output):
    if not isinstance(sqlite3, sqlite3.Connection):
      db_output = sqlite3.connect(db_output)
    self.db_output = db_output

  # Collect entity declarations, to back-resolve entities
  def EntityDeclHandler(self, entityName, is_parameter_entity, value, base, systemId, publicId, notationName):
    self.entities[value] = entityName

  def startDocument(self):
    self._locator._ref._parser.EntityDeclHandler = self.EntityDeclHandler
    self.entities = {}

    self.cur_entry = None
    self.cur_sense = None
    self.txt = None
    self.kanji_values = []
    self.reading_values = []
    self.sense_values = []
    self.gloss_values = []


  def endDocument(self):
    with self.db_output as conn:
      for s in ('kanji', 'reading', 'sense', 'gloss'):
        conn.execute("DROP TABLE IF EXISTS %s" % s)

      conn.execute("""
      CREATE TABLE kanji (
        ent_id INT NOT NULL,
        keb TINYTEXT NOT NULL
      )
      """)
      conn.execute("""
      CREATE TABLE reading (
        ent_id INT NOT NULL,
        reb TINYTEXT NOT NULL,
        romaji TINYTEXT NOT NULL
      )
      """)
      conn.execute("""
      CREATE TABLE sense (
        ent_id INT NOT NULL,
        sense_num INT NOT NULL,
        pos VARCHAR(50) NOT NULL,
        attr VARCHAR(50) NOT NULL,
        PRIMARY KEY (ent_id, sense_num)
      )
      """)
      conn.execute("""
      CREATE TABLE gloss (
        ent_id INT NOT NULL,
        sense_num INT NOT NULL,
        lang VARCHAR(5) NOT NULL,
        gloss TEXT NOT NULL
      )
      """)

      conn.executemany("INSERT INTO kanji VALUES (?,?)", self.kanji_values)
      conn.executemany("INSERT INTO reading VALUES (?,?,?)", self.reading_values)
      conn.executemany("INSERT INTO sense VALUES (?,?,?,?)", self.sense_values)
      conn.executemany("INSERT INTO gloss VALUES (?,?,?,?)", self.gloss_values)

      conn.execute("CREATE INDEX k_ent ON kanji (ent_id)")
      conn.execute("CREATE INDEX r_ent ON reading (ent_id)")
      conn.execute("CREATE INDEX g_sense ON gloss (ent_id, sense_num)")

      #conn.execute('VACUUM')
      conn.commit()


  def startElement(self, name, attrs):
    self.txt = ''
    if name == 'entry':
      self.sense = 0
    elif name == 'sense':
      self.pos = []
      self.attr = []
    elif name == 'gloss':
      self.lang = attrs.get('xml:lang', 'en')

  def endElement(self, name):
    self.txt = self.txt.strip()
    if name == 'ent_seq':
      self.cur_entry = int(self.txt)
    elif name == 'keb':
      self.kanji_values.append((self.cur_entry, self.txt))
    elif name == 'reb':
      self.reading_values.append((self.cur_entry, self.txt, kana2romaji(self.txt)))
    elif name == 'sense':
      self.sense_values.append((self.cur_entry, self.sense, ','.join(self.pos), ','.join(self.attr)))
      self.sense += 1
    elif name == 'pos':
      self.pos.append(self.entities[self.txt])
    elif name in ('field', 'dial'):
      self.attr.append(self.entities[self.txt])
    elif name == 'gloss':
      self.gloss_values.append((self.cur_entry, self.sense, self.lang, self.txt))

  def characters(self, content):
    self.txt += content


tbl_hiragana = [
    (u'きゃ', 'kya'), (u'きゅ', 'kyu'), (u'きょ', 'kyo'),
    (u'しゃ', 'sha'), (u'しゅ', 'shu'), (u'しょ', 'sho'),
    (u'ちゃ', 'cha'), (u'ちゅ', 'chu'), (u'ちょ', 'cho'),
    (u'にゃ', 'nya'), (u'にゅ', 'nyu'), (u'にょ', 'nyo'),
    (u'ひゃ', 'hya'), (u'ひゅ', 'hyu'), (u'ひょ', 'hyo'),
    (u'みゃ', 'mya'), (u'みゅ', 'myu'), (u'みょ', 'myo'),
    (u'りゃ', 'rya'), (u'りゅ', 'ryu'), (u'りょ', 'ryo'),
    (u'ぎゃ', 'gya'), (u'ぎゅ', 'gyu'), (u'ぎょ', 'gyo'),
    (u'じゃ', 'ja'),  (u'じゅ', 'ju'),  (u'じょ', 'jo'),
    (u'ぢゃ', 'ja'),  (u'ぢゅ', 'ju'),  (u'ぢょ', 'jo'),
    (u'びゃ', 'bya'), (u'びゅ', 'byu'), (u'びょ', 'byo'),
    (u'ぴゃ', 'pya'), (u'ぴゅ', 'pyu'), (u'ぴょ', 'pyo'),
    (u'あ', 'a'),   (u'い', 'i'),   (u'う', 'u'),   (u'え', 'e'),   (u'お', 'o'),
    (u'か', 'ka'),  (u'き', 'ki'),  (u'く', 'ku'),  (u'け', 'ke'),  (u'こ', 'ko'),
    (u'さ', 'sa'),  (u'し', 'shi'), (u'す', 'su'),  (u'せ', 'se'),  (u'そ', 'so'),
    (u'た', 'ta'),  (u'ち', 'chi'), (u'つ', 'tsu'), (u'て', 'te'),  (u'と', 'to'),
    (u'な', 'na'),  (u'に', 'ni'),  (u'ぬ', 'nu'),  (u'ね', 'ne'),  (u'の', 'no'),
    (u'は', 'ha'),  (u'ひ', 'hi'),  (u'ふ', 'fu'),  (u'へ', 'he'),  (u'ほ', 'ho'),
    (u'ま', 'ma'),  (u'み', 'mi'),  (u'む', 'mu'),  (u'め', 'me'),  (u'も', 'mo'),
    (u'や', 'ya'),  (u'ゆ', 'yu'),  (u'よ', 'yo'),
    (u'ら', 'ra'),  (u'り', 'ri'),  (u'る', 'ru'),  (u'れ', 're'),  (u'ろ', 'ro'),
    (u'わ', 'wa'),  (u'ゐ', 'wi'),  (u'ゑ', 'we'),  (u'を', 'wo'),
    (u'ん', 'n'),
    (u'が', 'ga'),  (u'ぎ', 'gi'),  (u'ぐ', 'gu'),  (u'げ', 'ge'),  (u'ご', 'go'),
    (u'ざ', 'za'),  (u'じ', 'ji'),  (u'ず', 'zu'),  (u'ぜ', 'ze'),  (u'ぞ', 'zo'),
    (u'だ', 'da'),  (u'ぢ', 'ji'),  (u'づ', 'zu'), (u'で', 'de'),  (u'ど', 'do'),
    (u'ば', 'ba'),  (u'び', 'bi'),  (u'ぶ', 'bu'),  (u'べ', 'be'),  (u'ぼ', 'bo'),
    (u'ぱ', 'pa'),  (u'ぴ', 'pi'),  (u'ぷ', 'pu'),  (u'ぺ', 'pe'),  (u'ぽ', 'po'),
    (u'ぁ', 'a'),   (u'ぃ', 'i'),   (u'ぅ', 'u'),   (u'ぇ', 'e'),   (u'ぉ', 'o'),
    ]

tbl_katakana = [
    (u'イェ', 'ye'),
    (u'ヴァ', 'va'),  (u'ヴィ', 'vi'),  (u'ヴェ', 've'),  (u'ヴォ', 'vo'),
    (u'ヴャ', 'vya'), (u'ヴュ', 'vyu'), (u'ヴョ', 'vyo'),
    (u'ブュ', 'byu'),
    (u'シェ', 'she'), (u'ジェ', 'je'),
    (u'チェ', 'che'),
    (u'スィ', 'si'),  (u'ズィ', 'zi'),
    (u'ティ', 'ti'),  (u'トゥ', 'tu'),  (u'テュ', 'tyu'), (u'ドュ', 'dyu'),
    (u'ディ', 'di'),  (u'ドゥ', 'du'),  (u'デュ', 'dyu'),
    (u'ツァ', 'tsa'), (u'ツィ', 'tsi'), (u'ツェ', 'tse'), (u'ツォ', 'tso'),
    (u'ファ', 'fa'),  (u'フィ', 'fi'),  (u'ホゥ', 'hu'),  (u'フェ', 'fe'),  (u'フォ', 'fo'),   (u'フュ', 'fyu'),
    (u'ウィ', 'wi'),  (u'ウェ', 'we'),  (u'ウォ', 'wo'),
    (u'クヮ', 'kwa'), (u'クァ', 'kwa'), (u'クィ', 'kwi'), (u'クェ', 'kwe'), (u'クォ', 'kwo'),
    (u'グヮ', 'gwa'), (u'グァ', 'gwa'), (u'グィ', 'gwi'), (u'グェ', 'gwe'), (u'グォ', 'gwo'),
    (u'ヴ', 'vu'),
    ] + [(''.join(unichr(ord(c)+0x60) for c in k), v) for k,v in tbl_hiragana]

tbl_symbols = [
    (u'〜', '~'), (u'。', '.'), (u'、', ','), (u'　', ' '),
    ]

tbl_all = tbl_hiragana + tbl_katakana + tbl_symbols
kana2romaji_regex = re.compile('|'.join(s for s, _ in tbl_all))
kana2romaji_map = dict(tbl_all)


def kana2romaji(txt):
  txt = unicode(txt)
  txt = kana2romaji_regex.sub(lambda m: kana2romaji_map[m.group()], txt)
  txt = re.sub(ur'[っッ]([bcdfghjkmnprstvwz])', r'\1\1', txt)
  txt = re.sub(ur'([aeiou])ー', r'\1\1', txt)
  txt = re.sub(ur'[・ー−―]', '-', txt)
  txt = re.sub(ur'[っッ]', r'-tsu', txt)
  txt = re.sub(ur'[\uff00-\uff5e]', lambda m: unichr(ord(m.group(0)) - 0xfee0), txt)
  try:
    txt = str(txt)
  except UnicodeEncodeError, e:
    print 'Warning: characters not translated in "%s"' % repr(txt)
    txt = txt.encode('ascii', 'replace')
  return txt


def import_jmdict(fin, output):
  """Import JMdict file into an database

  fin can be a file object or a filename.
  output can be aither an sqlite3 connection or a filename.
  """
  parser = xml.sax.make_parser()
  parser.setContentHandler(JMDictHandler(output))
  print "importing JMdict XML file to database..."
  parser.parse(fin)


# Last JMdict version (English only)
jmdict_url = 'http://ftp.monash.edu.au/pub/nihongo/JMdict_e.gz'



def main():
  import argparse
  parser = argparse.ArgumentParser(description="GTK+ interface for JMdict.")
  parser.add_argument('-d', '--database', metavar='FILE',
      help="SQLite database to use")
  group = parser.add_mutually_exclusive_group()
  group.add_argument('--import', dest='import_url', action='store_true',
      help="import JMdict from public URL")
  group.add_argument('--import-file', metavar='FILE',
      help="import JMdict from a file")
  parser.add_argument('search', nargs='?',
      help="search text")
  args = parser.parse_args()

  import_db = args.import_url or args.import_file

  if args.database is None:
    default_name = 'jpy.sqlite3'
    app_path = os.path.dirname(os.path.realpath(__file__))
    if import_db:
      args.database = os.path.join(app_path, default_name)
    else:
      # DB must exist
      for f in (default_name, os.path.join(app_path, default_name)):
        if os.path.isfile(f):
          args.database = f
          break
      if args.database is None:
        parser.error("cannot find a database file, please use '-d' option")

  if args.import_url:
    import urllib
    from StringIO import StringIO
    print "downloading JMdict..."
    f = StringIO(urllib.urlopen(jmdict_url).read())
    f = gzip.GzipFile(fileobj=f)
    import_jmdict(f, args.database)
  elif args.import_file:
    f = args.import_file
    if f.endswith('.gz'):
      f = gzip.GzipFile(f)
    import_jmdict(f, args.database)

  if import_db and not args.search:
    return

  app = JpyApp(args.database)
  if args.search:
    app.w_search.get_child().set_text(args.search)
    app.w_search.get_child().activate()
  app.main()

if __name__ == '__main__':
  main()

