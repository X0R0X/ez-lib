from typing import Callable, Any, Coroutine

# Basic (i.e. `atomic`) types and None
basic_types = str | float | int | bool | None

# Serialized JSON list of basic types, should also contain typed recursive
# list[basic_types] instead of just `list`
json_list = list[basic_types | list]

# Serialized JSON dist of basic types (key is of str type), should also contain
# typed recursive dict[str, basic_types] instead of just `dict`
json_dict = dict[str, basic_types | dict]

# All possible JSON Types
json_types = basic_types | json_list | json_dict

# Serialized JSON dict
json_ser = dict[str, json_types]

# Async Callable (asynchronous `Callable` definition)
AsyncCallable = Callable[..., Coroutine[Any, Any, Any]]
