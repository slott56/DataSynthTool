..  _containers:

###########
Containers
###########

The goal is to build a Data Generator App for a specific problem domain.
This app can used based on the synth data tools.
The app's responsibilities are:

-   to configure the synth data tools,

-   and persist the synthesized data in some useful serialization format.

Let's pretend the problem domain is some HR-related database.
The overall work is all HR related.

The structure will look like this:

..  uml::

    [HR Data App]

    [HR Schema]

    [Serialization]

    package "Synthetic Data Tool" {
        [SynthesizeModel]
        package "synths" {
            [field synth]
        }
        [SynthesizeModel] *- [field synth]
    }

    package "Pydantic" {
        [BaseModel]
        [Field]
        [BaseModel] *- [Field]
    }

    [HR Data App] --> [HR Schema] : defines
    [HR Data App] --> [Serialization] : uses
    [HR Data App] --> [SynthesizeModel] : uses
    [HR Schema] *-- [BaseModel] : contains
    [BaseModel] -- [SynthesizeModel] :< "creates objects"

The ``HR Data App`` will produce synthetic data for the data model defined in the ``HR Schema``.
It can be helpful to define the ``HR Schema`` as a separate, reusable Python module.
The Pydantic ``BaseModel`` class definitions can be used by an application.
The additional details used by the Synthetic Data Tools have no impact on other **Pydantic** features.

The ``HR Schema`` conatins one or more **Pydantic** ``BaseModel`` definitions.

The ``HR Data App`` uses the Synthetic Data Tools to build objects for classes in the ``HR Schema``.
Each ``HR Schema`` class will have a parallel ``SynthesizeModel`` object that is an iterator over the desired objects.
These objects can then be serialized.

The ``Serialization`` component covers the endless variety of file formats:

-   CSV
-   ND JSON
-   YAML
-   Spark
-   Kafka
-   SQL
-   etc.

Because the generated objects are **Pydantic** ``BaseModel`` subclasses, all of the facilities of Pydantic are available for conversion and serialization.

The details of the Synthetic Data Tool are covered in the :ref:`components` section.
To provide context, we'll look at the Data Generator App first.

Data Generator App
==================

The Data Generator App will be a Python application (or script) that creates and persists synthetic data.

For isolated data sets (without a complex multi-collection schema) the processing looks like this:

..  uml::

    start
    :define model;
    :configure model synthesizer;
    :get object iterator;
    repeat
      :get next object;
      :serialize object;
    repeat while (more data?) is (yes)
    ->no;
    stop

For SQL data, there are often multiple tables that require foreign key copies of primary key values.
In these cases, the processing will be somewhat more complicated:

..  uml::

    start
    :define all models in the schema;
    :configure all model synthesizers;
    :configure schema synthesizer;
    repeat
        :get object iterator;
        repeat
          :get next object;
          :serialize object;
        repeat while (more data?) is (yes)
        ->no more objects;
    repeat while (more models?) is (yes)
    ->no more models
    stop

There is no requirement to process the tables in any particular order.
Once the schema synthesizer has been populated, the various model generators can all be run independently.

The data generation depends on a **Pydantic** ``BaseModel``.

..  _`containers.model`:

Model Definition
================

The ``BaseModel`` definition is based on **Pydantic**, with some very important extensions.

The model definitions are focused on JSON Schema definitions.
This means the Pydantic ``json_schema_extra`` attribute of
a ``Field`` definition are used heavily to provide needed details.

The baseline Pydantic annotations define data types and provide very broad domain definitions within those types.
A data domain has a number of aspects:

-   The data type is often chosen from a small set of base types, including integer, float, string, date-time, and boolean. More complicated types are often built from these.

-   The domain is often a subset of the available values:

    -   Numbers have an upper and lower boundary.

    -   Strings can have a pattern or a defined format.
        They can also have minimum and maximum lengths.

    -   Date-time values often have an upper and lower boundary.

These domain definitions need to be extended to cover a number of cases:

-   String sizes and patterns.
    **Pydantic** and JSON Schema provide for numerous defined formats.
    For cases that extend beyond these, regular expression patterns are also supported.
    The patterns don't provide any information on the distribution of sizes for strings, or the distribution of choices within a regular expression.

-   Numbers and their distributions.
    While a minimum and a maximum are essential for data validation, a distribution or histogram is required to produce realistic data.

-   Dates and DateTimes have the same problem numbers have: they require a more complete domain definition including a distribution or histogram.

-   Enumerated values are supported directly by JSON Schema.
    However, a distribution histogram is also required.

-   Benford's Law is an interesting facet of some measurements.
    See https://mathworld.wolfram.com/BenfordsLaw.html.
    This biases the distribution of leading digits.

-   Foreign keys in a relational data model must match primary keys defined elsewhere in the schema.
    This means the foreign key synthesizer is limited to values chosen from a pool of values defined by a different synthesizer in a different model of the schema.

-   Optional values are a more subtle aspect of a domain definition.
    Optionality takes two forms: domain-indepedent null values, and domain-specific null values.
    A domain-indepedent null is the SQL ``NULL`` or Python ``None`` value.
    A domain-specific null is a coded value, like social security number ``999-99-9999`` that indicates some sort of missing or not-applicable value.

All of these aspects require JSON Schema extensions.
Not all are currently implemented, but the architecture provides a useful framework for adding features.

Schema Definition
=================

A Schema is a collection of models.
For an application where there's only one model, or the models are independent of each other, the schema can be safely ignored.

For SQL database design, however, requires a schema.
Some tables have foreign keys that are primary keys on other tables.
The schema is a collection of model definitions, allowing the cross-references to work.

It looks like this:

..  uml::

    class SynthesizeSchema

    class SynthesizeModel

    class pydantic.BaseModel

    class pydantic.Field

    SynthesizeSchema o-- "{1, m}" SynthesizeModel : "Contains"

    SynthesizeModel -- pydantic.BaseModel : "Based on"

    pydantic.BaseModel *- pydantic.Field

What's essential is the way a ``SynthesizerModel`` depends on an underlying Pydantic ``BaseModel``.
The Synthetic Data Tools rely on the rich set of type annotations in Pydantic.
These are used to validate the output from Synthesizers, assuring the data is valid.
This also makes Pydantic's rich set of serialization options available, permitting easy creation of newline-delimited JSON and CSV.
Further -- with some care -- the Pydantic model can be mapped against a separate SQL-based model to permit direct interaction with SQL databases in the case that's helpful.

Here's an example data model.

..  uml::


    hide methods
    hide circle

    class Employee {
        id: int
        {field} name: string(40)
        hire_date: timestamp
        velocity: float
        manager_id: int
    }

    class Manager {
        manager_id: int
        employee_id: int
        {field} department_id: string(8)
    }

    Employee "{0,10}" --* Manager :< Manages

    Employee -- Manager : IsA

A Manager manages a number of Employees.
A Manager IS an Employee, also.
This leads to complex SQL requiring two separate joins between manager and employee to get direct reports.

Here's the definition in Python.

..  literalinclude::
    ../tests/sample_schema.py

Here are the annotations for each field in the ``Employee`` table:

-   **id**.
    The fundamental type is ``int``.
    The ``json_schema_extra`` settings provide additional SQL-focused features, specifically, it's role as a unique primary key.

-   **name**.
    The fundamental type is ``str`` with length limit of 40.
    The ``json_schema_extra`` settings define a narrow domain of "name".

-   **hire_date**.
    This is a ``datetime`` with a lower limit
    of 2021-Jan-18.

-   **velocity**.
    This is a ``float`` value with a range of 2 to 21.
    The ``json_schema_extra`` defines it to have
    a normal distribution.
    Without additional details, the mean will be the midpoint of the domain and the standard deviation will be :math:`\tfrac{1}{6}` of the range.
    The defined limit values are unlikely to appear.

-   **manager**.
    This is an ``int`` field.
    The ``json_schema_extra`` settings provide additional SQL-focused features, specifically, it's a foreign key to the ``id`` attribute of the ``Manager`` table.

The primary keys create pools of candidate values.
The foreign key references select values from the pools.
The SQL "cardinality" of the relationship is defined by the number of rows in each ``Model``.
If the median cardinality is 5 employees per manager, then, the employee table must have 5 times as many rows as the manager table.

The ``Manager`` table avoids introducing anything new.
