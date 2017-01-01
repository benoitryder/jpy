jpydict
=======

jpydict is a graphical interface for the JMdict Japanese/English dictionary.
It uses GTK+.

For more information on the JMdict project and license terms, please refer to
the `JMdict project page <http://www.edrdg.org/jmdict/j_jmdict.html>`_.


Installation
------------

To install jpydict::

  pip install jpydict

Or simply download it, it's a single-file script::

  https://github.com/benoitryder/jpydict/raw/master/jpydict

jpydict depends on `PyGObject <https://wiki.gnome.org/Projects/PyGObject>`_
(aka PyGI). Make sure to install PyGObject version 3 at least. jpydict will not
work with PyGObject 2.X.

It is available on most Linux distribution in package python-gi or
python-gobject.

On Windows, dependencies can be downloaded from
`this page <https://sourceforge.net/projects/pygobjectwin32/files/?source=navbar>`_.
The easiest way is to install *pygi-aio*; make sure to install the following
components: gtk3, pango.


Use
---

On first launch, jpydict will download the JMdict dictionary file and store it
locally into a database.
Dictionnary can then be updated from the *Help* window.

Click on the *Help* button in the top right corner for information on how to
search for translations.

