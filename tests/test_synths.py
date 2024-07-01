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
    synth = Mock(return_value=sentinel.OBJECT)
    i = Independent(synth)
    assert repr(i) == "Independent"
    assert i.iterator() == synth
    assert i.next() == sentinel.OBJECT


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
        side_effect=objects,
    )
    i = Pooled(synth)
    assert repr(i) == "Pooled"
    assert set(i.iterator()) == set(objects)
    assert i.next() in objects
    assert i.count == 7


def test_synth_string(seeded_random, mock_model):
    ig = SynthesizeString(mock_model, Employee.model_fields["name"], behavior=Independent)
    assert next(iter(ig)) == "$D@=2.wf"
    assert (
        repr(ig)
        == f"SynthesizeString({repr(mock_model)}, {str(Employee.model_fields['name'])}, Independent)"
    )

    pg = SynthesizeString(mock_model, Employee.model_fields["name"], behavior=Pooled)
    pool = {
        "an$h:|tzfV=ZlD!",
        "lW%$,<",
        "zWLD4<L.,Q-",
        ">-QD[r",
        "5PN;vCzxs*nr6e~@5\\QCryh=",
        "eBkWkTO=2b`,'/4q5xWm)RQm\\dAg\"x}/xeCs",
        "(>%ITC)<i|I<t`Ss[3B2@",
        "MnB&~[e0Q+gFqpOj9{)&u>F",
        "/FX5[!}}Ba7a.qGran:4P5",
        "d!mJ_#/OH?(?i++~_)e11u]g6BdnW<f~y:|",
    }
    assert set(pg.behavior.pool) == pool
    assert next(iter(pg)) in pool


def test_synth_name(seeded_random, mock_model):
    g2 = SynthesizeName(mock_model, Employee.model_fields["name"])
    assert [next(g2) for _ in range(10)] == [
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


def test_syth_int(seeded_random, mock_model):
    g3 = SynthesizeInteger(mock_model, Employee.model_fields["id"])
    print([next(g3) for _ in range(10)])


def test_syth_float(seeded_random, mock_model):
    g4 = SynthesizeFloat(mock_model, Employee.model_fields["velocity"])

    # Expect min 2, max 21, mean $\tfrac{21 + 2}{2}$ = 11.5, stdev $\tfrac{21+2}{6}$ = 3.83
    s = [next(g4) for _ in range(1000)]
    assert min(s) == pytest.approx(2, rel=1)
    assert max(s) == pytest.approx(21, rel=1)
    assert mean(s) == pytest.approx(11.5, rel=0.1)
    assert stdev(s) == pytest.approx(3.83, rel=0.5)


def test_synth_date(seeded_random, mock_model):
    g5 = SynthesizeDate(mock_model, Employee.model_fields["hire_date"])
    assert next(g5) == datetime.datetime(2071, 7, 13, 13, 16, 4, 252645)


def test_synth_reference(seeded_random, mock_model):
    g6 = SynthesizeReference(mock_model, Employee.model_fields["manager"])
    g6.source = MagicMock(__next__=Mock(side_effect=[sentinel.POOL_VALUE]))
    assert next(g6) == sentinel.POOL_VALUE


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
    used_for = [name for name in Employee.model_fields if synth.match(Employee.model_fields[name])]
    return synth, used_for, fields


def test_rule_2_match(synth_used_for_fields):
    synth, actual, expected = synth_used_for_fields
    assert actual == expected, f"{synth}.match() error: {actual=} {expected=}"
