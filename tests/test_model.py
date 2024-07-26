"""
Test synthdata.base classes: SynthesizeModel and SynthesizeSchema
"""

import random
from typing import Union
from unittest.mock import Mock, MagicMock, sentinel, call

from sample_schema import *
from synthdata.synths import *
from synthdata.base import *

import pytest


@pytest.fixture()
def seeded_random():
    random.seed(42)


def test_synth_class_iter():
    d = synth_name_map()
    keys = list(d.keys())
    # LAST
    assert keys[-1] == "Synthesizer"
    # Specializations before Generalization
    assert keys.index("SynthesizeInteger") < keys.index("SynthesizeNumber")
    assert keys.index("SynthesizeFloat") < keys.index("SynthesizeNumber")
    assert keys.index("SynthesizeDate") < keys.index("SynthesizeNumber")
    # Unique items, rarely subclassed.
    assert keys[-2] == "SynthesizeUnion"
    assert keys[-3] == "SynthesizeReference"
    assert keys[-4] == "SynthesizeNone"


def test_data_iter():
    mock_base_model = Mock(return_value=sentinel.OBJECT)
    mock_model_synth = MagicMock(
        name="ModelSynthesizer",
        fields={"name": Mock(name="Synthesizer", next=Mock(return_value=sentinel.VALUE))},
        model_class=mock_base_model,
    )
    m = DataIter(mock_model_synth)

    assert iter(m) == m
    assert next(m) == {"name": sentinel.VALUE}
    assert mock_base_model.mock_calls == []
    assert repr(m) == f"DataIter({str(mock_model_synth)}, noise=0.0)"


def test_model_iter():
    mock_base_model = Mock(return_value=sentinel.OBJECT)
    mock_model_synth = MagicMock(
        name="ModelSynthesizer",
        fields={"name": Mock(name="Synthesizer", next=Mock(return_value=sentinel.VALUE))},
        model_class=mock_base_model,
    )
    m = ModelIter(mock_model_synth)

    assert iter(m) == m
    assert next(m) == sentinel.OBJECT
    assert mock_base_model.mock_calls == [call(name=sentinel.VALUE)]
    assert repr(m) == f"ModelIter({str(mock_model_synth)})"


def test_optional():
    class OptionalField(BaseModel):
        opt_int: int | None

    m = BaseModelSynthesizer(OptionalField, 12)

    assert isinstance(m.fields["opt_int"], SynthesizeUnion)
    assert m.fields["opt_int"].model == m
    assert m.fields["opt_int"].field == OptionalField.model_fields["opt_int"]
    assert isinstance(m.fields["opt_int"].behavior, Independent)


def test_model_prep():
    m = BaseModelSynthesizer(Employee, 12)
    m._prepare()

    assert repr(m) == f"BaseModelSynthesizer({Employee}, rows=12)"
    assert m.rows == 12
    assert len(m.fields) == len(Employee.model_fields)

    assert isinstance(m.fields["id"], SynthesizeInteger)
    assert m.fields["id"].model == m
    assert m.fields["id"].field == Employee.model_fields["id"]
    assert isinstance(m.fields["id"].behavior, Pooled)

    assert isinstance(m.fields["name"], SynthesizeName)
    assert m.fields["name"].model == m
    assert m.fields["name"].field == Employee.model_fields["name"]
    assert isinstance(m.fields["name"].behavior, Independent)

    assert isinstance(m.fields["hire_date"], SynthesizeDate)
    assert m.fields["hire_date"].model == m
    assert m.fields["hire_date"].field == Employee.model_fields["hire_date"]
    assert isinstance(m.fields["hire_date"].behavior, Independent)

    assert isinstance(m.fields["velocity"], SynthesizeFloat)
    assert m.fields["velocity"].model == m
    assert m.fields["velocity"].field == Employee.model_fields["velocity"]
    assert isinstance(m.fields["velocity"].behavior, Independent)

    assert isinstance(m.fields["manager"], SynthesizeReference)
    assert m.fields["manager"].model == m
    assert m.fields["manager"].field == Employee.model_fields["manager"]
    assert isinstance(m.fields["manager"].behavior, Independent)
    # Will be resolved by schema.
    assert m.fields["manager"].source is None


def test_sql_rule():
    class WeirdKey(BaseModel):
        weird: Annotated[int, Field(json_schema_extra={"sql": {"key": "notprimary-notforeign"}})]

    m = BaseModelSynthesizer(WeirdKey, 12)

    assert isinstance(m.fields["weird"], SynthesizeInteger)
    assert m.fields["weird"].model == m
    assert m.fields["weird"].field == WeirdKey.model_fields["weird"]
    assert isinstance(m.fields["weird"].behavior, Independent)


def test_explicit_rule_good():
    class Fussy(BaseModel):
        must_use: Annotated[str, Field(json_schema_extra={"synthesizer": "SynthesizeInteger"})]

    m = BaseModelSynthesizer(Fussy)

    assert isinstance(m.fields["must_use"], SynthesizeInteger)
    assert m.fields["must_use"].model == m
    assert m.fields["must_use"].field == Fussy.model_fields["must_use"]
    assert isinstance(m.fields["must_use"].behavior, Independent)


def test_explicit_rule_unknown():
    class Fussy(BaseModel):
        must_use: Annotated[str, Field(json_schema_extra={"synthesizer": "Invalid"})]

    with pytest.raises(KeyError) as exc_info:
        m = BaseModelSynthesizer(Fussy)
        assert exc_info.value.args == ("Invalid",)


def test_alternatives():
    class OverTheTop(BaseModel):
        alt: Union[int, str]

    m = BaseModelSynthesizer(OverTheTop, 12)

    assert isinstance(m.fields["alt"], SynthesizeUnion)
    assert m.fields["alt"].model == m
    assert m.fields["alt"].field == OverTheTop.model_fields["alt"]
    assert isinstance(m.fields["alt"].behavior, Independent)


def test_model_data(seeded_random):
    mock_manager_id = MagicMock(__next__=Mock(side_effect=[42]))
    m = BaseModelSynthesizer(Employee, 12)
    m._prepare()
    m.fields["manager"].source = mock_manager_id

    row = next(iter(m))
    assert row == Employee(
        id=2592983555,
        name="Rosjoruxxdoczuzrenktunpfzpd",
        hire_date=datetime.datetime(2032, 4, 30, 2, 17, 3, 359625, tzinfo=datetime.timezone.utc),
        velocity=12.336979706209183,
        manager=1,
    )


def test_schema(seeded_random):
    s = SchemaSynthesizer()
    s.add(Employee, 10)
    s.add(Manager, 2)

    assert s.schema["Employee"].model_class == Employee
    assert s.schema["Employee"].fields["manager"].source is None
    assert s.schema["Manager"].model_class == Manager

    employee_iter = s.rows(Employee)
    assert s.schema["Employee"].fields["manager"].source is not None
    assert s.schema["Employee"].fields["manager"].source is s.schema["Manager"].fields["id"]

    e_0 = next(employee_iter)
    assert e_0 == Employee(
        id=3701002945,
        name="Mokiupk",
        hire_date=datetime.datetime(2057, 7, 17, 21, 24, 55, 558971, tzinfo=datetime.timezone.utc),
        velocity=12.809854665970944,
        manager=398340369,
    )

    manager_iter = s.rows(Manager)
    m_0 = next(manager_iter)
    print(m_0)
    assert m_0 == Manager(id=3529615275, employee_id=2479708607, department_id="C)<i|I<")


def test_noisy_dataiter(seeded_random):
    mock_model = Mock(
        fields={
            "f1": Mock(
                noise_gen=Mock(return_value=sentinel.NOISE1),
                next=Mock(return_value=sentinel.VALUE1),
            ),
            "f2": Mock(
                noise_gen=Mock(return_value=sentinel.NOISE2),
                next=Mock(return_value=sentinel.VALUE2),
            ),
        },
        rows=2,
    )
    di = DataIter(mock_model, noise=0.5)
    rows = list(next(di) for _ in range(10))
    assert rows == [
        {"f1": sentinel.VALUE1, "f2": sentinel.NOISE2},
        {"f1": sentinel.NOISE1, "f2": sentinel.NOISE2},
        {"f1": sentinel.VALUE1, "f2": sentinel.VALUE2},
        {"f1": sentinel.VALUE1, "f2": sentinel.NOISE2},
        {"f1": sentinel.NOISE1, "f2": sentinel.NOISE2},
        {"f1": sentinel.NOISE1, "f2": sentinel.VALUE2},
        {"f1": sentinel.NOISE1, "f2": sentinel.NOISE2},
        {"f1": sentinel.VALUE1, "f2": sentinel.VALUE2},
        {"f1": sentinel.NOISE1, "f2": sentinel.VALUE2},
        {"f1": sentinel.VALUE1, "f2": sentinel.NOISE2},
    ]
