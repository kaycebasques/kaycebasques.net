:date: 2026-07-15
:desc: A proof-of-concept embedding an Elm app within Sphinx built with Bazel.

Hello, Elm!
===========

The random number below is a proof-of-concept that I can generate and embed an
`Elm <https://elm-lang.org/>`_ app within this `Sphinx
<https://www.sphinx-doc.org/en/master/>`_ site. Everything is hermetically
built with Bazel.

.. raw:: html

   <noscript>
     You must have JS enabled to generate the random number.
   </noscript>
   <div id="elm"></div>
   <script src="./foo.js"></script>
   <script>
     var app = Elm.Main.init({node: document.getElementById('elm')});
   </script>
