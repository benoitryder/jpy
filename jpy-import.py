#!/usr/bin/env python
# vim: fileencoding=utf-8

import xml.sax
import sqlite3
import re, sys


# Last JMdict version (English only)
jmdict_url = 'http://ftp.monash.edu.au/pub/nihongo/JMdict_e.gz'


class JMDictHandler(xml.sax.handler.ContentHandler):

  def __init__(self, db):
    self.db = db

  # Collect entity declarations, to back-resolve entities
  def EntityDeclHandler(self, entityName, is_parameter_entity, value, base, systemId, publicId, notationName):
    self.ent[value] = entityName

  def startDocument(self):
    self._locator._ref._parser.EntityDeclHandler = self.EntityDeclHandler
    self.ent = {}

    self.conn = sqlite3.connect(self.db)
    cursor = self.conn.cursor()

    for s in ('kanji', 'reading', 'sense', 'gloss'):
      cursor.execute("DROP TABLE IF EXISTS %s"%s)

    cursor.execute("""
    CREATE TABLE kanji (
      ent_id INT NOT NULL,
      keb TINYTEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE reading (
      ent_id INT NOT NULL,
      reb TINYTEXT NOT NULL,
      romaji TINYTEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE sense (
      ent_id INT NOT NULL,
      sense_num INT NOT NULL,
      pos VARCHAR(50) NOT NULL,
      attr VARCHAR(50) NOT NULL,
      PRIMARY KEY (ent_id, sense_num)
    )
    """)
    cursor.execute("""
    CREATE TABLE gloss (
      ent_id INT NOT NULL,
      sense_num INT NOT NULL,
      lang VARCHAR(5) NOT NULL,
      gloss TEXT NOT NULL
    )
    """)

    cursor.execute("CREATE INDEX k_ent ON kanji (ent_id)")
    cursor.execute("CREATE INDEX r_ent ON reading (ent_id)")
    #cursor.execute("CREATE INDEX r_reb ON reading (reb)")
    cursor.execute("CREATE INDEX g_sense ON gloss (ent_id, sense_num)")
    #cursor.execute("CREATE INDEX g_gloss ON gloss (gloss)")

    self.conn.commit()

    self.cur_entry = None
    self.cur_sense = None
    self.txt = None


  def endDocument(self):
    self.conn.execute('VACUUM')
    self.conn.commit()
    self.conn.close()

  def startElement(self, name, attrs):
    self.txt = ''
    if name == 'entry':
      self.sense = 0
    elif name == 'sense':
      self.pos = []
      self.attr = []
    elif name == 'gloss':
      if attrs.has_key('xml:lang'):
        self.lang = attrs.getValue('xml:lang')
      else:
        self.lang = None

  def endElement(self, name):
    self.txt = self.txt.strip()
    if name == 'ent_seq':
      self.cur_entry = int(self.txt)
    elif name == 'keb':
      self.conn.execute("INSERT INTO kanji VALUES (?,?)", (self.cur_entry, self.txt))
    elif name == 'reb':
      self.conn.execute("INSERT INTO reading VALUES (?,?,?)", (self.cur_entry, self.txt, kana2romaji(self.txt)))
    elif name == 'sense':
      self.conn.execute("INSERT INTO sense VALUES (?,?,?,?)",
          (self.cur_entry, self.sense, ','.join(self.pos), ','.join(self.attr)))
      self.sense += 1
    elif name == 'pos':
      self.pos.append(self.ent[self.txt])
    elif name in ('field', 'dial',):
      self.attr.append(self.ent[self.txt])
    elif name == 'gloss':
      if self.lang is None:
        self.lang = 'en'
      self.conn.execute("INSERT INTO gloss VALUES (?,?,?,?)",
          (self.cur_entry, self.sense, self.lang, self.txt))

  def characters(self, content):
    self.txt += content


tbl_hiragana = (
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
    )

tbl_katakana = (
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
    ) + tuple([ (''.join(unichr(ord(c)+0x60) for c in k), v) for k,v in tbl_hiragana])

tbl_symbols = (
    (u'〜', '~'), (u'。', '.'), (u'、', ','), (u'　', ' '),
    )

def kana2romaji(txt):
  txt = unicode(txt)
  for k,v in tbl_hiragana + tbl_katakana + tbl_symbols:
    txt = txt.replace(k, v)
  txt = re.sub(ur'[っッ]([bcdfghjkmnprstvwz])', r'\1\1', txt)
  txt = re.sub(ur'([aeiou])ー', r'\1\1', txt)
  txt = re.sub(ur'[・ー−―]', '-', txt)
  txt = re.sub(ur'[っッ]', r'-tsu', txt)
  txt = re.sub(ur'[\uff00-\uff5e]', lambda m: unichr(ord(m.group(0))-0xfee0), txt)
  try:
    txt = str(txt)
  except UnicodeEncodeError, e:
    print >>sys.stderr, 'Warning: characters not translated in "%s"'% repr(txt)
    txt = txt.encode('ascii', 'replace')
  return txt



if __name__ == '__main__':
  import argparse
  import gzip, urllib, StringIO

  parser = argparse.ArgumentParser(description="""\
Build jpy database from XML JMdict.
JMdict can be provided as a file or downloaded (~5MB).
If filename ends with '.gz', it is automatically gunzipped.
""")
  parser.add_argument('-d', '--download', action='store_true',
      help="download lastest JMdict (take some time)")
  parser.add_argument('-o', '--output', metavar='FILE', default='jpy.db',
      help="output db file (default 'jpy.sqlite3')")
  parser.add_argument('xmlfile', nargs='?',
      help="JMdict XML file")
  args = parser.parse_args()
  
  if args.download and args.xmlfile:
    parser.error("cannot use -d with a manually set XML file")

  if args.download:
    print "downloading JMdict..."
    f = StringIO.StringIO(urllib.urlopen(jmdict_url).read())
    f = gzip.GzipFile(fileobj=f)
  elif args.xmlfile:
    f = args.xmlfile
    if f.endswith('.gz'):
      f = gzip.GzipFile(f)
  else:
    parser.error("either -d or an XML file must be provided")

  parser = xml.sax.make_parser()
  parser.setContentHandler(JMDictHandler(args.output))
  parser.parse(f)

