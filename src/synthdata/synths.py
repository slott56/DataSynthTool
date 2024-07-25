"""
Synthesizer Definitions.
"""

import datetime
from datetime import timezone
from functools import partial
from operator import attrgetter
import random
import string
from types import UnionType, NoneType
from typing import Any, cast, _UnionGenericAlias  # type: ignore [attr-defined]

from pydantic.fields import FieldInfo
from annotated_types import MaxLen, MinLen, Ge, Le

from .base import Synthesizer, NoiseGen


class SynthesizeNone(Synthesizer):
    """
    Returns None. Handles ``Optional[type]`` and ``type | None`` annotated types.
    """

    @classmethod
    def match(cls, field_type: type | None, json_schema_extra: dict[str, Any]) -> bool:
        return field_type is None or issubclass(field_type, NoneType)

    def initialize(self):
        self.noise_synth = [lambda x: f"Noise-{x}"]

    def value_gen(self, sequence: int | None = None) -> Any:
        return None


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

    def initialize(self) -> None:
        self.min_length = cast(int, self.get_meta(MinLen, attrgetter("min_length")))
        self.max_length = cast(int, self.get_meta(MaxLen, attrgetter("max_length")))
        if self.min_length is None:
            self.min_length = self.min_default
        if self.min_length > 0:
            self.noise_synth.append(lambda x: "")
        if self.max_length is None:
            self.max_length = self.max_default
            # No point in trying to create a string too long... no max length provided.
        else:
            too_long = lambda x: self._value(self.max_length + random.randint(4, 12), x)
            self.noise_synth.append(too_long)

    def _value(self, size: int, sequence: int | None = None) -> str:
        return "".join([random.choice(self.domain) for _ in range(size)])

    def value_gen(self, sequence: int | None = None) -> Any:
        """
        Low-level value synthesis.
        """
        size = random.randint(self.min_length, self.max_length)
        return self._value(size, sequence)

    @classmethod
    def match(cls, field_type: type, json_schema_extra: dict[str, Any]) -> bool:
        """Generic ``Annotated[str, ...]``."""
        return issubclass(field_type, str)


class SynthesizeName(SynthesizeString):
    """
    Synthesizer Name-like strings. This title-cases a random string.

    ..  todo:: Improve the name generator with better pattern (and anti-pattern).

        Options

        1. get first names from census data; get digraph frequency from last names.

        2. Use NLTK digraph frequencies to generate plausible English-like works.

    Default min_length is 3 to avoid 1-char names.
    """

    domain = string.ascii_letters
    min_default = 3
    max_default = 12

    def value_gen(self, sequence: int | None = None) -> Any:
        """
        Low-level value synthesis.
        Creates length and a string of the desired length in Title Case.
        """
        return super().value_gen(sequence).title()

    @classmethod
    def match(cls, field_type: type, json_schema_extra: dict[str, Any]) -> bool:
        """Requires ``Annotated[str, ...]`` and ``json_schema_extra`` with ``{"domain": "name"}``"""
        if issubclass(field_type, str):
            return (
                json_schema_extra is not None
                and cast(dict[str, str], json_schema_extra).get("domain") == "name"
            )
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

    def initialize(self) -> None:
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

    def initialize(self) -> None:
        super().initialize()
        self.gen = {
            "uniform": partial(random.randint, self.min_value, self.max_value),
            "normal": partial(
                random.normalvariate,
                mu=(self.max_value + self.min_value) / 2,
                sigma=(self.max_value - self.min_value) / 6,
            ),
        }[self.dist_name]
        self.noise_synth.extend(
            [
                lambda x: self.min_value - random.randint(4, 12),
                lambda x: self.max_value + random.randint(4, 12),
                lambda x: f"XXX{x}XXX",
            ]
        )

    def value_gen(self, sequence: int | None = None) -> Any:
        """Creates integer in range with given distribution."""
        v = int(self.gen())
        while v < self.min_value or v > self.max_value:
            v = int(self.gen())
        return v

    @classmethod
    def match(cls, field_type: type, json_schema_extra: dict[str, Any]) -> bool:
        """Requires ``Annotated[int, ...]``."""
        return issubclass(field_type, int)


class SynthesizeFloat(SynthesizeNumber):
    """Extends :py:class:`synthdata.synths.SynthesizeNumber` to offer only float values."""

    min_value: float
    max_value: float

    def initialize(self) -> None:
        super().initialize()
        self.gen = {
            "uniform": lambda: random.random() * (self.max_value - self.min_value) + self.min_value,
            "normal": partial(
                random.normalvariate,
                mu=(self.max_value + self.min_value) / 2,
                sigma=(self.max_value - self.min_value) / 6,
            ),
        }[self.dist_name]
        self.noise_synth.extend(
            [
                lambda x: self.min_value - random.random() * 8,
                lambda x: self.max_value + random.random() * 8,
            ]
        )

    def value_gen(self, sequence: int | None = None) -> Any:
        """Creates float in range with given distribution."""
        v = float(self.gen())
        while v < self.min_value or v > self.max_value:
            v = float(self.gen())
        return v

    @classmethod
    def match(cls, field_type: type, json_schema_extra: dict[str, Any]) -> bool:
        """Requires ``Annotated[float, ...]``."""
        return issubclass(field_type, float)


class SynthesizeDate(SynthesizeNumber):
    """
    Extends :py:class:`synthdata.synths.SynthesizeNumber` to offer only datetime.datetime values.

    Default range is 1970-Jan-1 to 2099-Dec-31.
    """

    def initialize(self) -> None:
        super().initialize()
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
        self.noise_synth.extend(
            [
                lambda x: datetime.datetime.fromtimestamp(
                    self.min_date - random.random() * 90, tz=timezone.utc
                ),
                lambda x: datetime.datetime.fromtimestamp(
                    self.max_date + random.random() * 90, tz=timezone.utc
                ),
            ]
        )

    def value_gen(self, sequence: int | None = None) -> Any:
        """Creates date in range with given distribution."""
        dt = self.gen()
        return datetime.datetime.fromtimestamp(dt, tz=timezone.utc)

    @classmethod
    def match(cls, field_type: type, json_schema_extra: dict[str, Any]) -> bool:
        """Requires ``Annotated[datetime.datetime, ...]``"""
        return issubclass(field_type, datetime.datetime)
