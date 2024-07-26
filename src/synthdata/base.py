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

..  important:: This relies on Pydantic's rich set of type annotations.

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
    :special-members: __init__, __iter__, __next__

..  todo:: Reduce reliance on the Pydantic ``FieldInfo`` and annotation classes.

Model and Schema Synthesizers
==============================

The :py:class:`synthdata.base.BaseModelSynthesizer` supports the pydantic ``BaseModel``.
The :py:class:`synthdata.base.SchemaSynthesizer` permits references among Synthesizers.
This permits FK references to PK pools.

..  autofunction:: synth_name_map

..  autoclass:: DataIter
    :members:
    :special-members: __init__, __next__

..  autoclass:: ModelIter
    :members:
    :special-members: __init__, __next__

..  autoclass:: ModelSynthesizer
    :members:
    :special-members: __init__

..  autoclass:: BaseModelSynthesizer
    :members:
    :special-members: __init__

..  autoclass:: SchemaSynthesizer
    :members:
    :special-members: __init__
"""

import abc
from collections.abc import Iterator, Callable
from itertools import filterfalse
import random
from types import UnionType, NoneType
from typing import Any, cast, TypeVar, _UnionGenericAlias  # type: ignore [attr-defined]

from pydantic import BaseModel, Json
from pydantic.fields import FieldInfo


class Behavior(abc.ABC):
    """
    General features of the alternative **Strategty** plug-ins for a :py:class:`synthdata.base.Synthesizer`.
    """

    def __init__(self, synth: "Synthesizer") -> None:
        """Constructs a Behavior strategy bound to a specific :py:class:`synthdata.base.Synthesizer`."""
        self.synth = synth

    def prepare(self) -> None:
        pass

    def __repr__(self) -> str:
        return self.__class__.__name__

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

    def next(self) -> Any:
        """
        Returns a value from :py:meth:`synthdata.base.Synthesizer.value_gen()`.
        """
        v = self.synth.value_gen(self.count)
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
        self.pool_iter: Iterator[Any]

    def prepare(self):
        self.fill()

    def fill(self):
        """
        Populate the ``self.pool`` collection of unique values.
        This uses :py:meth:`synthdata.base.Synthesizer.value_gen` to build instances.
        This is used by the model's _prepare() method.
        """
        # Often, these are enough
        if self.synth.model.rows is None:
            raise ValueError("no rows provided for {self.synth.model} instance")  # pragma: no cover
        unique_pool = set(self.synth.value_gen(x) for x in range(self.synth.model.rows))
        self.count = self.synth.model.rows
        # May need a few more because of duplicates.
        while len(unique_pool) != self.synth.model.rows:
            unique_pool.add(self.synth.value_gen(self.count))
            self.count += 1
        self.pool = list(unique_pool)
        random.shuffle(self.pool)
        self.pool_iter = iter(self.pool)

    def next(self) -> Any:
        """
        In the event of using ``next(synth_instance)``,
        the :py:meth:`synthdata.base.Synthesizer.__next__` picks a value at random from the pool using this.
        """
        try:
            return next(self.pool_iter)
        except StopIteration:
            random.shuffle(self.pool)
            self.pool_iter = iter(self.pool)
            return next(self.pool_iter)


type NoiseGen = Callable[[int | None], Any | None]


class Synthesizer(abc.ABC):
    """
    Abstract Base Class for all synthesisers.
    """

    # Fields only used by SynthesizeReference, named here to satisfy PyRight
    model_ref = ""
    field_ref = ""

    # Field only used by SynthesizeUnion.
    sources: dict[str, "Synthesizer"]

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
        self.behavior = behavior(self)
        self.json_schema_extra = cast(dict[str, Any], self.field.json_schema_extra or {})
        self.noise_synth: list[NoiseGen] = [lambda x: None]  # Noise values.
        self.initialize()
        # Subclasses use these values
        self.min_length: int
        self.max_length: int

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.model}, {self.field}, {self.behavior})"

    def next(self) -> Any:
        """Get the next value from the :py:class:`synthdata.base.Behavior` **Strategy**."""
        return self.behavior.next()

    def prepare(self) -> None:
        self.behavior.prepare()

    @abc.abstractmethod
    def initialize(self) -> None:  # pragma: no cover
        """
        Parse the field information and prepare the synthesizer.
        This is the last step of ``__init__()``.

        This also prepares the noise generator.
        If bounds or patterns are provided, and out-of-bounds value or anti-pattern value of the right type.
        Otherwise, the data is a short, random string of punctuation characters, unlikely to be valid.
        """
        ...

    @abc.abstractmethod
    def value_gen(self, sequence: int | None = None) -> Any:  # pragma: no cover
        """
        Low-level value synthesis.
        """
        ...

    def noise_gen(self, sequence: int | None = None) -> Any:  # pragma: no cover
        """
        Low-level noise synthesis. Pick one of the ``noise_synth`` functions.
        """
        noise_synth = random.choice(self.noise_synth)
        return noise_synth(sequence)

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
    def match(cls, field_type: type, json_schema_extra: dict[str, Any]) -> bool:
        return False


class SynthesizeUnion(Synthesizer):
    """
    Synthesize a value selected from a union of values.

    For ``type | None``, or ``Optional[type]``, the None values have a default probability of 0.05.
    For all other cases, the distribution is uniform by default.

    The json_schema_extra can provide subdomain distribution details.

    -   ``{"subDomain": {"None": 1, "int": 99}}`` for simple optional.

    -   ``{"subDomain": {"int": 3, "float": 1}}`` for multiple values.

    Gets values from another :py:class:`synthdata.base.Synthesizer`.
    """

    def __init__(
        self,
        model: "ModelSynthesizer",
        field: FieldInfo,
        behavior: type[Behavior] = Independent,
        sources: dict[str, type[Synthesizer]] | None = None,
    ) -> None:
        if sources is None:
            raise TypeError(f"sources is required.")  # pragma: no cover
        self.sources: dict[str, Synthesizer] = {
            name: synth_class(model, field, behavior) for name, synth_class in sources.items()
        }
        super().__init__(model, field, behavior)

    def initialize(self):
        """
        Use jsonschema "subdomain"  to determine distribution.
        If two sources, one of which is SynthesizeNone and no subdomain in jsonschema, then 95% data, 5% None.
        """

        if "subdomain" in self.json_schema_extra:
            subdomain_spec: dict[str, int]
            subdomain_spec = self.json_schema_extra["subdomain"]
            # TODO: Assert it's a {string: number, ...} dictionary and the strings are in the sources map.
            # Map string names of types to the synthesizer instances in self.sources.
            self.subdomain = {self.sources[name]: fq for name, fq in subdomain_spec.items()}

        else:
            synth_none = lambda synth: synth.__class__.__name__ == "SynthesizeNone"
            none_source: list[Synthesizer] = list(filter(synth_none, self.sources.values()))
            other_source: list[Synthesizer] = list(filterfalse(synth_none, self.sources.values()))
            if len(other_source) == 1 and len(none_source) == 1:
                # One and None? and no subdomain with details.
                self.subdomain = {none_source[0]: 1, other_source[0]: 19}
            else:
                # Default distribution is uniform.
                self.subdomain = {s: 1 for s in self.sources}

        self.domain_synth: list[Synthesizer] = [
            cast(Synthesizer, synth)
            for synth, number in self.subdomain.items()
            for _ in range(number)
        ]

    def value_gen(self, sequence: int | None = None) -> Any:
        """
        Pick a domain. Then pick a value from the domain.
        """
        synth = random.choice(self.domain_synth)
        return synth.value_gen(sequence)

    def noise_gen(self, sequence: int | None = None) -> Any:
        """
        Pick a value not in any domain.

        Ideally, pick a domain and pick a value not in the domain.
        If the domains are reasonably disjoint, this **could** work.
        """
        synth = random.choice(self.domain_synth)
        return synth.noise_gen(sequence)


class SynthesizeReference(Synthesizer):
    """
    Synthesize a foreign key reference value.

    Gets values from another :py:class:`synthdata.base.Synthesizer`
    which must have :py:class:`synthdata.base.Pooled` behavior.

    This relies on Rule 0 of :py:class:`synthdata.base.SynthesizeModel`
    to locate the other synthesizer.
    This rule requires `json_schema_extra={"sql": {"key": "foreign", "reference": "model.field"}}`

    The ``source`` attribute is stateful.
    The :py:class:`synthdata.base.SynthesizeSchema` sets this to a specific :py:class:`synthdata.base.Synthesizer`  instance.
    The update is done as part of preparation to emit rows of data.

    ..  note::

        The pool of values are generated when
        a  :py:class:`synthdata.base.Synthesizer`
        with :py:class:`synthdata.base.Pooled` behavior is prepared.

        This makes it possible to emit rows for all models in a schema in any
        convenient order.
    """

    def initialize(self):
        try:
            self.model_ref, self.field_ref = self.json_schema_extra["sql"]["reference"].split(".")
        except KeyError:  # pragma: no cover
            raise ValueError(f"improper value for {self.json_schema_extra}")
        # Will be updated by a SynthesizerSchema when the reference is resolved.
        self.source: Synthesizer | None = None

    def value_gen(self, sequence: int | None = None) -> Any:
        """Generates a value by extracting it from a source synthensizer."""
        if self.source is None:
            raise ValueError(
                f"source {self.model_ref}.{self.field_ref} not resolved"
            )  # pragma: no cover
        return self.source.next()

    def noise_gen(self, sequence: int | None = None) -> Any:
        """Pick a value NOT in the key pool."""
        if self.source is None:
            raise ValueError(
                f"source {self.model_ref}.{self.field_ref} not resolved"
            )  # pragma: no cover
        return self.source.noise_gen()


def synth_name_map() -> dict[str, type[Synthesizer]]:
    """
    Finds all subclasses of :py:class:`synthdata.base.Synthesizer`.

    This is used once during model and schema creation to create a mapping from a name to a class.

    Yields name and class from most specific to most general.
    """

    def synth_class_iter(
        base: type[Synthesizer] = Synthesizer,
    ) -> Iterator[tuple[str, type]]:
        yield base.__name__, base
        for c in base.__subclasses__():
            yield from synth_class_iter(c)

    return dict(reversed(list(synth_class_iter())))


class DataIter:
    """
    Iterate through values of a :py:class:`synthdata.base.ModelSynthesizer` instance.
    This will create dictionaries suitable for creating Pydantic ``BaseModel`` instances.

    A trash injector can replace good data with invalid values -- bad numbers, bad strings, None, etc.
    The resulting object will **not** be a valid Pydantic ``BaseModel`` instance.

    ..  todo:: Handle recursive structures here.
    """

    def __init__(self, model: "ModelSynthesizer", noise: float = 0.0) -> None:
        """Creates an iterator, bound to a :py:class:`synthdata.base.ModelSynthesizer` instance."""
        self.model = model
        self.noise = noise

    def __repr__(self) -> str:
        return f"DataIter({self.model}, noise={self.noise})"

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return self

    def __next__(self) -> dict[str, Any]:  # BaseModel:
        """
        Creates the next ``dict[str, Any]`` object.
        Each field is created by the Sythesizer's attached Behavior.
        """
        data: dict[str, Any] = {}
        for name, synth in self.model.fields.items():
            if self.noise and random.random() < self.noise:
                data[name] = synth.noise_gen()
            else:
                data[name] = synth.next()
        return data


class ModelIter:
    """
    Iterate through values of a :py:class:`synthdata.base.ModelSynthesizer` instance.
    This can only create the Pydantic ``BaseModel`` instances with valid data.
    """

    def __init__(self, model: "ModelSynthesizer", noise: float = 0.0) -> None:
        """Creates an iterator, bound to a :py:class:`synthdata.base.ModelSynthesizer` instance."""
        self.model = model
        if noise:  # pragma: no cover
            raise TypeError("must use noise=0.0 for ModelIter instances")
        self.data_iter = DataIter(model)

    def __repr__(self) -> str:
        return f"ModelIter({self.model})"

    def __iter__(self) -> Iterator[BaseModel]:
        return self

    def __next__(self) -> BaseModel:
        data = next(self.data_iter)
        try:
            return self.model.model_class(**data)
        except Exception:  # pragma: no cover
            print(f"VALIDATION ERROR in {self.model}")
            print(data)
            raise


class ModelSynthesizer(abc.ABC):
    """Abstract Base Class for various model synthesizers."""

    @abc.abstractmethod
    def __init__(self, cls_: type, rows: int | None = None) -> None:
        """
        Initialize a model synthesizer.

        :param cls_: a class definition with fields of some kind.
        :param rows: the number of rows to generate when creating key pools.
        :param noise: the probability of invalid data in the resulting object.
            Note that non-zero noise values may lead to Pydantic validation errors.
        """
        self.model_class = cls_
        self.rows = rows
        # Reversed to put subclasses first in the dictionary keys.
        self._synth_name_map = synth_name_map()

        # Subclasses will popluate the field - synthesizer mapping.
        self.fields: dict[str, Synthesizer]


class BaseModelSynthesizer(ModelSynthesizer):
    """
    Synthesizes instances of Pydantic ``BaseModel``.

    This expects a flat collection of atomic fields.
    In that way, it's biased to work with SQL-oriented schema, which tend to be flat.

    ..  todo:: Handle recursive structures here.
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

        ..  todo:: Handle nested models.
        """
        super().__init__(cls_, rows)
        # Special case for FK references
        self.synthesize_reference = self._synth_name_map["SynthesizeReference"]

        self.fields = {
            name: self.make_field_synth(field)
            for name, field in self.model_class.model_fields.items()
        }

    def _prepare(self):
        """Initialize pools, and handle any other required preparation."""
        for name, field_synth in self.fields.items():
            field_synth.prepare()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.model_class}, rows={self.rows})"

    def sql_rule(
        self, field: FieldInfo
    ) -> tuple[type[Behavior] | None, dict[str, type[Synthesizer]] | None]:
        """
        Rule 0 -- PK's are pooled, FK's are references to PK pools.
        This also means ``"sql": {'key': "foreign", ...`` will get a reference synthesizer.

        ..  todo:: FK's may have optionality rules.

            The ``SynthesizeReference`` instance may need a subdomain distribution.
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
                # Optionality, however, may be defined here if this is ``KeyType | None``.
                return Independent, {str(field.annotation): self.synthesize_reference}
            else:
                # TODO: Raise ValueError? Warning?
                return Independent, None
        else:
            # TODO: Unique values? -- use Pooled also.
            return Independent, None

    def explicit_rule(
        self, field: FieldInfo
    ) -> tuple[type[Behavior] | None, dict[str, type[Synthesizer]] | None]:
        """
        Rule 1 -- json_schema_extra names a synthesizer class to use.
        Generally {"synthesizer": "SomeSynth"}
        """
        json_schema_extra = cast(dict[str, Any], field.json_schema_extra or {})

        if "synthesizer" in json_schema_extra:
            # Map synthesizer name to implementation classes.
            synth_class = self._synth_name_map[json_schema_extra["synthesizer"]]
            return None, {str(field.annotation): synth_class}
        return None, None

    def match_rule(
        self, field: FieldInfo
    ) -> tuple[type[Behavior] | None, dict[str, type[Synthesizer] | None]]:
        """
        Rule 2 -- deduce synthesizer from annotation class and json_schema_extra.
        requires map keys names all subclasses first, and names all superclasses last.

        Most cases there's a single ``{"type": type[Synthesizer]}``.

        Optionality returns ``{"type": type[Synthesizer], "NoneType": type[Synthesizer]}``.
        Further details may be required to get the frequency of null values correct.

            match field.annotation:
                case _UnionGenericAlias() | UnionType():
                    # If the union has two parts, one of which is None, then it's simply optional.
                    # Without further details, it's not clear what fraction should be None. Assume 5%.
                    # In general, a distribution table is required in json_schema_extra.
                    # ``{"subDomain": {"None": 1, "int": 99}}`` for simple optional.
                    # ``{"subDomain": {"int": 3, "float": 1}}`` for multiple values.
        """

        def simple_match(annotation: type, json_schema_extra: Json) -> type[Synthesizer] | None:
            for name in self._synth_name_map.keys():
                cls_ = self._synth_name_map[name]
                if cls_.match(annotation, json_schema_extra):
                    return cls_
            return None

        sources: dict[str, type[Synthesizer] | None]
        match field.annotation:
            case _UnionGenericAlias() | UnionType() as union:
                # Multiple Matches. No Behavior.
                sources = {
                    str(alt): simple_match(alt, field.json_schema_extra) for alt in union.__args__
                }
            case type() as simple_type:
                # Single Match, also no Behavior.
                sources = {str(simple_type): simple_match(simple_type, field.json_schema_extra)}
            case _:  # pragma: no cover
                raise TypeError(f"unexpected {field.annotation!r}")
        return None, sources

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
        behavior, synth_class_map = self.sql_rule(field)

        # Explicit json_schema_extra can name a class.
        if not synth_class_map:
            _, synth_class_map = self.explicit_rule(field)

        # Search all Synthesizer subclasses for match(es).
        # For non-Union, sources is an empty list.
        # For Union, the synth_class will be
        if not synth_class_map:
            _, synth_class_map = self.match_rule(field)

        # TODO: Confirm all alternatives defined in synth_class_map? No None values?
        if not synth_class_map or behavior is None:
            raise TypeError(f"no synth class matches {field=}")  # pragma: no cover
        elif len(synth_class_map) > 1:
            return SynthesizeUnion(
                self,
                field,
                behavior,
                cast(dict[str, type[Synthesizer]], synth_class_map),
            )
        else:
            synth_class = list(cast(dict[str, type[Synthesizer]], synth_class_map).values())[0]
            return synth_class(self, field, behavior)

    def __iter__(self) -> Iterator[BaseModel]:
        return self.model_iter()

    def model_iter(self, noise: float = 0.0) -> Iterator[BaseModel]:
        self._prepare()
        return ModelIter(self, noise=0.0)

    def data_iter(self, noise: float = 0.0) -> Iterator[dict[str, Any]]:
        self._prepare()
        return DataIter(self, noise)


class SchemaSynthesizer:
    """
    Synthesizes collections of Models.

    A Schema has multiple models to handle SQL Foreign Key references to another model's Primary Key.

    -   The PK is a :py:class:`synthdata.base.Synthesizer` with :py:class:`synthdata.base.Pooled` behavior.

    -   The FK is a :py:class:`synthdata.base.SynthesizeReference` that extracts values from the PK's pool.

    First, use :py:meth:`add` to add a ``BaseModel`` to the schema.

    Then -- after all models have been added -- use :py:meth:`rows` to get rows for a ``BaseModel``.

    The ``noise`` value is the probability of noise -- invalid values or None values if None is not permitted.

    ..  important::

        All models with PK's must be defined before creating rows for any model with FK's.

        It's best to define all model classes before trying to emit any data.
    """

    def __init__(self) -> None:
        self.schema = {}
        self.references = []
        self.prepared = False

    def add(self, model_class: type[BaseModel], rows: int | None = None) -> None:
        """
        Adds a ``BaseModel`` to the working schema.

        :raises KeyError: if the FK reference (``"Model.field"``) cannot be parsed.
        """
        match model_class:
            case BaseModel.__class__():
                model = BaseModelSynthesizer(model_class, rows)
            case _:  # pragma: no cover
                raise ValueError(f"unsupported {type(model_class)} model")
        self.schema[model_class.__name__] = model
        references = [
            (model, field, field.model_ref, field.field_ref)
            for field in model.fields.values()
            if field.model_ref and field.field_ref
        ]
        self.references.extend(references)

    def _resolve(self) -> None:
        """
        Resolve references among classes in the schema.
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
            self.prepare()

    def prepare(self) -> None:
        """
        For Pooled synthesizers, this will populate the pools.
        Once.
        After that, it does nothing.
        """
        if self.prepared:
            return
        self.prepared = True
        for model, model_synth in self.schema.items():
            model_synth._prepare()

    def reset(self) -> None:
        """Reset the synthesizers to repopulate pools."""
        self.prepared = False
        self.prepare()

    def rows(self, model_class: type[BaseModel]) -> Iterator[BaseModel]:
        """
        Returns the iterator for the :py:class:`synthdata.synth.SynthesizeModel`.
        If all FK references are not resolved, will raise an exception.

        :raises KeyError: if the FK reference (``"Model.field"``) cannot be found.
        :raises ValueError: if the FK reference is not a Pooled synthesizer.
        """
        self._resolve()
        self.prepare()
        model = self.schema[model_class.__name__]
        return model.model_iter(noise=0.0)

    def data(self, model_class: type[BaseModel], noise: float = 0.0) -> Iterator[dict[str, Any]]:
        """
        Returns an iterator for potential :py:class:`synthdata.synth.SynthesizeModel` instances.
        Noise is injected and the values may not be valid.
        """
        self._resolve()
        self.prepare()
        model = self.schema[model_class.__name__]
        return model.data_iter(noise=noise)
