"""
Contains base class definitions for all synthesizers.
This includes the field-level synthesizers,
plus model-level and schema-level synthesizers.

A field-level synthesizer has two aspects.

-   An essential synth algorithms for various data types.
    These are generally randomly-generated sequences of values.

-   The behavior of the overall synth process.
    This falls into two variant strategies:

    - **Independent**. This means duplicates are possible, and the values are not referenced by other synthesizers.

    - **Dependent**. ("Pooled") Duplicates will be prevented, and the pool of values can be referenced by a :py:class:`synthdata.synths.SythesizerReference` instance.

In order to handle foreign key references, a :py:class:`synthdata.synths.SynthesizeReference`
extracts values from a pooled synthesizer.

Behavior Strategy
=================

The :py:class:`synthdata.base.Behavior` class hierarchy defines a **Strategy** that
tailors the behavior of a :py:class:`synthdata.base.Synthesizer`.

..  autoclass:: Behavior
    :members:

..  autoclass:: Independent
    :members:
    :special-members: __init__

..  autoclass:: Pooled
    :members:
    :special-members: __init__

Synthesizer Class
===============================

This is the superclass for the various definitions in the :py:mod:`synthdata.synths` module.

..  autoclass:: Synthesizer
    :members:
    :special-members: __init__, __iter__, __next__, __call__

Model and Schema Synthesizers
==============================

The :py:class:`synthdata.base.ModelSynthesizer` parallels the pydantic ``BaseModel``.
The :py:class:`synthdata.base.SchemaSynthesizer` permits references among Synthesizers.
This permits FK references to PK pools.

..  autofunction:: synth_class_iter

..  autoclass:: ModelIter
    :members:
    :special-members: __init__, __next__

..  autoclass:: ModelSynthesizer
    :members:
    :special-members: __init__

..  autoclass:: SchemaSynthesizer
    :members:
    :special-members: __init__
"""

import abc
from collections.abc import Iterator, Callable
import random
from typing import Any, cast, TypeVar

from pydantic import BaseModel
from pydantic.fields import FieldInfo


class Behavior(abc.ABC):
    """
    General features of the alternative **Strategty** plug-ins for a :py:class:`synthdata.base.Synthesizer`.
    """

    def __init__(self, synth: "Synthesizer") -> None:
        """Constructs a Behavior strategy bound to a specific :py:class:`synthdata.base.Synthesizer`."""
        self.synth = synth

    def __repr__(self) -> str:
        return self.__class__.__name__

    @abc.abstractmethod
    def iterator(self) -> Iterator[Any]:  # pragma: no cover
        """
        Constructs an iterator for the Synthesizer.
        """
        ...

    @abc.abstractmethod
    def next(self) -> Any:  # pragma: no cover
        """
        Returns a next value for a Synthesizer.
        """
        ...


class Independent(Behavior):
    """
    Defines a :py:class:`synthdata.base.Synthesizer` that cannot be the target of a :py:class:`SynthesizerReference`.
    Each value is generated randomly, with no assurance of uniqueness.

    This is -- in effect -- the default behavior of a :py:class:`synthdata.base.Synthesizer`.
    The methods are delegated back to the :py:class:`synthdata.base.Synthesizer` instance.
    """

    def __init__(self, synth: "Synthesizer") -> None:
        super().__init__(synth)
        self.count = 0

    def iterator(self) -> Iterator[Any]:
        """
        Returns the :py:class:`synthdata.base.Synthesizer`.
        An independent synthesizer is an ``Iterator[Any]``.
        """
        return self.synth

    def next(self) -> Any:
        """
        Returns a value from :py:meth:`synthdata.base.Synthesizer.__call__`.
        """
        v = self.synth(self.count)
        self.count += 1
        return v


class Pooled(Behavior):
    """
    Defines a :py:class:`synthdata.base.Synthesizer` that created a pool of values.
    This can be the target of a :py:class:`synthdata.base.SynthesizerReference` isntance.
    This requires an associated :py:class:`synthdata.base.SynthesizerModel` to provide the target number of rows in the pool.

    Values in the pool will be unique.
    """

    def __init__(self, synth: "Synthesizer") -> None:
        super().__init__(synth)
        assert self.synth.model.rows is not None, f"no target rows for {self.synth.model}"
        self.pool = self.fill()
        random.shuffle(self.pool)

    def fill(self) -> list[Any]:
        """
        Populate the pool of unique values.
        This uses :py:meth:`synthdata.base.Synthesizer.__call__` to build instances.
        """
        # Often, these are enough
        if self.synth.model.rows is None:
            raise ValueError("no rows provided for {self.synth.model} instance")  # pragma: no cover
        unique_pool = set(self.synth(x) for x in range(self.synth.model.rows))
        self.count = self.synth.model.rows
        # May need a few more because of duplicates
        while len(unique_pool) != self.synth.model.rows:
            unique_pool.add(self.synth(self.count))
            self.count += 1
        ordered_pool = list(unique_pool)
        return ordered_pool

    def iterator(self) -> Iterator[Any]:
        """Returns an iterator over the pool."""
        return iter(self.pool)

    def next(self) -> Any:
        """
        In the event of using ``next(synth_instance)``, this picks a value at random from the pool.
        """
        return random.choice(self.pool)


class Synthesizer(abc.ABC):
    """
    Abstract Base Class for all synthesisers.
    """

    model_ref = ""
    field_ref = ""

    def __init__(
        self,
        model: "ModelSynthesizer",
        field: FieldInfo,
        behavior: type[Behavior] = Independent,
    ) -> None:
        """
        Builds a Synthesizer that's part of a :py:class:`synthdata.base.ModelSynthesizer`.
        This is associated with a specific field of the ``BaseModel``.

        The :py:class:`synthdata.base.Behavior` is provided as a class name.
        The instance is created here *after* the field information is parsed by the :py:meth:`prepare` method.
        This permits a :py:class:`synthdata.base.Pooled` synthesizer to immediately create the
        pool of unique values.
        """
        self.model = model
        self.field = field
        self.json_schema_extra = cast(dict[str, Any], self.field.json_schema_extra or {})
        self.prepare()
        self.behavior = behavior(self)
        # Subclasses use these values
        self.min_length: int
        self.max_length: int

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.model}, {self.field}, {self.behavior})"

    def __iter__(self) -> Iterator[Any]:
        """Get the iterator from the :py:class:`synthdata.base.Behavior` **Strategy**."""
        return self.behavior.iterator()

    def __next__(self) -> Any:
        """Get the next value from the :py:class:`synthdata.base.Behavior` **Strategy**."""
        return self.behavior.next()

    @abc.abstractmethod
    def prepare(self) -> None:  # pragma: no cover
        """
        Parse the field information and prepare the synthesizer.
        This is called *before* the :py:class:`synthdata.base.Behavior` is constructed.
        """
        ...

    @abc.abstractmethod
    def __call__(self, sequence: int | None = None) -> Any:  # pragma: no cover
        """Low-level value synthesis."""
        ...

    T = TypeVar("T")

    def get_meta(self, cls_: type[T], getter: Callable[[T], Any]) -> Any:
        """Extract metadata from the Pydantic ``FieldInfo`` instance."""
        matches = [m for m in self.field.metadata if isinstance(m, cls_)]
        if len(matches) == 0:
            return None
        elif len(matches) != 1:
            raise ValueError(f"{matches}")  # pragma: no cover
        else:
            return getter(matches[0])

    @classmethod
    def match(cls, field: FieldInfo) -> bool:
        return False


def synth_class_iter(
    base: type[Synthesizer] = Synthesizer,
) -> Iterator[tuple[str, type]]:
    """
    Finds all subclasses of :py:class:`synthdata.base.Synthesizer`.

    This is used to create a mapping from name to class.

    Yields name and class top-down from most general to most specific.
    It's more useful reversed, though, starting from most specific.
    Clients should do ``dict(reversed(list(synth_class_iter())))``
    """
    yield base.__name__, base
    for c in base.__subclasses__():
        yield from synth_class_iter(c)


class ModelIter:
    """
    Iterate through values of a :py:class:`synthdata.base.ModelSynthesizer` instance.
    This will create the Pydantic ``BaseModel`` instances.
    """

    def __init__(self, model: "ModelSynthesizer") -> None:
        """Creates an iterator, bound to a :py:class:`synthdata.base.ModelSynthesizer` instance."""
        self.model = model
        self.synth_iter = {name: iter(synth) for name, synth in self.model.fields.items()}

    def __repr__(self) -> str:
        return f"ModelIter({self.model})"

    def __iter__(self) -> Iterator[BaseModel]:
        return self

    def __next__(self) -> BaseModel:
        """Creates the next ``BaseModel`` object."""
        data = {name: next(g) for name, g in self.synth_iter.items()}
        try:
            return self.model.model_class(**data)
        except Exception:  # pragma: no cover
            print("VALIDATION ERROR")
            print(data)
            raise


class ModelSynthesizer:
    """
    Synthesizes instances of ``BaseModel``.

    This expects a flat collection of atomic fields.
    In that way, it's biased to work with SQL-oriented schema, which tend to be very flat.
    """

    def __init__(self, cls_: type[BaseModel], rows: int | None = None) -> None:
        """
        Initializes a synthesizer for all fields of a given ``BaseModel``.
        The number of rows is only needed if there are any :py:class:`synthdata.base.Pooled` synthesizers,
        generally because of SQL primary keys.

        Construction of the synthesizers is part of initialization.
        The :py:meth:`make_field_synth` method is exposed so subclasses can extend the processing.

        The general use case is the use the ``fields`` attribute, which is a mapping
        of field names to :py:class:`synthdata.base.Synthesizer` instances.
        """
        self.model_class = cls_
        self.rows = rows
        # Reversed to put subclasses first in the dictionary keys.
        self._synth_name_map = dict(reversed(list(synth_class_iter())))
        # Special case for FK references
        self.synthesize_reference = self._synth_name_map["SynthesizeReference"]

        self.fields = {
            name: self.make_field_synth(field)
            for name, field in self.model_class.model_fields.items()
        }

    def __repr__(self) -> str:
        return f"ModelSynthesizer({self.model_class}, rows={self.rows})"

    def sql_rule(self, field: FieldInfo) -> tuple[type[Behavior] | None, type[Synthesizer] | None]:
        """
        Rule 0 -- PK's are pooled, FK's are references to PK pools.
        This also means ``"sql": {'key': "foreign", ...`` will get a reference synthesizer.
        """
        json_schema_extra = cast(dict[str, Any], field.json_schema_extra or {})

        if "sql" in json_schema_extra:
            key = cast(dict[str, Any], json_schema_extra["sql"]).get("key", "primary")
            if key == "primary":
                # "sql": {"key": "primary"} -- Pooled -- based on type.
                return Pooled, None
            elif key == "foreign":
                # "sql": {'key': "foreign", "reference": "Manager.id"} -- Independent instance of ``SynthesizeReference``.
                # Type actually depends on the referenced source.
                return Independent, self.synthesize_reference
            else:
                # TODO: Raise ValueError? Warning?
                return Independent, None
        else:
            # TODO: Unique values? -- use Pooled also.
            return Independent, None

    def explicit_rule(
        self, field: FieldInfo
    ) -> tuple[type[Behavior] | None, type[Synthesizer] | None]:
        """
        Rule 1 -- json_schema_extra names a synthesizer class to use.
        Generally {"synthesizer": "SomeSynth"}
        """
        json_schema_extra = cast(dict[str, Any], field.json_schema_extra or {})

        if "synthesizer" in json_schema_extra:
            # Map synthesizer name to implementation classes.
            synth_class = self._synth_name_map[json_schema_extra["synthesizer"]]
            return None, synth_class
        return None, None

    def match_rule(
        self, field: FieldInfo
    ) -> tuple[type[Behavior] | None, type[Synthesizer] | None]:
        """
        Rule 2 -- deduce synthesizer from annotation class and json_schema_extra.
        requies map keys has subclasses first, superclasses last.
        """
        for name in self._synth_name_map.keys():
            cls_ = self._synth_name_map[name]
            if cls_.match(field):
                return None, cls_
        return None, None

    def make_field_synth(self, field: FieldInfo) -> Synthesizer:
        """
        Given a specific field, apply the matching rules to locate a synthesizer.

        -   **Rule 0**. PK's lead to a :py:class:`synthdata.base.Pooled` **Strategy**.
            FK's will be references to PK pools.
            Otherwise, synthesizers are :py:class:`synthdata.base.Independent`.

        -   **Rule 1**. ``json_schema_extra`` can name a synthesizer to use.
            The key is ``"synthesizer"``.
            Example: ``{"synthesizer": "SomeSynth"}``

        -   **Rule 2**. Deduce synthesizer from annotation class and ``json_schema_extra`` properties.
            This is done by evaluating :py:meth:`synthdata.base.Synthesizer.match` for all subclasses
            of :py:class:`synthdata.base.Synthesizer` from most specific subclass to most general superclass.
            First match is assigned.
        """
        # SQL PK defines behavior.
        # SQL FK defines behavior and class.
        behavior, synth_class = self.sql_rule(field)

        # Explicit json_schema_extra can name class
        if synth_class is None:
            _, synth_class = self.explicit_rule(field)

        # Search all Synthesizer subclasses.
        if synth_class is None:
            _, synth_class = self.match_rule(field)

        if synth_class is None or behavior is None:
            raise TypeError(f"no synth class matches {field=}")  # pragma: no cover
        return synth_class(self, field, behavior)

    def __iter__(self) -> Iterator[BaseModel]:
        return ModelIter(self)


class SchemaSynthesizer:
    """
    Synthesizes collections of Models.

    Handle SQL Foreign Key references to another model's Primary Key.

    -   The PK is a :py:class:`synthdata.base.Synthesizer` with :py:class:`synthdata.base.Pooled` behavior.

    -   The FK is a :py:class:`synthdata.base.SynthesizeReference` that extracts values from the PK's pool.

    First, use :py:meth:`add` to add a ``BaseModel`` to the schema.

    Then -- after all models have been added -- use :py:meth:`rows` to get rows for a ``BaseModel``.

    ..  important::

        All models with PK's must be defined before creating rows for any model with FK's.

        It's best to define all model classes before trying to emit any data.
    """

    def __init__(self) -> None:
        self.schema = {}
        self.references = []

    def add(self, model_class: type[BaseModel], rows: int | None = None) -> None:
        """
        Adds a ``BaseModel`` to the working schema.

        :raises KeyError: if the FK reference (``"Model.field"``) cannot be parsed.
        """
        model = ModelSynthesizer(model_class, rows)
        self.schema[model_class.__name__] = model
        references = [
            (model, field, field.model_ref, field.field_ref)
            for field in model.fields.values()
            if field.model_ref and field.field_ref
        ]
        self.references.extend(references)

    def _prepare(self) -> None:
        """
        Schema preparation prior to creating any rows.
        """
        while self.references:
            model, field, model_ref, field_ref = self.references.pop()
            # DEBUG: print(f"Resolving Reference: {model} {field} refers to {model_ref}.{field_ref}")
            try:
                target = self.schema[model_ref].fields[field_ref]
            except KeyError:  # pragma: no cover
                print(f"{model_ref} not in {self.schema.keys()}")
                raise KeyError(f"can't resolve {model} {field} ref to {model_ref}.{field_ref}")
            field.source = target
            # Not needed here because it's handled when the Pooled Synthesizer is created
            # Alternative is to defer to here:  target.behavior.fill()

    def rows(self, model_class: type[BaseModel]) -> Iterator[BaseModel]:
        """
        Makes sure all FK references are resolved.
        Returns the iterator for the :py:class:`synthdata.synth.SynthesizeModel` iterator for the given class.

        :raises KeyError: if the FK reference (``"Model.field"``) cannot be found.
        :raises ValueError: if the FK reference is not a Pooled synthesizer.
        """
        self._prepare()
        model = self.schema[model_class.__name__]
        return iter(model)
