"""
Test synthdata.synths classes.
"""

import random
from statistics import mean, stdev
from unittest.mock import Mock, MagicMock, sentinel

from sample_schema import *
from synthdata.synths import *
from synthdata.base import *

import pytest


@pytest.fixture()
def seeded_random():
    random.seed(42)


@pytest.fixture()
def mock_model():
    return Mock(rows=10)


def test_independent():
    synth = Mock(value_gen=Mock(return_value=sentinel.OBJECT))
    behavior = Independent(synth)
    behavior.prepare()
    assert repr(behavior) == "Independent"
    assert behavior.next() == sentinel.OBJECT


def test_pooled():
    objects = [
        sentinel.OB1,
        sentinel.OB2,
        sentinel.OB3,
        sentinel.OB3,
        sentinel.OB4,
        sentinel.OB5,
        sentinel.OB6,
    ]
    synth = Mock(
        model=Mock(rows=6),
        value_gen=Mock(side_effect=objects),
    )
    behavior = Pooled(synth)
    behavior.prepare()

    assert repr(behavior) == "Pooled"
    assert set(behavior.pool) == set(objects)
    assert behavior.next() in objects
    assert behavior.count == 7


def test_synth_none(seeded_random, mock_model):
    ig = SynthesizeNone(mock_model, Employee.model_fields["name"], behavior=Independent)
    assert ig.next() is None
    assert (
        repr(ig)
        == f"SynthesizeNone({repr(mock_model)}, {str(Employee.model_fields['name'])}, Independent)"
    )

    assert ig.noise_gen() is not None


def test_synth_string(seeded_random, mock_model):
    ig = SynthesizeString(mock_model, Employee.model_fields["name"], behavior=Independent)
    ig.prepare()
    assert ig.next() == "$D@=2.wf"
    assert (
        repr(ig)
        == f"SynthesizeString({repr(mock_model)}, {str(Employee.model_fields['name'])}, Independent)"
    )

    pg = SynthesizeString(mock_model, Employee.model_fields["name"], behavior=Pooled)
    pg.prepare()
    pool = {
        "5PN;vCzxs*nr6e~@5\\QCryh=",
        "/FX5[!}}Ba7a.qGran:4P5",
        "lW%$,<",
        "(>%ITC)<i|I<t`Ss[3B2@",
        "an$h:|tzfV=ZlD!",
        "MnB&~[e0Q+gFqpOj9{)&u>F",
        "d!mJ_#/OH?(?i++~_)e11u]g6BdnW<f~y:|",
        ">-QD[r",
        "eBkWkTO=2b`,'/4q5xWm)RQm\\dAg\"x}/xeCs",
        "zWLD4<L.,Q-",
    }
    assert set(pg.behavior.pool) == pool
    assert pg.next() in pool

    assert pg.noise_gen() not in pool


def test_synth_name(seeded_random, mock_model):
    g2 = SynthesizeName(mock_model, Employee.model_fields["name"])
    assert [g2.next() for _ in range(10)] == [
        "Bvrpoivgrv",
        "Flbcbfnogmbjmtpsiaoclrzawzksbvrjnwvgf",
        "Gwwmqzcudihyfjsonxkmtecqoxs",
        "Ogyrdoxk",
        "Wnqrsrpemokiupkdyrosjoruxx",
        "Oczuzr",
        "Nktunpf",
        "Pdjqipvjiqvlblzxoigffwdhjoky",
        "Meyymdhqjaruhriwrxpvhsbkdauuqg",
        "Ggotogmmjxwkix",
    ]
    assert g2.noise_gen() == "MuFbhxZtpdpKffUFeWIXiiQEJkqHMBnIWUSmTtzQPxCH"


def test_syth_int(seeded_random, mock_model):
    g3 = SynthesizeInteger(mock_model, Employee.model_fields["id"])
    print([g3.next() for _ in range(10)])
    assert g3.noise_gen() is None


def test_syth_float(seeded_random, mock_model):
    g4 = SynthesizeFloat(mock_model, Employee.model_fields["velocity"])

    # Expect min 2, max 21, mean $\tfrac{21 + 2}{2}$ = 11.5, stdev $\tfrac{21+2}{6}$ = 3.83
    s = [g4.next() for _ in range(1000)]
    assert min(s) == pytest.approx(2, rel=1)
    assert max(s) == pytest.approx(21, rel=1)
    assert mean(s) == pytest.approx(11.5, rel=0.1)
    assert stdev(s) == pytest.approx(3.83, rel=0.5)

    assert g4.noise_gen() < 2.0


def test_synth_date(seeded_random, mock_model):
    g5 = SynthesizeDate(mock_model, Employee.model_fields["hire_date"])
    assert g5.next() == datetime.datetime(
        2071, 7, 13, 20, 16, 4, 252645, tzinfo=datetime.timezone.utc
    )

    assert g5.noise_gen() is None


def test_synth_reference(seeded_random, mock_model):
    g6 = SynthesizeReference(mock_model, Employee.model_fields["manager"])
    g6.source = MagicMock(
        next=Mock(side_effect=[sentinel.POOL_VALUE]), noise_gen=Mock(side_effect=[sentinel.NOISE])
    )
    assert g6.next() == sentinel.POOL_VALUE

    assert g6.noise_gen() == sentinel.NOISE


def test_synth_union_default(seeded_random, mock_model):
    g8 = SynthesizeUnion(
        mock_model,
        Employee.model_fields["name"],
        sources={"str": SynthesizeName, "None": SynthesizeNone},
    )
    assert g8.next() == "Vrpo"
    names = list(g8.next() for _ in range(50))
    assert sum(1 for n in names if n is None) == 3


def test_synth_union_subdomain(seeded_random, mock_model):
    class EmployeeU(BaseModel):
        name: Annotated[
            str | None,
            Field(
                max_length=40,
                json_schema_extra={"domain": "name", "subdomain": {"str": 50, "None": 50}},
            ),
        ]

    g8 = SynthesizeUnion(
        mock_model,
        EmployeeU.model_fields["name"],
        sources={"str": SynthesizeName, "None": SynthesizeNone},
    )
    assert g8.next() is None
    names = list(g8.next() for _ in range(50))
    assert sum(1 for n in names if n is None) == 19


RULE_2_MATCHES = [
    (Synthesizer, []),
    (SynthesizeString, ["name"]),
    (SynthesizeNumber, []),
    (SynthesizeName, ["name"]),
    (SynthesizeInteger, ["id", "manager"]),
    (SynthesizeFloat, ["velocity"]),
    (SynthesizeDate, ["hire_date"]),
]


@pytest.fixture(params=RULE_2_MATCHES)
def synth_used_for_fields(request):
    synth, fields = request.param
    used_for = [
        name
        for name in Employee.model_fields
        if synth.match(
            Employee.model_fields[name].annotation, Employee.model_fields[name].json_schema_extra
        )
    ]
    return synth, used_for, fields


def test_rule_2_match(synth_used_for_fields):
    synth, actual, expected = synth_used_for_fields
    assert actual == expected, f"{synth}.match() error: {actual=} {expected=}"
