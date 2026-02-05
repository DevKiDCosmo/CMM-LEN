from dataclasses import dataclass


statement = "If k in Z then [n in Z; n disivible k] subset [n in Z; n disivible k^2]"
##################################################
# RPSTN Main Module
# statement: A string containing instances and effects
# strcture: Instances: k...
##################################################

@dataclass
class Entry:
    effect: str # Later List[op|var_ref|expr]
    seq: str # Later List[op|var_ref|expr]
    domain: str # Later List[op|var_ref|expr]

class RPSTNMain:
    def __init__(self, statement):
        self.statement = statement
        self.instances = []
        self.effects = []

    def parse_statement(self):
        buffer: str = ''
        i =0
        while i < len(self.statement):
            char = self.statement[i]
            if char == '[':
                if buffer.strip():
                    self.instances.append(buffer.strip())
                    buffer = ''
                i += 1
                while i < len(self.statement) and self.statement[i] != ']':
                    buffer += self.statement[i]
                    i += 1
                self.effects.append(buffer.strip())
                buffer = ''
            else:
                buffer += char
            i += 1
        self.display_results()
    
    def display_results(self):
        print("Instances:")
        for instance in self.instances:
            print(f"- {instance.strip()}")
        print("Effects:")
        for effect in self.effects:
            print(f"- {effect.strip()}")

if __name__ == "__main__":
    rpstn = RPSTNMain(statement)
    rpstn.parse_statement()