=================================================================
Quickly create reStructuredText overlines (and underlines) in Vim
=================================================================

I format H1-level section titles in reStructuredText with an overline
and underline, like this:

.. code-block:: rst
   
   =============
   Hello, world!
   =============

The sequence of ``=`` characters above ``Hello, world!`` is the overline, and
the sequence below is the underline.

To quickly create overlines and underlines in Vim:

#. Write the H1-level section title text.

   .. code-block:: rst
   
      Hello, world!

#. Yank the line with ``yy`` and then duplicate it with ``p``.

   .. code-block:: rst
   
      Hello, world!
      Hello, world!

#. Press ``Vr=`` to create the underline.

   .. code-block:: rst
   
      Hello, world!
      =============

#. Yank the underline with ``yy`` then press ``kk`` to move up 2 lines then
   ``p`` to paste.

   .. code-block:: rst
   
      =============
      Hello, world!
      =============
