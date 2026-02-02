# Z3 Integration für CMM-LEN

## Überblick

Die Z3-Integration ermöglicht komplexe logische Berechnungen über CMM-LEN Hierarchien mittels SMT-Solving.

## Installation

```bash
pip install z3-solver
```

## Konzepte

### 1. **Mapping zu Z3**

| CMM-LEN | Z3 |
|---------|-----|
| InstanceObject | `InstanceSort` Konstante |
| Domain | `DomainSort` Konstante |
| Environment | `EnvironmentSort` Konstante |
| Property | `has_property(inst, key, value)` |
| Relationship | `related(inst1, inst2)` |
| Parent-Child | `parent_of(parent, child)` |

### 2. **Z3 Funktionen**

```python
in_domain(Instance, Domain) → Bool
in_env(Instance, Environment) → Bool
related(Instance, Instance) → Bool
has_property(Instance, String, String) → Bool
parent_of(Instance, Instance) → Bool
```

### 3. **Query-Typen**

#### **Domain-basiert**
```python
# Finde alle Instanzen in "Security" Domain
instances = z3_builder.query_instances_in_domain("Security")
```

#### **Relationship-basiert**
```python
# Finde alle Instanzen verbunden mit "Camera"
related = z3_builder.query_related_instances("Camera")
```

#### **Komplexe Constraints**
```python
# Custom Z3 Bedingungen
constraints = [
    in_domain(x, security_domain),
    has_property(x, "status", "active"),
    related(x, y)
]
result = z3_builder.complex_query(constraints)
```

## Verwendung

### Basic Setup

```python
from parse import parse_len
from z3_integration import Z3ModelBuilder

# 1. Lade CMM-LEN Model
model = parse_len("logic.len")

# 2. Erstelle Z3 Builder
z3_builder = Z3ModelBuilder(model)
solver = z3_builder.build()

# 3. Führe Queries aus
results = z3_builder.query_instances_in_domain("Security")
```

### Axiom-Verifizierung

```python
def axiom_all_security_devices_monitored():
    # Alle Instanzen in Security müssen 'recording=yes' haben
    for inst in security_instances:
        inst_const = z3_builder.instance_consts[inst.id]
        dom_const = z3_builder.domain_consts[security_domain.id]
        return Implies(
            z3_builder.in_domain(inst_const, dom_const),
            z3_builder.has_property(inst_const, "recording", "yes")
        )

is_valid = z3_builder.verify_axiom(axiom_all_security_devices_monitored)
print(f"Axiom valid: {is_valid}")
```

### Inkonsistenz-Erkennung

```python
inconsistencies = z3_builder.find_inconsistencies()
# Erkennt:
# - Zirkuläre Parent-Kind-Beziehungen
# - Widersprüchliche Properties
# - Domain-Konflikte
```

## Erweiterte Anwendungen

### 1. **Constraint-basiertes Planen**

```python
# Finde Konfiguration wo alle Geräte "active" sind
for inst in model.instances:
    inst_const = z3_builder.instance_consts[inst.id]
    solver.add(z3_builder.has_property(inst_const, "status", "active"))

if solver.check() == sat:
    m = solver.model()
    # Extrahiere Lösung
```

### 2. **Transitive Beziehungen**

```python
# Definiere transitive Closure für parent_of
def add_transitivity():
    for i1 in instances:
        for i2 in instances:
            for i3 in instances:
                solver.add(Implies(
                    And(parent_of(i1, i2), parent_of(i2, i3)),
                    parent_of(i1, i3)
                ))
```

### 3. **Property-Inferenz**

```python
# Regel: Wenn Instance in "Electronics" → braucht "power" Property
for inst in model.instances:
    inst_const = z3_builder.instance_consts[inst.id]
    electronics_dom = domain_consts["Electronics"]
    
    solver.add(Implies(
        in_domain(inst_const, electronics_dom),
        has_property(inst_const, "power", "required")
    ))
```

## Vorteile

✓ **Automatisches Reasoning** über komplexe Hierarchien  
✓ **Inkonsistenz-Erkennung** in großen Modellen  
✓ **Constraint-Solving** für Planung/Optimierung  
✓ **Axiom-Verifikation** mathematisch beweisbar  
✓ **Skalierbar** für 1000+ Instanzen

## Performance

- **Kleine Modelle** (<100 Instanzen): <1s
- **Mittlere Modelle** (100-1000): 1-10s
- **Große Modelle** (>1000): Kann Minutes dauern, abhängig von Constraint-Komplexität

## Beispiel-Output

```
=== Z3 Integration Example ===
Solver has 47 assertions

Instances in Security domain: ['SecurityCamera', 'SmartLock']

No inconsistencies found

Complex query result: True
```
