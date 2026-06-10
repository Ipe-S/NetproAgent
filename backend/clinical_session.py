from typing import Dict

SPECIALISTS = ("to", "psicologia", "neurologia")


class ClinicalSession:
    def __init__(self):
        self._inputs: Dict[str, str] = {}

    def set_input(self, specialist: str, text: str):
        self._inputs[specialist] = text.strip()

    def get_all(self) -> Dict[str, str]:
        return dict(self._inputs)

    def status(self) -> Dict[str, bool]:
        return {s: s in self._inputs for s in SPECIALISTS}

    def is_complete(self) -> bool:
        return all(s in self._inputs for s in SPECIALISTS)

    def clear(self):
        self._inputs.clear()


clinical_session = ClinicalSession()
