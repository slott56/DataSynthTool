##################
Future Directions
##################

See :ref:`containers.model` for a list of features.


-   Additional string formats and patterns.

-   Additional numeric distributions.

-   Additional date, datetime, and time features.

-   Enumerated value with a distribution histogram.

-   Optional values are a more subtle aspect of a domain definition.

    -   A domain-indepedent null is the SQL ``NULL`` or Python ``None`` value.
        This can be done with a JSONSchema ``oneOf`` and a ``json_schema_extra`` to provide probability of a ``null``.

        More generally, it requires a ``oneOf`` with probabilities for each alternative.
        This leads to a ``Union[Annnotated[int, ...], Annotated[None, ...], etc.]`` with probabilities for each choice.

    -   A domain-specific null is a coded value, like social security number ``999-99-9999`` that indicates some sort of missing or not-applicable value.
        This is also a complicated ``Union``.
        This leads to a ``Union[Annnotated[int, ...], Annotated[Literal[n], ...], etc.]`` with probabilities for each choice.
