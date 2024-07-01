..  _code:

###########
Code
###########

In this section we'll look at the sample application.
This comes in two parts: the schema and the main application to emit rows.

Schema
=======

We'll look at the ``sample_schema.py`` module.

First, the imports.

.. literalinclude:: ../tests/sample_schema.py
   :lines: 5-7

Next the ``Employee`` model.

.. literalinclude:: ../tests/sample_schema.py
   :lines: 10-43

Note that each field has annotations to define the desired synthetic data.

Finally, the ``Manager`` model.

.. literalinclude:: ../tests/sample_schema.py
   :lines: 46-62

Note that each field has annotations to define the desired synthetic data.

Yes, these are what are often called "anemic" models.
They lack any methods or processing related to the relationships between the two items.

Data Generator App
==================

Here's the ``sample_app.py`` module.
Starting with the imports

.. literalinclude:: ../tests/sample_app.py
   :lines: 5-9

The main function does four separate things.

1. Dump the available synthesizers.

2. Build a schema.

3. Export ``Employee`` data.

4. Export ``Manager`` data.


.. literalinclude:: ../tests/sample_app.py
   :lines: 12-16

The :py:func:`synthdata.base.synth_class_iter` emits a sequence of (name, class) pairs.
Generally, if the class lacks a docstring on the :py:meth:`synthdata.base.Synthesizer.match`` method, it means the class is abstract.

.. literalinclude:: ../tests/sample_app.py
   :lines: 18-20

The schema, ``s``, is populated with two classes.
This will build :py:meth:`synthdata.base.ModelSynthesizer` instances for each class.
Any pooled synthesizers will be used to fill the needed PK pools.

.. literalinclude:: ../tests/sample_app.py
   :lines: 22-29

This writes ``Employee`` instances to both the console and a file.
The ``csv`` module's ``DictWriter`` class is initialized with the field names from the ``Employee`` class.
Then each object's ``dict()`` result is used to write a row to the file.

Note that only key values are pooled. The ``Employee`` instances are built as needed from the key pool.

.. literalinclude:: ../tests/sample_app.py
   :lines: 31-35

This writes ``Manager`` instances to a file.
The ``csv`` module's ``DictWriter`` class is initialized with the field names from the ``Manager`` class.
This uses a streamlined approach to applying the ``dict()`` method to each object and writing all of the resulting rows.

Since the schema specifies there are 100 employees and 10 managers, the average cardinality of the manager to employee relationship is going to be :math:`\tfrac{1}{10}`.
This distribtion tends to be relatively flat in the current implementation.
For some more nuanced database query design issues, a more complicated weighted pool is required to create the needed bias in relationships.
