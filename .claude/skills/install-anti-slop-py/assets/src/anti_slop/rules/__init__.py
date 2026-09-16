"""Rule registry: every rule exposes `check(context)` yielding findings."""

from anti_slop.rules import (
    any_alias,
    chained_cast,
    dynamic_attribute,
    known_value_widening,
    module_mocking,
    object_contracts,
    runtime_narrowing,
    safety_comment,
    shape_names,
    unsafe_dictionary,
)

ALL = [
    safety_comment.check,
    runtime_narrowing.check,
    module_mocking.check,
    chained_cast.check,
    known_value_widening.check,
    dynamic_attribute.check,
    shape_names.check,
    object_contracts.check,
    unsafe_dictionary.check,
    any_alias.check,
]
