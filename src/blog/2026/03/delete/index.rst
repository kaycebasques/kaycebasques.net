:date: 2026-03-21
:desc: Recursively delete all files matching a pattern using find.

===============================================
Recursively delete all files matching a pattern
===============================================

E.g. to delete every JSON file:

.. code-block:: console

   find . -name "*.json" -type f -delete
