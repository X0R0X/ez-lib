from abc import ABC
import contextlib
from ez_lib.types import json_ser
from logging import Logger
from typing import Iterable, Any

try:
    import sqlalchemy
    from sqlalchemy.ext.asyncio import (
        AsyncEngine,
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
except ImportError:
    sqlalchemy = None

if sqlalchemy:

    class AsyncPgWrapper:
        log = None

        def __init__(
                self,
                host: str,
                port: int,
                user: str,
                passwd: str,
                db_name: str,
                pool_size: int = 10,
                pool_max_overflow: int = 10,
                pool_timeout: int = 30,
                pool_recycle: int = 1800,
                log: Logger | None = None
        ):
            self._host = host
            self._port = port
            self._user = user
            self._passwd = passwd
            self._db_name = db_name
            self._pool_size = pool_size
            self._pool_max_overflow = pool_max_overflow
            self._pool_timeout = pool_timeout
            self._pool_recycle = pool_recycle
            AsyncPgWrapper.log = log

            self._engine: AsyncEngine | None = None
            self._session_maker: async_sessionmaker[
                                     AsyncSession
                                 ] | None = None

        @property
        def engine(self):
            return self._engine

        @property
        def session_maker(self):
            return self._session_maker

        async def init(self):
            self._engine = create_async_engine(
                self._mk_conn_str(),
                pool_size=self._pool_size,
                max_overflow=self._pool_max_overflow,
                pool_timeout=self._pool_timeout,
                pool_recycle=self._pool_recycle,
                echo=False
            )

            self._session_maker = async_sessionmaker(
                bind=self._engine,
                expire_on_commit=False,
                autoflush=True,
                class_=AsyncSession
            )

            if AsyncPgWrapper.log:
                AsyncPgWrapper.log.info("Postgres Connection Pool Created.")

        @contextlib.asynccontextmanager
        async def get_session(self) -> AsyncSession:
            if not async_sessionmaker:
                raise RuntimeError(
                    "SQLAlchemy Postgres async SessionMaker not inited."
                )

            session = self._session_maker()
            try:
                yield session
            except BaseException as e:
                if AsyncPgWrapper.log:
                    AsyncPgWrapper.log.error(
                        f"Error during leased SQL Alchemy Postgres AsyncSession, "
                        f"Rolling Back the tx...\nerror={e}"
                    )
                await session.rollback()
                raise e
            finally:
                await session.close()

        async def close(self):
            # todo check opened conns
            self._engine.pool.dispose()

        def _mk_conn_str(self):
            return (
                f'postgresql+asyncpg://{self._user}:{self._passwd}@'
                f'{self._host}:{self._port}/{self._db_name}'
            )


    """
    ----------------------------------------------------------------------------
    |                             -<=(Helpers)=>-                              |
    ----------------------------------------------------------------------------
    """


    class AbstractModelHelper(sqlalchemy.orm.DeclarativeBase):
        # Map fields with different names, e.g. { "my_id" : "id" }, where
        # "my_id" is property in our Model and "id" is defined in serialized
        # JSON dictionary.
        _serialize_map = {}
        # These fields do not occur in the serialized JSON dictionary but 
        # rather are defined only by us e.g. [ "id", "date_created" ]
        _except_fields = []

        def from_dict(self, d: json_ser, strict: bool = False):
            """
            Serialize all fields with the same name from `d` dictionary to 
            our defined Model. We can serialize fields with different names 
            using the `self._serialized map`. Fields defined by field names 
            in `self._except_fields` list will be skipped. Serializable 
            Fields MAY NOT start with "_" - if they do, we need to use the 
            _serialize_map property. If `d` contains sub-dictionaries, 
            we can define them using double underscore, 
            e.g. `d.properties.color.main` ~ d__properties__color__main.

            :param d: Dictionary to be serialized.
            :param strict: If True, throw KeyError when field is not found in
                           `d` dictionary.
            """
            for field_name in self.__class__.__dict__.keys():
                if (
                        not field_name.startswith('_')
                        and field_name not in self.__class__._except_fields
                ):
                    if field_name in self.__class__._serialize_map.keys():
                        setattr(
                            self,
                            field_name,
                            d[self.__class__._serialize_map[field_name]]
                        )
                    else:
                        if '__' not in field_name:
                            try:
                                setattr(self, field_name, d[field_name])
                            except KeyError as e:
                                self._log_field_not_found(field_name)
                                if strict:
                                    raise e
                        else:
                            arr = field_name.split('__')
                            f = d
                            try:
                                for nested in arr:
                                    f = f[nested]
                                setattr(self, field_name, f)
                            except KeyError as e:
                                self._log_field_not_found(field_name)
                                if strict:
                                    raise e

        def to_values_dict(self, include: Iterable[str] = ()) -> dict:
            """
            Return dictionary containing all values set on concrete model 
            except those set in `self._except_fields`. Exceptions can be 
            overridden by `include` parameter. Useful for SqlAlchemy VALUES = 
            ...

            :param include: Force to include also values which would be 
            otherwise excluded by `self._except_fields`. :return:
            """

            return {
                c.key: getattr(self, c.key) for c in self.__table__.c
                if (c.key not in self._except_fields or c.key in include)
            }

        def _log_field_not_found(self, field_name: str):
            if AsyncPgWrapper.log:
                AsyncPgWrapper.log.debug(
                    f"SqlAlchemy Model '{self.__class__.__name__}' field "
                    f"'{field_name}' not found."
                )

        def __str__(self):
            s = f'{self.__class__.__name__}:\n'
            for k, v in self.__dict__.items():
                if not k.startswith('_'):
                    s += f'    {k}={v}\n'

            return s


    class PgSessionSingleton:
        _instance = None

        def __init__(self, pg_wrapper: AsyncPgWrapper):
            self._pg_wrapper = pg_wrapper
            PgSessionSingleton._instance = self

        @property
        def pg_wrapper(self):
            return self._pg_wrapper

        @classmethod
        def get_session(cls):
            if cls._instance:
                return cls._instance.pg_wrapper.get_session()
            else:
                raise RuntimeError(
                    "Unable to access singleton instance, "
                    "PgSessionWrapper not initialized."
                )


    class DictKeyMapError(Exception):
        """
        This Booms
        """

        def __init__(
                self, model_cls: type[AbstractModelHelper], id_field_name: str
        ):
            self.model_cls = model_cls
            self.id_field_name = id_field_name

            self.message = (
                f"Unable to map model {self.model_cls} dictionary key to "
                f"{id_field_name}"
            )


    def mapping_result_to_list(
            select_result, model_cls_name: str
    ) -> list[AbstractModelHelper]:
        """
        Create a list from SqlAlchemy transaction result mapping (e.g. select())

        :return: list[type[AbstractModel]]
        """
        ret = []
        for item in select_result.mappings().all():
            ret.append(item[model_cls_name])

        return ret


    def model_list_to_dict(
            models: list[AbstractModelHelper], id_field_name: str
    ) -> dict[Any, AbstractModelHelper]:
        """
        Create dictionary where key is existing field in the Model instance
        defined by id_field_name and value is Model instance itself.

        :param models: List of SqlAlchemy Models.
        :param id_field_name: Name of the field that should be used as a key in
                              newly created dictionary. We should be sure that
                              this field is unique, otherwise we overwrite
                              existing record(s).

        :return: dict[id_field, Model]
        :raise: slack_bot.types.DictKeyMapError: When field named
                `id_field_name` is not found on the model.
        """
        d = {}
        for model in models:
            id_field = getattr(model, id_field_name)
            if not id_field:
                raise DictKeyMapError(model.__class__, id_field_name)
            d[id_field] = model

        return d
