..  _components:

##############################
Synthetic Data Tool Components
##############################

The Synthetic Data Tool package contains a number of field-level synthesizers, a model synthesizer, and a schema synthesizer.

..  uml::

    top to bottom direction

    package "synths" {
        class SynthesizeString
        class SynthesizeName
        SynthesizeString <|-- SynthesizeName
        class SynthesizeNumber
        class SynthesizeInteger
        SynthesizeNumber <|-- SynthesizeInteger
        class SynthesizeReference
    }

    package "base" {
        class Synthesizer
        class Behavior
        class Pooled
        class Independent
        class SynthesizeModel {
            fields: dict[str, Synthesizer]
        }
        class SynthesizeSchema {
            add(Model)
            rows(Model)
        }

        SynthesizeSchema o-- SynthesizeModel
        SynthesizeModel o-- Synthesizer

        Synthesizer - Behavior
        Behavior <|-- Pooled
        Behavior <|-- Independent
    }

    synths.SynthesizeString -up-|> base.Synthesizer
    synths.SynthesizeNumber -up-|> base.Synthesizer
    synths.SynthesizeReference -up-|> base.Synthesizer

``base`` Module
################

..  automodule:: synthdata.base

``synths`` Module
##################

..  automodule:: synthdata.synths
    :members:
    :special-members: __call__
    :show-inheritance:
