#!/usr/bin/env python2.7
# vim: fileencoding=utf-8

import os
import sys
import re
import sqlite3
import time
import xml.parsers.expat
import urllib2
import gzip
import zlib

__version__ = '1.0.0'

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, Pango


class JpydictApp:

  def __init__(self, db=None):
    self.window = Gtk.Window(Gtk.WindowType.TOPLEVEL)
    self.window.set_resizable(True)
    self.window.set_size_request(400, 500)
    self.window.set_title('jpydict')
    self.window.connect('delete_event', lambda w,e: Gtk.main_quit())

    vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    self.window.add(vbox)

    hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)

    self.w_search = Gtk.ComboBoxText.new_with_entry()
    self.w_search.get_child().connect('activate', lambda w: self.display_results(w.get_text()))
    self.w_search.get_child().modify_text(Gtk.StateType.NORMAL, Gdk.color_parse('black'))
    self.w_search.get_child().modify_font(Pango.FontDescription('sans 12'))
    hbox.pack_start(self.w_search, True, True, 0)

    self.w_help = Gtk.Button.new_from_icon_name("help-faq", Gtk.IconSize.BUTTON)
    self.w_help.connect('clicked', self.show_help)
    hbox.pack_start(self.w_help, False, False, 0)

    vbox.pack_start(hbox, False, False, 0)

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
    vbox.pack_start(self.w_display, True, True, 0)

    self.window.show_all()

    # Connect to SQLite database
    # Prompt for dictionary update if database is empty or does not exist
    self.conn = sqlite3.connect(db)
    row = self.conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='version'").fetchone()
    if row is None:
      self.update_dictionary(self.window)


  def main(self):
    Gtk.main()


  def display_results(self, txt):
    buf = self.w_result.get_buffer()
    buf.set_text('')
    if len(txt) == 0:
      return

    result = Query(self.conn, txt.decode('utf-8'), limit=50).execute()

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

  def show_help(self, w):
    dialog = Gtk.Dialog("Help", self.window)
    dialog.set_resizable(False)

    box = dialog.get_content_area()

    tbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 5)
    tbox.set_margin_start(10)
    tbox.set_margin_end(10)
    tbox.set_margin_top(10)
    tbox.set_margin_bottom(20)
    box.add(tbox)

    custom_markups = [
        ('{em}', '<span bgcolor="black" bgalpha="10%">'),
        ('{/em}', '</span>'),
        ]

    def text_label(markup, **props):
      for pat,sub in custom_markups:
        markup = markup.replace(pat, sub)
      label = Gtk.Label()
      label.set_markup(markup)
      label.set_halign(Gtk.Align.START)
      if props:
        for k,v in props.items():
          getattr(label, 'set_%s' % k)(v)
      return label

    tbox.add(text_label("<big><b>jpydict v%s</b></big>" % __version__, halign=0.5))
    tbox.add(text_label("<b>How to search</b>", margin_top=10, margin_left=20))
    tbox.add(text_label(
      "To translate Japanese into English, enter Japanese (kanjis, kanas, romanization)."))
    tbox.add(text_label(
      "To translate English into Japanese, start with a {em}/{/em} followed by the English text.\n"
      "For instance, searching for {em}/dictionary{/em} will return {em}字引{/em}."))
    tbox.add(text_label(
      "Wildcards characters can be used for more refined searches.\n"
      "Without wildcards, search will match anything starting with the given pattern.\n"
      "  {em}*{/em} or {em}%{/em} replace any text: {em}pi*e{/em} searches for {em}pie{/em}, {em}pipe{/em}, {em}piece{/em}, ...\n"
      "  {em}?{/em} or {em}_{/em} replace a single character: {em}?回{/em} searches for {em}何回{/em}, {em}今回{/em} but not {em}一次回{/em}.", margin_top=5))
    tbox.add(text_label(
      "Romanization uses the usual kana to latin conversion.\n"
      "Long voyels are transcribed similarly to hiraganas:\n"
      "{em}先生{/em} becomes {em}sensei{/em},"
      " {em}大{/em} becomes {em}oo{/em},"
      " {em}ローマ{/em} becomes {em}roomaji{/em}."))

    tbox.add(text_label("<b>Dictionary</b>", margin_top=10, margin_left=20))
    dict_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
    dict_txt_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
    tbox.add(dict_box)
    dict_box.add(dict_txt_box)
    dict_txt_box.add(text_label(
      "This application uses Japanese dictionary from the JMdict project.\n"
      "<a href='http://www.edrdg.org/jmdict/j_jmdict.html'>More information and license terms.</a>"))
    w_update = Gtk.Button.new_with_label("Update\ndictionary")
    w_update.set_margin_left(20)
    w_update.get_child().set_justify(Gtk.Justification.CENTER)
    dict_box.add(w_update)

    updated_at_label = text_label('')
    def update_updated_at():
      row = self.conn.execute("SELECT updated_at FROM version").fetchone()
      d = (time.time() - row[0]) / 86400
      if d < 1:
        txt = "today"
      elif d < 2:
        txt = "yesterday"
      else:
        txt = "%d days ago" % d
      updated_at_label.set_text("Last update: %s." % txt)
    update_updated_at()
    dict_txt_box.add(updated_at_label)

    w_update.connect('clicked', lambda w: self.update_dictionary(dialog, update_updated_at))

    # create close button but reparent it to align it
    w_close = dialog.add_button("_Close", Gtk.ResponseType.CLOSE)
    w_close.get_parent().remove(w_close)
    box.add(w_close)

    dialog.show_all()
    dialog.run()
    dialog.destroy()

  def update_dictionary(self, parent, on_update=None):
    dialog = Gtk.Dialog("Dictionary update", parent)
    dialog.set_modal(True)
    dialog.set_resizable(False)
    dialog.set_size_request(350, -1)

    box = dialog.get_content_area()
    box.set_margin_start(10)
    box.set_margin_end(10)
    box.set_margin_top(10)
    box.set_margin_bottom(20)

    label = Gtk.Label()
    label.set_margin_bottom(10)
    bar = Gtk.ProgressBar()
    box.add(label)
    box.add(bar)
    dialog.show_all()

    class AbortException(Exception):
      pass

    def reporter(msg, progress):
      if msg is None:
        label.set_text("Dictionary update")
        bar.set_fraction(1)
      else:
        label.set_text(msg)
        if progress is None:
          bar.pulse()
        else:
          bar.set_fraction(progress)
      if not dialog.get_visible():
        raise AbortException()  # dialog has been closed, abort
      while Gtk.events_pending():
        Gtk.main_iteration()

    dialog.present()
    while Gtk.events_pending():
      Gtk.main_iteration()
    loader = JMDictLoader(self.conn, reporter)
    try:
      loader.load_url()
    except AbortException:
      pass  # ignore

    dialog.destroy()
    if on_update:
      on_update()


class Query:
  """Search query and database connection.

  Instance attributes:
    conn -- SQLite Connection object
    to_jp -- search for Japanese translation (default: False)
    pattern -- search pattern, with (converted) wildcards
    limit -- maximum number of results (no limit: negative number, the default)

  Instance methods:
    build -- build a query from an ordinary search string
    execute -- execute the query and return the result Entry list

  Instance attribute:

  """

  conn = None

  def __init__(self, conn, s=None, to_jp=False, limit=None):
    """Build a query.
    Arguments values may be overwritten by special tags in search string.

    """

    self.conn = conn
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


class JMDictLoader:
  """Load JMdict to database.

  output can be either an sqlite3 connection or a filename.

  reporter is a method used to report loading progress:
    reporter(step, progress)
  Where step is a string describing current step and progress the progress of
  the current step, from 0 to 1, None if unknown.
  reporter(None, None) is called at the end.
  """

  # Last JMdict version (English only)
  jmdict_url = 'http://ftp.monash.edu.au/pub/nihongo/JMdict_e.gz'

  def __init__(self, db_output, reporter):
    if not isinstance(db_output, sqlite3.Connection):
      db_output = sqlite3.connect(db_output)
    self.db_output = db_output
    self.reporter = reporter
    self.parser = xml.parsers.expat.ParserCreate()
    self.parser.StartElementHandler = self.startElement
    self.parser.EndElementHandler = self.endElement
    self.parser.CharacterDataHandler = self.characterData
    self.parser.EntityDeclHandler = self.entityDecl

  def load_url(self):
    """Load JMdict from public URL

    Download and process by chunks to have progress and parallelize a bit.
    """

    result = urllib2.urlopen(self.jmdict_url)
    try:
      total_size = float(result.info().getheader('Content-Length').strip())
    except AttributeError:
      total_size = None

    dec = zlib.decompressobj(32 + zlib.MAX_WBITS)  # offset 32 to skip the header
    read_size = 0
    self.startDocument()
    while True:
      self.reporter("Download and process XML dictionary file",
                    None if total_size is None else read_size / total_size)
      chunk = result.read(10240)
      if not chunk:
        break
      read_size += len(chunk)
      self.parser.Parse(dec.decompress(chunk))
    self.parser.Parse('', True)
    self.endDocument()
    self.reporter(None, None)

  def load_file(self, path):
    """Load JMdict from a file"""

    if path.endswith('.gz'):
      f = gzip.GzipFile(path)
    else:
      f = open(path, 'rb')
    self.reporter("Process XML dictionary file", None)
    self.startDocument()
    self.parser.ParseFile(f)
    self.endDocument()
    self.reporter(None, None)


  # Collect entity declarations, to back-resolve entities
  def entityDecl(self, entityName, is_parameter_entity, value, base, systemId, publicId, notationName):
    self.entities[value] = entityName

  def startDocument(self):
    self.entities = {}
    self.cur_entry = None
    self.cur_sense = None
    self.txt = None
    self.kanji_values = []
    self.reading_values = []
    self.sense_values = []
    self.gloss_values = []


  def endDocument(self):
    self.reporter("Updating database", None)

    with self.db_output as conn:
      for s in ('kanji', 'reading', 'sense', 'gloss', 'version'):
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
      conn.execute("""
      CREATE TABLE version (
        updated_at INT NOT NULL
      )
      """)

      conn.executemany("INSERT INTO kanji VALUES (?,?)", self.kanji_values)
      conn.executemany("INSERT INTO reading VALUES (?,?,?)", self.reading_values)
      conn.executemany("INSERT INTO sense VALUES (?,?,?,?)", self.sense_values)
      conn.executemany("INSERT INTO gloss VALUES (?,?,?,?)", self.gloss_values)

      conn.execute("CREATE INDEX k_ent ON kanji (ent_id)")
      conn.execute("CREATE INDEX r_ent ON reading (ent_id)")
      conn.execute("CREATE INDEX g_sense ON gloss (ent_id, sense_num)")

      conn.execute("INSERT INTO version VALUES (?)", (int(time.time()),))
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

  def characterData(self, content):
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
    import appdirs
    data_dir = appdirs.user_data_dir('jpydict', '')
    if not os.path.isdir(data_dir):
      os.makedirs(data_dir)
    args.database = os.path.join(data_dir, 'jpydict.sqlite3')

  if import_db:
    def reporter(msg, progress):
      if msg is None:
        sys.stdout.write("\n")
      else:
        if progress is not None:
          msg = "%s  (%3d%%)" % (msg, int(progress * 100))
        # assume all messages fit on 72 chars
        sys.stdout.write("\r%s%s" % (msg, ' ' * (72 - len(msg))))

    loader = JMDictLoader(args.database, reporter)
    if args.import_url:
      loader.load_url()
    elif args.import_file:
      loader.load_file(args.import_file)

  if import_db and not args.search:
    return

  app = JpydictApp(args.database)
  if args.search:
    app.w_search.get_child().set_text(args.search)
    app.w_search.get_child().activate()
  app.main()

if __name__ == '__main__':
  main()

