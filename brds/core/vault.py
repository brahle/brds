from typing import Any as _Any
from typing import Dict as _Dict

from hvac import Client as _Client

from .environment import vault_token as _vault_token


class Vault:
    client = _Client(url="http://localhost:8200", token=_vault_token())

    def secret(self: "Vault", name: str) -> _Dict[str, _Any]:
        ret: _Dict[str, _Any] = self.client.read(f"kv/data/{name}")["data"]["data"]
        return ret
