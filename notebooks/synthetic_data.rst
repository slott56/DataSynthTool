######################
Synthetic Data Spike
######################

Clean way to handle production of high-volume data.

Also.

Clean way to handle Primary/Foriegn Key relationships.

Architecture
============

Three parts:

-  Pydantic is expected to provide the essential class definitions.

-  Field-level Synthesizers to emit atomic data.

-  Model and Schema-level collections.

Sample Pydantic Class Definitions
=================================

These two classes (with circular references) will be our working
example.

.. code:: ipython3

    import datetime
    from typing import Annotated
    from pydantic import BaseModel, Field
    
    class Employee(BaseModel):
        id: Annotated[
            int, Field(json_schema_extra={"sql": {'key': 'primary'}}) 
        ]
        name: Annotated[
            str, Field(max_length=40)
        ]
        hire_date: Annotated[
            datetime.datetime, Field(ge=datetime.datetime(2021, 1, 18))
        ]
        velocity: Annotated[
            float, Field(ge=2, le=21, 
                         json_schema_extra={"distribution": "normal"})
        ]
        manager: Annotated[
            int, Field(json_schema_extra={"sql": {'key': 'foreign', 'reference': 'Manager.id'}})
        ]
    
    
    class Manager(BaseModel):
        id: Annotated[
            int, Field(json_schema_extra={"sql": {'key': 'primary'}}) 
        ]
        employee_id: Annotated[
            int, Field(json_schema_extra={"sql": {'key': 'foreign', 'reference': 'Employee.id'}})
        ]
        department_id: Annotated[
            str, Field(max_length=8)
        ]

Field-level Data Synthesizer
============================

Two aspects of each synthesizer.

-  The essential synth algorithms for various data types

-  Behavior of the synth process:

   -  Independent generation – duplicates are possible.
   -  Pooled generation – duplicates will be prevented.

Plus, in order to handle foreign key references. A reference synthesizer
that extracts values from a pooled synthesizer.

.. code:: ipython3

    import abc
    from annotated_types import MaxLen, MinLen, Ge, Le
    from operator import attrgetter
    import random
    from typing import Any, Iterator
    
    from pydantic.fields import FieldInfo
    
    class Behavior:
        def __init__(self, synth: "Synthesizer") -> None:
            self.synth = synth
    
        def __repr__(self) -> str:
            return self.__class__.__name__
            
        @abc.abstractmethod
        def iterator(self) -> Iterator[Any]:
            ...        
    
        @abc.abstractmethod
        def next(self) -> Any:
            ...
    
    class Independent(Behavior):
        def __init__(self, synth: "Synthesizer") -> None:
            super().__init__(synth)
            self.count = 0
        def iterator(self) -> Iterator[Any]:
            return self.synth
        def next(self) -> Any:
            v = self.synth(self.count)
            self.count += 1
            return v
    
    class Pooled(Behavior):
        def __init__(self, synth: "Synthesizer") -> None:
            super().__init__(synth)
            assert self.synth.model.rows is not None, f"no target rows for {self.synth.model}"
            self.fill()
    
        def fill(self) -> None:
            # Often, these are enough
            self.pool = set(
                self.synth(x)
                for x in range(self.synth.model.rows)
            )
            # May need a few more
            count = self.synth.model.rows
            while len(self.pool) != self.synth.model.rows:
                self.pool.add(self.synth(count))
                count += 1
            self.pool = list(self.pool)
            random.shuffle(self.pool)
    
        def iterator(self) -> Iterator[Any]:
            return iter(self.pool)
            
        def next(self) -> Any:
            return random.choice(self.pool)

.. code:: ipython3

    class Synthesizer:
        model_ref = ""
        field_ref = ""
        
        def __init__(
            self, 
            model: "ModelSynthesizer", 
            field: FieldInfo, 
            behavior: type[Behavior] = Independent
        ) -> None:
            self.model = model
            self.field = field
            self.json_schema_extra = self.field.json_schema_extra or {}
            self.prepare()
            self.behavior = behavior(self)
    
        def __repr__(self) -> str:
            return f"{self.__class__.__name__}({self.model}, {self.field}, {self.behavior})"
    
        def __iter__(self) -> Iterator[Any]:
            return self.behavior.iterator()
    
        def __next__(self) -> Any:
            return self.behavior.next()
    
        @abc.abstractmethod
        def prepare(self) -> None:
            """Parse the field."""
            ...
            
        @abc.abstractmethod
        def __call__(self, sequence: int | None = None) -> Any:
            """Generate a value."""
            ...
    
        def get_meta(self, cls_, getter):
            matches = [m for m in self.field.metadata if isinstance(m, cls_)]
            if len(matches) == 0:
                return None
            elif len(matches) != 1:
                raise ValueError(f"{matches}")
            else:
                return getter(matches[0])
    
        @classmethod
        def match(cls, field: FieldInfo) -> bool:
            # return issubclass(field.annotation, int)
            return False

The Model Synthesizer Protocol
------------------------------

.. code:: ipython3

    from dataclasses import dataclass
    
    @dataclass
    class MockModelSynthesizer:
        rows: int
    
    model = MockModelSynthesizer(12)

String Synthesizer
------------------

.. code:: ipython3

    import string
    
    class SynthesizeString(Synthesizer):
        domain = string.ascii_letters + string.punctuation
        min_default = 1
        
        def prepare(self) -> None:
            self.min_length = self.get_meta(MinLen, attrgetter("min_length"))
            self.max_length = self.get_meta(MaxLen, attrgetter("max_length"))
            if self.min_length is None:
                self.min_length = self.min_default
            if self.max_length is None:
                self.max_length = 32
                
        def __call__(self, sequence: int | None = None) -> Any:
            size = random.randint(self.min_length, self.max_length)
            return "".join([
                random.choice(self.domain)
                for _ in range(size)
            ])
            
        @classmethod
        def match(cls, field: FieldInfo) -> bool:
            return issubclass(field.annotation, str)


.. code:: ipython3

    g = SynthesizeString(None, Employee.model_fields['name'])

.. code:: ipython3

    g()




::

    'ZJu,ZWy'



.. code:: ipython3

    ig = SynthesizeString(model, Employee.model_fields['name'], behavior=Independent)
    next(iter(ig))




::

    't%jRJCwdngrbqSn\'?&l+WJ!&H$dd"&h<'



.. code:: ipython3

    pg = SynthesizeString(model, Employee.model_fields['name'], behavior=Pooled)
    next(iter(pg))




::

    "<r{'"



.. code:: ipython3

    pg.behavior.pool[0]




::

    "<r{'"



Name Synthesizer
----------------

Not very good.

Options

1. get first names from census data; get digraph frequency from last
   names.

2. Use NLTK digraph frequencies to generate plausible English-like
   works.

.. code:: ipython3

    class SynthesizeName(SynthesizeString):
        domain = string.ascii_letters
        min_default = 3
        
        def __call__(self, sequence: int | None = None) -> Any:
            return super().__call__(sequence).title()
    
        @classmethod
        def match(cls, field: FieldInfo) -> bool:
            return (
                issubclass(field.annotation, str)
                and field.json_schema_extra and field.json_schema_extra.get("domain") == "name"
            )


.. code:: ipython3

    g2 = SynthesizeName(model, Employee.model_fields['name'])
    [next(g2) for _ in range(10)]




::

    ['Ckbnjjtiiezbvavbatcdm',
     'Dpuxzzscvtmyzccsnfl',
     'Movedguauzstngqubtszm',
     'Zgooedlwgukursklbbwbr',
     'Yytvpsthmsllancauvihan',
     'Gjsvhjiutwrsdcalnou',
     'Iogmrzbafhweikoqoymefcjaaus',
     'Xbbvwfakdjimbrhmktmunthqcgaokfq',
     'Mkbbfejywjrjfophbhzmukkrcxdozbvdrfdr',
     'Omfzkuipvh']



Number Synthesizers
-------------------

.. code:: ipython3

    from functools import partial
    
    class SynthesizeNumber(Synthesizer):
        default_distribution = "uniform"
        
        def prepare(self) -> None:
            self.min_value = self.get_meta(Ge, attrgetter("ge"))
            self.max_value = self.get_meta(Le, attrgetter("le"))
            if self.min_value is None:
                self.min_value = 0
            if self.max_value is None:
                self.max_value = 2**32-1
            self.dist_name = self.json_schema_extra.get("distribution", self.default_distribution)
    
    class SynthesizeInteger(SynthesizeNumber):
        def prepare(self) -> None:
            super().prepare()
            self.gen = {
                "uniform": partial(random.randint, self.min_value, self.max_value), 
                "normal": partial(random.normalvariate, 
                                  mu=(self.max_value + self.min_value)/2, 
                                  sigma = (self.max_value - self.min_value)/6)
            }[self.dist_name]
        def __call__(self, sequence: int | None = None) -> Any:
            v = int(self.gen())
            while v < self.min_value or v > self.max_value:
                v = int(self.gen())
            return v
    
        @classmethod
        def match(cls, field: FieldInfo) -> bool:
            return issubclass(field.annotation, int)
    
    class SynthesizeFloat(SynthesizeNumber):
        def prepare(self) -> None:
            super().prepare()
            self.gen = {
                "uniform": partial(random.randint, self.min_value, self.max_value), 
                "normal": partial(random.normalvariate, 
                                  mu=(self.max_value + self.min_value)/2, 
                                  sigma=(self.max_value - self.min_value)/6)
            }[self.dist_name]
        def __call__(self, sequence: int | None = None) -> Any:
            v = float(self.gen())
            while v < self.min_value or v > self.max_value:
                v = float(self.gen())
            return v
    
        @classmethod
        def match(cls, field: FieldInfo) -> bool:
            return issubclass(field.annotation, float)
    


.. code:: ipython3

    g3 = SynthesizeInteger(model, Employee.model_fields['id'])

.. code:: ipython3

    [next(g3) for _ in range(10)]




::

    [1620130150,
     470998807,
     562439064,
     400356711,
     426271425,
     2981324347,
     3892751825,
     612460124,
     514934604,
     910507644]



.. code:: ipython3

    g4 = SynthesizeFloat(model, Employee.model_fields['velocity'])

.. code:: ipython3

    [next(g4) for _ in range(10)]




::

    [10.333933607379473,
     10.920061248849933,
     14.731619274213585,
     14.332560156503941,
     4.737780386229399,
     5.328339687110079,
     14.014912287900792,
     18.46094923703935,
     13.988209306867594,
     10.27216839327092]



Expect min 2, max 21, mean :math:`\tfrac{21 + 2}{2}` = 11.5, stdev
:math:`\tfrac{21+2}{6}` = 3.83

.. code:: ipython3

    from statistics import mean, stdev
    s = [next(g4) for _ in range(200)]
    f"{min(s)=:.2f}, {max(s)=:.2f}, {mean(s)=:.2f}, {stdev(s)=:.3f}"




::

    'min(s)=4.16, max(s)=20.48, mean(s)=11.79, stdev(s)=3.330'



Date Synthesizer
----------------

.. code:: ipython3

    class SynthesizeDate(SynthesizeNumber):
        def prepare(self) -> None:
            super().prepare()
            self.min_value = self.get_meta(Ge, attrgetter("ge"))
            self.max_value = self.get_meta(Le, attrgetter("le"))
            if self.min_value is None:
                self.min_value = datetime.datetime(1970,1,1)
            if self.max_value is None:
                self.max_value = datetime.datetime(2099,12,31)
            self.dist_name = self.json_schema_extra.get("distribution", self.default_distribution)
    
            self.min_date = self.min_value.timestamp()
            self.max_date = self.max_value.timestamp()
            self.gen = {
                "uniform": lambda : random.random() * (self.max_date - self.min_date) + self.min_date, 
                "normal": partial(random.normalvariate, mu=(self.max_date + self.min_date)/2, sigma = (self.max_date - self.min_date)/6)
            }[self.dist_name]
            
        def __call__(self, sequence: int | None = None) -> Any:
            dt = self.gen()
            return datetime.datetime.fromtimestamp(dt)
            
        @classmethod
        def match(cls, field: FieldInfo) -> bool:
            return issubclass(field.annotation, datetime.datetime)


.. code:: ipython3

    g5 = SynthesizeDate(model, Employee.model_fields['hire_date'])

.. code:: ipython3

    next(g5)




::

    datetime.datetime(2034, 11, 28, 6, 32, 24, 458422)



Reference Synthesizer
---------------------

Gets values from another Pooled Synthesizer.

Requies
``json_schema_extra={"sql": {"key": "foreign", "reference": "model.field"}}``

The ``source`` attribute is stateful – It’s set to a specific
``Synthesizer`` instance.

The update is done as part of preparing a Model iterator – as late as
possible.

The pool of values are generated when a Pooled Synthesizer is built.

.. code:: ipython3

    class SynthesizeReference(Synthesizer):
        
        def __init__(self, model: "ModelSynthesizer", field: FieldInfo, behavior: type[Behavior] = Independent) -> None:
            super().__init__(model, field, behavior)
            # "sql": {'key': "foreign", "reference": "Manager.id"}
            self.model_ref, self.field_ref = self.json_schema_extra["sql"]["reference"].split(".")
            self.source: Synthesizer | None = None
            
        def __call__(self, sequence: int | None = None) -> Any:
            """Generate a value."""
            try:
                return next(self.source)
            except TypeError as ex:
                # Usually, it's because the source is not resolved or not a pool.
                raise ValueError(f"source {self.model_ref}.{self.field_ref} not resolved")

Model Synthesizer
=================

A Model is a collection of atomic fields.

The point of a ``ModelSynthesizer`` is to produce values for a Pydantic
``BaseModel`` class.

.. code:: ipython3

    def synth_class_iter(base: type[Synthesizer] = Synthesizer) -> Iterator[tuple[str, type]]:
        """
        Find all Synthesizers.
    
        Tends to be top-down from most general to most specific.
        It's more useful reversed, though, starting from most specific.
        """
        yield base.__name__, base
        for c in base.__subclasses__():
            yield from synth_class_iter(c)

.. code:: ipython3

    class ModelIter:
        def __init__(self, model: "ModelSynthesizer") -> None:
            self.model = model
            self.synth_iter = {
                name: iter(synth) 
                for name, synth in self.model.fields.items()
            }
    
        def __repr__(self) -> str:
            return f"ModelIter({self.model})"
    
        def __iter__(self) -> Iterator[BaseModel]:
            return self
            
        def __next__(self) -> BaseModel:
            data = {
                name: next(g)
                for name, g in self.synth_iter.items()
            }
            try:
                return self.model.model_class(**data)
            except Exception:
                print("VALIDATION ERROR")
                print(data)
                raise
            
    class ModelSynthesizer:
        def __init__(self, cls_: type[BaseModel], rows: int | None = None) -> None:
            self.model_class = cls_
            self.rows = rows 
            # Reversed to put subclasses first.
            self._synth_name_map = dict(reversed(list(synth_class_iter())))
    
            self.fields = {
                name: self._make_field_synth(field)
                for name, field in self.model_class.model_fields.items()
            }
    
        def __repr__(self) -> str:
            return f"ModelSynthesizer({self.model_class}, rows={self.rows})"
            
        @property
        def references(self) -> list[str]:
            """List of field names contain references elsewhere in a schema."""
            refs = [name for name, field in self.fields.items() if field.has_reference]
            return refs
            
        def _make_field_synth(self, field: FieldInfo) -> Synthesizer:
            json_schema_extra = field.json_schema_extra or {}
    
            # Rule 0 -- PK's are pooled, FK's are references to PK pools.
            behavior: Behavior
            if "sql" in json_schema_extra:
                key = json_schema_extra["sql"].get("key", "primary")
                if key == "primary":
                    # "sql": {"key": "primary"} -- Pooled -- based on type.
                    behavior = Pooled
                elif key == "foreign":
                    # "sql": {'key': "foreign", "reference": "Manager.id"} -- Independent instance of ``SynthesizeReference``.
                    # Type comes from the referenced source.
                    return SynthesizeReference(self, field, Independent)
                else:
                    # TODO: Raise ValueError? Warning?
                    behavior = Pooled
            else:
                behavior = Independent
    
            synth_class: type[Synthesizer] | None = None
            
            # Rule 1 -- json_schema_extra names a synthesizer class to use.
            if "synthesizer" in json_schema_extra:
                # Map synthesizer name to implementation classes.
                synth_class = self._synth_name_map[json_schema_extra["synthesizer"]]
                return synth_class(self, field, behavior)
                            
            # Rule 2 -- deduce synthesizer from annotation class and json_schema_extra.
            # Works best if list has subclasses first, superclasses last.
            for name in self._synth_name_map.keys():
                cls_ = self._synth_name_map[name]
                if cls_.match(field):
                    synth_class = cls_
                    break
            if synth_class is None:
                raise ValueError(f"no synth class matches {field=}")
            return synth_class(self, field, behavior)
    
        def __iter__(self) -> Iterator[BaseModel]:
            return ModelIter(self)

Our example has inter-model references. It can’t work.

.. code:: ipython3

    emp_synth = ModelSynthesizer(Employee, 100)
    emp_synth_iter = iter(emp_synth)
    for _ in range(10):
        print(next(emp_synth_iter))


::


    ---------------------------------------------------------------------------

    TypeError                                 Traceback (most recent call last)

    Cell In[22], line 12, in SynthesizeReference.__call__(self, sequence)
         11 try:
    ---> 12     return next(self.source)
         13 except TypeError as ex:
         14     # Usually, it's because the source is not resolved or not a pool.


    TypeError: 'NoneType' object is not an iterator

    
    During handling of the above exception, another exception occurred:


    ValueError                                Traceback (most recent call last)

    Cell In[33], line 4
          2 emp_synth_iter = iter(emp_synth)
          3 for _ in range(10):
    ----> 4     print(next(emp_synth_iter))


    Cell In[32], line 17, in ModelIter.__next__(self)
         15 def __next__(self) -> BaseModel:
         16     data = {
    ---> 17         name: next(g)
         18         for name, g in self.synth_iter.items()
         19     }
         20     try:
         21         return self.model.model_class(**data)


    Cell In[3], line 24, in Synthesizer.__next__(self)
         23 def __next__(self) -> Any:
    ---> 24     return self.behavior.next()


    Cell In[2], line 31, in Independent.next(self)
         30 def next(self) -> Any:
    ---> 31     v = self.synth(self.count)
         32     self.count += 1
         33     return v


    Cell In[22], line 15, in SynthesizeReference.__call__(self, sequence)
         12     return next(self.source)
         13 except TypeError as ex:
         14     # Usually, it's because the source is not resolved or not a pool.
    ---> 15     raise ValueError(f"source {self.model_ref}.{self.field_ref} not resolved")


    ValueError: source Manager.id not resolved


Schema Synthesizer
==================

A Schema is a collection of Models.

This is how we handle Foreign Key references to another model’s Primary
Key.

The PK is a ``Synthesizer`` with ``Pooled`` behavior.

The FK is a ``SynthesizeReference`` that extracts values from the pool.

The ``prepare()`` process resolves references.

.. code:: ipython3

    class SchemaSynthesizer:
        def __init__(self) -> None:
            self.schema = {}
            self.references = []
    
        def add(self, model_class: type[BaseModel], rows: int | None = None) -> None:
            model = ModelSynthesizer(model_class, rows)
            self.schema[model_class.__name__] = model
            references = [
                (model, field, field.model_ref, field.field_ref)
                for field in model.fields.values()
                if field.model_ref and field.field_ref
            ]
            self.references.extend(references)
    
        def prepare(self) -> None:
            while self.references:
                model, field, model_ref, field_ref = self.references.pop()
                # DEBUG: print(f"Resolving Reference: {model} {field} refers to {model_ref}.{field_ref}")
                try:
                    target = self.schema[model_ref].fields[field_ref]
                except KeyError:
                    print(f"{model_ref} not in {self.schema.keys()}")
                    raise KeyError(f"can't resolve {model} {field} ref to {model_ref}.{field_ref}")
                field.source = target
                # Not needed here because it's handled when the Pooled Synthesizer is created
                # Alternative is to defer to here:  target.behavior.fill()
    
        def rows(self, model_class: type[BaseModel]) -> Iterator[BaseModel]:
            self.prepare()
            model = self.schema[model_class.__name__]
            return iter(model)

.. code:: ipython3

    s = SchemaSynthesizer()
    s.add(Employee, 10)
    s.add(Manager, 2)
    
    print(s.schema['Employee'])
    for name, f in s.schema['Employee'].fields.items():
        print(f"  {name}: {f}")


::

    ModelSynthesizer(<class '__main__.Employee'>, rows=10)
      id: SynthesizeInteger(ModelSynthesizer(<class '__main__.Employee'>, rows=10), annotation=int required=True json_schema_extra={'sql': {'key': 'primary'}}, Pooled)
      name: SynthesizeString(ModelSynthesizer(<class '__main__.Employee'>, rows=10), annotation=str required=True metadata=[MaxLen(max_length=40)], Independent)
      hire_date: SynthesizeDate(ModelSynthesizer(<class '__main__.Employee'>, rows=10), annotation=datetime required=True metadata=[Ge(ge=datetime.datetime(2021, 1, 18, 0, 0))], Independent)
      velocity: SynthesizeFloat(ModelSynthesizer(<class '__main__.Employee'>, rows=10), annotation=float required=True json_schema_extra={'distribution': 'normal'} metadata=[Ge(ge=2), Le(le=21)], Independent)
      manager: SynthesizeReference(ModelSynthesizer(<class '__main__.Employee'>, rows=10), annotation=int required=True json_schema_extra={'sql': {'key': 'foreign', 'reference': 'Manager.id'}}, Independent)


.. code:: ipython3

    for e in s.rows(Employee):
        print(e)


::

    id=1830925711 name="Ew#!yPlKg=KM]j'y;" hire_date=datetime.datetime(2067, 12, 26, 22, 17, 32, 717739) velocity=12.643047311951968 manager=2657133193
    id=3042616909 name='THVafJDTtyo?":Wu=y]P' hire_date=datetime.datetime(2093, 8, 9, 14, 4, 58, 483257) velocity=15.138835992381933 manager=2657133193
    id=1220375740 name="Yh'o$wMR#}eBu*Jg*rowD'B_I+Lz(C" hire_date=datetime.datetime(2043, 12, 2, 4, 2, 18, 743324) velocity=8.228239779243467 manager=3836089139
    id=170845071 name='PXZfmUy";v;' hire_date=datetime.datetime(2088, 9, 28, 12, 14, 4, 442257) velocity=8.386546313449461 manager=2657133193
    id=2734751330 name='-(' hire_date=datetime.datetime(2062, 4, 21, 17, 28, 53, 322033) velocity=8.526964708078806 manager=3836089139
    id=2057004573 name='gYjnpM+?+)]}V<EQ<!"e' hire_date=datetime.datetime(2095, 10, 24, 8, 54, 55, 258200) velocity=14.546317658884723 manager=3836089139
    id=4105659792 name='|TXPvba^mg+Yx-)ILjiK%!J;@C_W' hire_date=datetime.datetime(2075, 1, 10, 19, 10, 34, 547362) velocity=10.00286845639161 manager=2657133193
    id=3285262661 name="Ozi~ACEVb!i@Re~#LbKjYla*);'+X@" hire_date=datetime.datetime(2038, 11, 12, 21, 59, 41, 442073) velocity=11.966749342732534 manager=3836089139
    id=2054336087 name='Yv_gll.wi!%p:V%w|mfpwrnSoA%%R.n+pE;k' hire_date=datetime.datetime(2070, 7, 10, 15, 48, 11, 567657) velocity=16.75815000413133 manager=2657133193
    id=4136022130 name='+;{q%/[w' hire_date=datetime.datetime(2021, 10, 19, 8, 14, 57, 574306) velocity=13.998976460717653 manager=3836089139


.. code:: ipython3

    for m in s.rows(Manager):
        print(m)


::

    id=2657133193 employee_id=3042616909 department_id='zsV(|'
    id=3836089139 employee_id=170845071 department_id='R?V'


