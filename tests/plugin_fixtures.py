"""Source fixtures exercise actual imports rather than mocking the loader."""
ENTRY = '''
from .implementation import ExampleFact
PLUGIN = {"name": "example", "version": "1.2.3", "api": 1}
def actions():
    return []
def facts():
    return [ExampleFact()]
'''

IMPLEMENTATION = '''
from etchlib.providers.observations import FactResult, FactState
class ExampleFact:
    name = "example_fact"
    def validate(self, config, context):
        pass
    def gather(self, config, context):
        return FactResult(FactState.VALUE, "from plugin")
'''


def write_plugin(root, entry=ENTRY):
    root.mkdir(parents=True)
    (root / "etch_plugin.py").write_text(entry)
    (root / "implementation.py").write_text(IMPLEMENTATION)
    return root
