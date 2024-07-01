"""
Test synthdata.base classes: SynthesizeModel and SynthesizeSchema
"""

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
    d = dict(reversed(list(synth_class_iter())))
    keys = list(d.keys())
    # LAST
    assert keys[-1] == "Synthesizer"
    # FIRST
    assert keys[0] == "SynthesizeReference"
    # Specializations before Generalization
    assert keys.index("SynthesizeInteger") < keys.index("SynthesizeNumber")
    assert keys.index("SynthesizeFloat") < keys.index("SynthesizeNumber")
    assert keys.index("SynthesizeDate") < keys.index("SynthesizeNumber")


def test_model_iter():
    mock_base_model = Mock(return_value=sentinel.OBJECT)
    mock_model_synth = MagicMock(
        fields={"name": [sentinel.VALUE]},
        model_class=mock_base_model,
    )
    m = ModelIter(mock_model_synth)

    assert iter(m) == m
    assert next(m) == sentinel.OBJECT
    assert mock_base_model.mock_calls == [call(name=sentinel.VALUE)]
    assert repr(m) == f"ModelIter({str(mock_model_synth)})"


def test_model_prep():
    m = ModelSynthesizer(Employee, 12)
    assert repr(m) == f"ModelSynthesizer({Employee}, rows=12)"
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

    m = ModelSynthesizer(WeirdKey, 12)

    assert isinstance(m.fields["weird"], SynthesizeInteger)
    assert m.fields["weird"].model == m
    assert m.fields["weird"].field == WeirdKey.model_fields["weird"]
    assert isinstance(m.fields["weird"].behavior, Independent)


def test_explicit_rule_good():
    class Fussy(BaseModel):
        must_use: Annotated[str, Field(json_schema_extra={"synthesizer": "SynthesizeInteger"})]

    m = ModelSynthesizer(Fussy)

    assert isinstance(m.fields["must_use"], SynthesizeInteger)
    assert m.fields["must_use"].model == m
    assert m.fields["must_use"].field == Fussy.model_fields["must_use"]
    assert isinstance(m.fields["must_use"].behavior, Independent)


def test_explicit_rule_unknown():
    class Fussy(BaseModel):
        must_use: Annotated[str, Field(json_schema_extra={"synthesizer": "Invalid"})]

    with pytest.raises(KeyError) as exc_info:
        m = ModelSynthesizer(Fussy)
        assert exc_info.value.args == ("Invalid",)


def test_match_rule_failure():
    class OverTheTop(BaseModel):
        unknown: Union[int, str]

    with pytest.raises(TypeError) as exc_info:
        m = ModelSynthesizer(OverTheTop)
        assert exc_info.value.args == ("Invalid",)


def test_model_data(seeded_random):
    mock_manager_id = MagicMock(__next__=Mock(side_effect=[42]))
    m = ModelSynthesizer(Employee, 12)
    m.fields["manager"].source = mock_manager_id

    row = next(iter(m))
    assert row == Employee(
        id=2746317213,
        name="Zcudihyfjsonxkmtecq",
        hire_date=datetime.datetime(2039, 1, 15, 16, 11, 32, 65844),
        velocity=10.256638902448898,
        manager=42,
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
        id=2340505846,
        name="Zcudihyfjsonxkmtecq",
        hire_date=datetime.datetime(2039, 1, 15, 16, 11, 32, 65844),
        velocity=10.256638902448898,
        manager=398340369,
    )

    manager_iter = s.rows(Manager)
    m_0 = next(manager_iter)
    print(m_0)
    assert m_0 == Manager(
        id=398340369,
        employee_id=958682846,
        department_id="D[rO5PN",
    )
