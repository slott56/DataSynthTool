"""
Synthesizer Definitions.
"""

import datetime
from functools import partial
from operator import attrgetter
import random
import string
from types import UnionType, NoneType
from typing import Any, cast, _UnionGenericAlias  # type: ignore [attr-defined]

from pydantic.fields import FieldInfo
from annotated_types import MaxLen, MinLen, Ge, Le

from .base import Synthesizer


class SynthesizeString(Synthesizer):
    """
    Synthesizes printable strings with no whitespace or ``\\``.

    Uses ``Field`` attributes

    -   ``min_length`` (default 1)
    -   ``max_length`` (default 32)
    """

    domain = sorted(
        set(string.ascii_letters) | set(string.punctuation) | set(string.digits) - {"\\"}
    )
    min_default = 1
    max_default = 32

    def prepare(self) -> None:
        self.min_length = cast(int, self.get_meta(MinLen, attrgetter("min_length")))
        self.max_length = cast(int, self.get_meta(MaxLen, attrgetter("max_length")))
        if self.min_length is None:
            self.min_length = self.min_default
        if self.max_length is None:
            self.max_length = self.max_default

    def __call__(self, sequence: int | None = None) -> Any:
        """Creates length and a string of the desired length."""
        size = random.randint(self.min_length, self.max_length)
        return "".join([random.choice(self.domain) for _ in range(size)])

    @classmethod
    def match(cls, field: FieldInfo) -> bool:
        """Generic ``Annotated[str, ...]``."""
        match field.annotation:
            case _UnionGenericAlias() | UnionType():
                pass
            case type() as cls_ if issubclass(cls_, str):
                return True
            case type():
                return False
            case _:
                raise TypeError(f"unexpected {field.annotation!r}")
        return False


class SynthesizeName(SynthesizeString):
    """
    Synthesizer Name-like strings

    Not very good.

    Options

    1. get first names from census data; get digraph frequency from last names.

    2. Use NLTK digraph frequencies to generate plausible English-like works.

    Default min_length is 3 to avoid 1-char names.
    """

    domain = string.ascii_letters
    min_default = 3
    max_default = 12

    def __call__(self, sequence: int | None = None) -> Any:
        """Creates length and a string of the desired length in Title Case."""
        return super().__call__(sequence).title()

    @classmethod
    def match(cls, field: FieldInfo) -> bool:
        """Requires ``Annotated[str, ...]`` and ``json_schema_extra`` with ``{"domain": "name"}``"""
        match field.annotation:
            case _UnionGenericAlias() | UnionType():
                pass
            case type() as cls_ if issubclass(cls_, str):
                return (
                    field.json_schema_extra is not None
                    and cast(dict[str, str], field.json_schema_extra).get("domain") == "name"
                )
            case type():
                return False
            case _:
                raise TypeError(f"unexpected {field.annotation!r}")
        return False


class SynthesizeNumber(Synthesizer):
    """
    Abstract number synthesizer.

    Uses ``Field`` attributes

    -   ``ge`` (default 0)
    -   ``le`` (default 2**32 - 1, $2^{32} - 1$.

    Uses ``json_schema_extra`` values

    -    ``"distribution"`` -- can be ``"normal"`` or ``"uniform"``.
    """

    default_distribution = "uniform"

    def prepare(self) -> None:
        self.min_value = self.get_meta(Ge, attrgetter("ge"))
        self.max_value = self.get_meta(Le, attrgetter("le"))
        if self.min_value is None:
            self.min_value = 0
        if self.max_value is None:
            self.max_value = 2**32 - 1
        self.dist_name = self.json_schema_extra.get("distribution", self.default_distribution)


class SynthesizeInteger(SynthesizeNumber):
    """Extends :py:class:`synthdata.synths.SynthesizeNumber` to offer only integer values."""

    min_value: int
    max_value: int

    def prepare(self) -> None:
        super().prepare()
        self.gen = {
            "uniform": partial(random.randint, self.min_value, self.max_value),
            "normal": partial(
                random.normalvariate,
                mu=(self.max_value + self.min_value) / 2,
                sigma=(self.max_value - self.min_value) / 6,
            ),
        }[self.dist_name]

    def __call__(self, sequence: int | None = None) -> Any:
        """Creates integer in range with given distribution."""
        v = int(self.gen())
        while v < self.min_value or v > self.max_value:
            v = int(self.gen())
        return v

    @classmethod
    def match(cls, field: FieldInfo) -> bool:
        """Requires ``Annotated[int, ...]``."""
        match field.annotation:
            case _UnionGenericAlias() | UnionType():
                pass
            case type() as cls_ if issubclass(cls_, int):
                return True
            case type():
                return False
            case _:
                raise TypeError(f"unexpected {field.annotation!r}")
        return False


class SynthesizeFloat(SynthesizeNumber):
    """Extends :py:class:`synthdata.synths.SynthesizeNumber` to offer only float values."""

    min_value: float
    max_value: float

    def prepare(self) -> None:
        super().prepare()
        self.gen = {
            "uniform": lambda: random.random() * (self.max_value - self.min_value) + self.min_value,
            "normal": partial(
                random.normalvariate,
                mu=(self.max_value + self.min_value) / 2,
                sigma=(self.max_value - self.min_value) / 6,
            ),
        }[self.dist_name]

    def __call__(self, sequence: int | None = None) -> Any:
        """Creates float in range with given distribution."""
        v = float(self.gen())
        while v < self.min_value or v > self.max_value:
            v = float(self.gen())
        return v

    @classmethod
    def match(cls, field: FieldInfo) -> bool:
        """Requires ``Annotated[float, ...]``."""
        match field.annotation:
            case _UnionGenericAlias() | UnionType():
                pass
            case type() as cls_ if issubclass(cls_, float):
                return True
            case type():
                return False
            case _:
                raise TypeError(f"unexpected {field.annotation!r}")
        return False


class SynthesizeDate(SynthesizeNumber):
    """
    Extends :py:class:`synthdata.synths.SynthesizeNumber` to offer only datetime.datetime values.

    Default range is 1970-Jan-1 to 2099-Dec-31.
    """

    def prepare(self) -> None:
        super().prepare()
        self.min_value = self.get_meta(Ge, attrgetter("ge"))
        self.max_value = self.get_meta(Le, attrgetter("le"))
        if self.min_value is None:
            self.min_value = datetime.datetime(1970, 1, 1)
        if self.max_value is None:
            self.max_value = datetime.datetime(2099, 12, 31)
        self.dist_name = self.json_schema_extra.get("distribution", self.default_distribution)

        self.min_date = self.min_value.timestamp()
        self.max_date = self.max_value.timestamp()
        self.gen = {
            "uniform": lambda: random.random() * (self.max_date - self.min_date) + self.min_date,
            "normal": partial(
                random.normalvariate,
                mu=(self.max_date + self.min_date) / 2,
                sigma=(self.max_date - self.min_date) / 6,
            ),
        }[self.dist_name]

    def __call__(self, sequence: int | None = None) -> Any:
        """Creates date in range with given distribution."""
        dt = self.gen()
        return datetime.datetime.fromtimestamp(dt)

    @classmethod
    def match(cls, field: FieldInfo) -> bool:
        """Requires ``Annotated[datetime.datetime, ...]``"""
        match field.annotation:
            case _UnionGenericAlias() | UnionType():
                pass
            case type() as cls_ if issubclass(cls_, datetime.datetime):
                return True
            case type():
                return False
            case _:
                raise TypeError(f"unexpected {field.annotation!r}")
        return False


class SynthesizeReference(Synthesizer):
    """
    Synthesize a foreign key reference value.

    Gets values from another :py:class:`synthdata.base.Synthesizer` with :py:class:`synthdata.base.Pooled` behavior.

    This relies on Rule 0 of :py:class:`synthdata.base.SynthesizeModel` to locate
    this synthesizer.
    It requires `json_schema_extra={"sql": {"key": "foreign", "reference": "model.field"}}`

    The ``source`` attribute is stateful.
    The :py:class:`synthdata.base.SynthesizeSchema` sets this to a specific :py:class:`synthdata.base.Synthesizer`  instance.
    The update is done as part of preparation to emit rows of data.

    ..  note::

        The pool of values are generated when
        a  :py:class:`synthdata.base.Synthesizer`
        with :py:class:`synthdata.base.Pooled` behavior is built.

        This makes it possible to emit rows for all models in a schema in any
        convenient order.
    """

    def prepare(self):
        try:
            self.model_ref, self.field_ref = self.json_schema_extra["sql"]["reference"].split(".")
        except KeyError:
            raise ValueError(f"improper value for {self.json_schema_extra}")
        # Will be updated by a SynthesizerSchema when the reference is resolved.
        self.source: Synthesizer | None = None

    def __call__(self, sequence: int | None = None) -> Any:
        """Generates a value by extracting it from the source synthensizer."""
        if self.source is None:
            raise ValueError(
                f"source {self.model_ref}.{self.field_ref} not resolved"
            )  # pragma: no cover
        return next(self.source)
