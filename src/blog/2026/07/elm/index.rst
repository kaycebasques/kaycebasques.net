Hello, Elm!
===========
The ``Hello, Elm!`` message below is a proof-of-concept that I can generate
and embed `Elm <https://elm-lang.org/>`_ apps within
`Sphinx <https://www.sphinx-doc.org/en/master/>`_.

.. raw:: html

   <noscript>
     You must have JS enabled to view the embedded Elm app that follows.
   </noscript>
   <div id="elm"></div>
   <script src="main_js.js"></script>
   <script>
     var app = Elm.Main.init({
       node: document.getElementById('elm')
     });
   </script>
