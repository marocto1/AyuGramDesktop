from dataclasses import dataclass, field
@dataclass
class ParsedEntity:
    data: object=None
    def to_tlrpc_object(self): return self.data or {}
@dataclass
class ParsedMarkdown:
    text: str
    entities: list=field(default_factory=list)
def parse_markdown(text): return ParsedMarkdown(str(text), [])
