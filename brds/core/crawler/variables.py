from typing import Any, Dict, Optional, Union


class VariableHolder:
    def __init__(self: "VariableHolder", variables: Optional[Dict[str, Any]] = None) -> None:
        if variables is None:
            variables = {}
        self.variables = variables

    def __getitem__(self: "VariableHolder", key: str) -> Any:
        return self.variables[key]

    def __setitem__(self: "VariableHolder", key: str, value: Any) -> None:
        self.variables[key] = value

    def extend(self: "VariableHolder", other: Union["VariableHolder", Dict[str, Any]]) -> Any:
        if isinstance(other, VariableHolder):
            self.variables.update(other.variables)
        else:
            self.variables.update(other)
