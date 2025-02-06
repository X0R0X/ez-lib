import os
import typing_extensions
from typing import Union, get_origin, get_args, Optional

from ez_lib.types import basic_types


class EmptyEnvVarError(Exception):
    def __init__(self, missing_env_vars: list[str]):
        self.missing_env_vars = missing_env_vars

        self.message = (
            f"Empty Environment Variables: {missing_env_vars}"
        )


class InvalidAnnotatedType(Exception):
    def __init__(
            self, field_name: str, expected_type: type, field_value: basic_types
    ):
        self.field_name = field_name
        self.expected_type = expected_type
        self.field_value = field_value

        self.message = (
            f"Invalid Annotated Type '{field_name}': "
            f"Expecting type {str(expected_type).replace('<class ','')[:-1]}, "
            f"got value '{field_value}'"
        )

class BaseEnvConfig:
    """
    Set environment variables to class variables.

    Declare class variables, these will be inferred from the environment and
    will be typed either automatically or by declared type, e.g.:

    environment:
        export MY_FLOAT=3.14159
        export MY_INT=42
        export MY_STR=some_string
        export MY_BOOL=True
        export MY_BOOL2=false
        export MY_TYPED_STR=false
        export MY_TYPED_SET_OPT_BOOL=True
        export MY_SET_OPT_FLOAT=1.618

    python:
        class MyConfig(BaseEnvConfig):
            MY_FLOAT_VAR = None
            MY_STR = None
            MY_INT = None
            MY_BOOL = None
            MY_BOOL2 = None
            MY_TYPED_STR: str = None
            MY_TYPED_SET_OPT_BOOL:Optional[bool] = None
            MY_TYPED_OPT_UNSET_INT: Optional[int] = None
            MY_SET_OPT_FLOAT: Optional = None
            MY_UNSET_OPT_FLOAT: Optional = None

        MyConfig.init()

    config_values:
        {
            'MY_FLOAT_VAR': 3.14159,
            'MY_STR': 'some_string',
            'MY_INT': 42,
            'MY_BOOL': True,
            'MY_BOOL2': False,
            'MY_TYPED_STR': 'false',
            'MY_TYPED_SET_OPT_BOOL': True,
            'MY_TYPED_OPT_UNSET_INT': None,
            'MY_SET_OPT_FLOAT': 1.618,
            'MY_UNSET_OPT_FLOAT': None
        }


    If non-optional declared variables are not exported in the environment,
    `EmptyEnvVarError` is thrown.

    If the type is wrongly annotated, `InvalidAnnotatedType` is thrown.
    """

    @classmethod
    def init(cls):
        typed, optional = cls._get_typed_and_opt()
        for env_var_name in cls._get_config_var_names():
            env_var_val = os.environ.get(env_var_name)
            if env_var_val:
                if env_var_name in typed.keys():
                    type_ = typed[env_var_name]
                    try:
                        setattr(
                            cls, env_var_name, type_(env_var_val)
                        )
                    except ValueError:
                        raise InvalidAnnotatedType(
                            env_var_name, type_, env_var_val
                        )
                else:
                    setattr(cls, env_var_name, cls._type_env_var(env_var_val))

        cls._check_all_vars(optional)

    @classmethod
    def _get_typed_and_opt(cls):
        optional = []
        del_fields = []
        typed = typing_extensions.get_type_hints(cls)
        for field_name, field_type in typed.items():
            if get_origin(field_type) is Union:
                optional.append(field_name)
                typed[field_name] = get_args(field_type)[0]
            elif field_type is Optional:
                optional.append(field_name)
                del_fields.append(field_name)

        for field_name in del_fields:
            del typed[field_name]

        return typed, optional

    @classmethod
    def _check_all_vars(cls, optional):
        missing_vars = []
        for attr_name in cls._get_config_var_names():
            if getattr(cls, attr_name) is None and attr_name not in optional:
                missing_vars.append(attr_name)

        if missing_vars:
            raise EmptyEnvVarError(missing_vars)

    @classmethod
    def _get_config_var_names(cls):
        config_var_names = []
        for k in cls.__dict__.keys():
            s = str(k)
            if s.isupper():
                config_var_names.append(s)

        return config_var_names

    @staticmethod
    def _type_env_var(env_var: str | None) -> basic_types:
        if env_var is None:
            return None

        if env_var.lower() == "false":
            return False
        elif env_var.lower() == "true":
            return True
        elif '.' in env_var:
            try:
                return float(env_var)
            except ValueError:
                return env_var
        else:
            try:
                return int(env_var)
            except ValueError:
                return env_var
