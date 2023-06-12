from asyncio import Lock
from typing import TypeVar, Generic

_KT = TypeVar("_KT")
_VT = TypeVar("_VT")


class ConcurrentMap(Generic[_KT, _VT]):
    def __init__(self) -> None:
        self._lock = Lock()
        self._store: dict[_KT, _VT] = {}

    async def put(self, key: _KT, value: _VT) -> None:
        try:
            await self._lock.acquire()
            self._store[key] = value
        finally:
            self._lock.release()

    async def remove(self, key: _KT) -> None:
        try:
            await self._lock.acquire()
            if self.contains(key):
                del self._store[key]
        finally:
            self._lock.release()

    def get(self, key: _KT) -> _VT | None:
        return self._store.get(key)

    def contains(self, key: _KT) -> bool:
        return key in self._store
