############
Installation
############

Currently, this is not in https://pypi.org.

Consequently, it is installed via a slightly more complex sequence of commands.

::

    git clone https://github.com/slott56/DataSynthTool.git
    python -m pip install -e DataSynthTool

An alternative to using PIP is to add the project's ``src`` directory to :envvar:`PYTHONPATH`.

::

    export PYTHONPATH=$PYTHONPATH:/path/to/DataSynthTool/src
