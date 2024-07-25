#####
Usage
#####

See :ref:`code` for an example application to generate valid data.

The essence is this:

1.  Define the applciation model using Pydantic.

2.  Add details beyond the typical validation cases.
    This often means adding a distribution information in addition to valid choices or numeric ranges.

3.  Use the :py:class:`syntdata.base.SynthesizeModel` for a single ``BaseModel``.
    Use :py:class:`syntdata.base.SynthesizeSchema` for a schema with multiple, related ``BaseModel``.

4.  The :py:class:`syntdata.base.SynthesizeModel` is an Iterator over ``BaseModel`` objects.
    The :py:class:`syntdata.base.SynthesizeSchema` can emit Iterators over ``BaseModel`` objects for each model in the schema.

5.  Serialize the objects.
    For noise-free, clean data, a model iterator produces Pydantic :py:class:`pydantic.BaseModel` instances.
    For noisy data, a data iterator produces dictionaries that may raise an exception when used to created a py:class:`pydantic.BaseModel` instance.

