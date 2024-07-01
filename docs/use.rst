#####
Usage
#####

See :ref:`code` for an example application.

The essence is this:

1.  Define the applciation model using Pydantic.

2.  Use the :py:class:`syntdata.base.SynthesizeModel` for a single ``BaseModel``.
    Use :py:class:`syntdata.base.SynthesizeSchema` for a schema with multiple, related ``BaseModel``.

3.  The :py:class:`syntdata.base.SynthesizeModel` is an Iterator over ``BaseModel`` objects.
    The :py:class:`syntdata.base.SynthesizeSchema` can emit Iterators over ``BaseModel`` objects for each model in the schema.

4.  Serialize the objects.
