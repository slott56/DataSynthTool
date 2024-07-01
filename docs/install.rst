############
Installation
############

Currently, this is not in https://pypi.org.

Consequently, it is installed via a slightly more complex pair of commands.

::

    git clone whatever
    python -m pip install -e whatever

An alternative to using PIP is to add the project's ``src`` directory to :envvar:`PYTHONPATH`.

::

    export PYTHONPATH=$PYTHONPATH:/path/to/whatever
