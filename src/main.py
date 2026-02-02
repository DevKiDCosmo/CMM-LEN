from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

RegisterItem = Union[
    "EnvironmentObject",
    "InstanceObject",
    "SubGroupInstance",
    "PropertyInstance",
    "Domain",
]

_current_model: Optional["Model"] = None


def set_current_model(model: "Model") -> None:
    global _current_model
    if _current_model is not None:
        raise RuntimeError("Only one Model instance is allowed.")
    _current_model = model


def get_current_model() -> "Model":
    if _current_model is None:
        raise RuntimeError("Model not initialized. Create Model() before creating objects.")
    return _current_model


@dataclass
class Register:
    by_id: Dict[str, RegisterItem] = field(default_factory=dict)

    def register(self, item: RegisterItem) -> None:
        if item.id in self.by_id:
            raise ValueError(f"Duplicate id in register: {item.id}")
        self.by_id[item.id] = item

    def get(self, item_id: str) -> RegisterItem:
        return self.by_id[item_id]

@dataclass
class EnvironmentObject:
    id: str
    name: str
    instances: List[uuid.UUID]
    register: Register
    domains: list[Domain]

    def __init__(self, name: str):
        self.id = "env_" + uuid.uuid4().hex
        self.name = name
        self.instances = []
        self.domains = []
        model = get_current_model()
        self.register = model.register
        self.register.register(self)
        model.environments.append(self)

    def __repr__(self):
        return f"EnvironmentObject(id={self.id}, name={self.name})"

    def link(self, uuid):
        if uuid not in self.instances:
            self.instances.append(uuid)
        else:
            raise ValueError("UUID already linked in instances")

    def unlink(self, uuid):
        if uuid in self.instances:
            self.instances.remove(uuid)
        else: 
            raise ValueError("UUID not found in instances")

    def identifier(self):
        return self.id

@dataclass
class InstanceObject:
    id: str
    name: str
    env: EnvironmentObject
    properties: List[str]
    register: Register
    relationship: List[InstanceObject]
    instances: List[InstanceObject]
    parent: Optional[InstanceObject]

    def __init__(self, name: str, env: EnvironmentObject, parent: Optional[InstanceObject] = None):
        self.id = "inst_" + uuid.uuid4().hex
        self.name = name
        self.env = env
        self.properties = []
        self.relationship = []
        self.instances = []
        self.parent = parent
        model = get_current_model()
        self.register = model.register
        self.register.register(self)
        model.instances.append(self)

        # Link this instance to the environment
        self.env.link(self.id)

        if self.parent is not None:
            self.parent.link_instance(self)

    def link(self, prop_id: str):
        if prop_id not in self.properties:
            self.properties.append(prop_id)
        else:
            raise ValueError("Property already linked in instance")

    def unlink(self, prop_id: str):
        if prop_id in self.properties:
            self.properties.remove(prop_id)
        else:
            raise ValueError("Property not found in instance")

    def link_instance(self, inst: InstanceObject) -> None:
        if inst not in self.instances:
            self.instances.append(inst)
        else:
            raise ValueError("Instance already linked in instance")

    def unlink_instance(self, inst: InstanceObject) -> None:
        if inst in self.instances:
            self.instances.remove(inst)
        else:
            raise ValueError("Instance not found in instance")
    
    def identifier(self):
        return self.id

    def relationship_to(self, other: InstanceObject) -> None:
        # Check if same environment
        if self.env != other.env:
            raise ValueError("Instances must be in the same environment to form a relationship")

        if other not in self.relationship:
            self.relationship.append(other)
        if self not in other.relationship:
            other.relationship.append(self)

    def destroy_relationship(self, other: InstanceObject) -> None:
        if other in self.relationship:
            self.relationship.remove(other)
        if self in other.relationship:
            other.relationship.remove(self)

@dataclass
class SubGroupInstance:
    id: str
    name: str
    instances: List[PropertyInstance]
    register: Register

    def __init__(self, name: str):
        self.id = "subg_" + uuid.uuid4().hex
        self.name = name
        self.instances = []
        model = get_current_model()
        self.register = model.register
        self.register.register(self)
        model.subgroups.append(self)

    def link(self, instance: PropertyInstance):
        if instance not in self.instances:
            self.instances.append(instance)
        else:
            raise ValueError("Instance already linked in subgroup")

    def unlink(self, instance: PropertyInstance):
        if instance in self.instances:
            self.instances.remove(instance)
        else:
            raise ValueError("Instance not found in subgroup")

    def identifier(self):
        return self.id

@dataclass
class PropertyInstance:
    id: str
    key: str
    value: Union[str, int, float, bool, InstanceObject]
    instance: InstanceObject
    register: Register
    calculated: bool = False  # Flag if value was calculated

    def __init__(self, key: str, value: Union[str, int, float, bool, InstanceObject], instance: InstanceObject, calculated: bool = False):
        self.id = "prop_" + uuid.uuid4().hex
        self.key = key
        self.value = value
        self.instance = instance
        self.calculated = calculated
        model = get_current_model()
        self.register = model.register
        self.register.register(self)
        model.properties.append(self)

        # Link this property to the instance
        self.instance.link(self.id)


@dataclass
class Domain:
    id: str
    name: str
    env: EnvironmentObject
    instances: list[InstanceObject]
    register: Register

    def __init__(self, name: str, env: EnvironmentObject):
        self.id = "dom_" + uuid.uuid4().hex
        self.name = name
        self.env = env
        self.instances = []
        model = get_current_model()
        self.register = model.register
        self.register.register(self)
        model.domains.append(self)
        self.env.domains.append(self)

    def link(self, inst: InstanceObject) -> None:
        if inst not in self.instances:
            self.instances.append(inst)
        else:
            raise ValueError("Instance already linked in domain")


@dataclass
class ModelRelationship:
    left: InstanceObject
    right: InstanceObject


class Query:
    def __init__(self, description: str):
        self.description = description
        self.results: list[InstanceObject | Domain] = []

    def execute(self, model: "Model") -> list:
        return self.results


class Rule:
    def __init__(self, name: str, condition: callable, consequence: callable, axiom: bool = True):
        self.name = name
        self.condition = condition
        self.consequence = consequence
        self.axiom = axiom
        self.triggered_count = 0
        self.applied_to: set[str] = set()  # Track which objects this rule was applied to

    def check_and_apply(self, obj: Union[InstanceObject, Domain], force: bool = False) -> bool:
        """Check condition and apply consequence if not already applied."""
        obj_id = obj.id
        
        # Skip if already applied to this object (unless forced)
        if not force and obj_id in self.applied_to:
            return False
            
        if self.condition(obj):
            self.consequence(obj)
            self.triggered_count += 1
            self.applied_to.add(obj_id)
            return True
        return False


class InferenceEngine:
    def __init__(self, model: "Model"):
        self.model = model
        self.rules: list[Rule] = []
        self.derived_facts: dict[str, set[str]] = {}  # Changed to set for uniqueness

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)

    def infer(self) -> dict:
        """Run inference engine until no new facts can be derived."""
        results = {"triggered_rules": [], "new_facts": [], "iterations": 0}
        max_iterations = 100
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            triggered_this_round = False

            # Apply rules to all instances
            for inst in self.model.instances:
                for rule in self.rules:
                    if rule.check_and_apply(inst):
                        triggered_this_round = True
                        results["triggered_rules"].append(
                            {"rule": rule.name, "instance": inst.name, "iteration": iteration}
                        )

            # Apply rules to all domains
            for dom in self.model.domains:
                for rule in self.rules:
                    if rule.check_and_apply(dom):
                        triggered_this_round = True
                        results["triggered_rules"].append(
                            {"rule": rule.name, "domain": dom.name, "iteration": iteration}
                        )

            # Stop if no new facts were derived
            if not triggered_this_round:
                results["iterations"] = iteration
                break

        if iteration >= max_iterations:
            results["iterations"] = max_iterations
            results["warning"] = "Reached maximum iterations"

        return results

class Model:
    def __init__(self):
        set_current_model(self)
        self.register = Register()
        self.environments: list[EnvironmentObject] = []
        self.instances: list[InstanceObject] = []
        self.subgroups: list[SubGroupInstance] = []
        self.properties: list[PropertyInstance] = []
        self.domains: list[Domain] = []
        self.model_relationships: list[ModelRelationship] = []
        self.queries: list[Query] = []
        self.rules: list[Rule] = []
        self.inference_engine = InferenceEngine(self)

    def tree(self) -> str:
        lines: list[str] = []

        def add_line(prefix: str, text: str) -> None:
            lines.append(f"{prefix}{text}")

        def disambiguate(names: list[str]) -> dict[str, int]:
            counts: dict[str, int] = {}
            for n in names:
                counts[n] = counts.get(n, 0) + 1
            return counts

        def format_name(name: str, obj_id: str, name_counts: dict[str, int]) -> str:
            if name_counts.get(name, 0) > 1:
                return f"{name} ({obj_id})"
            return name

        def render_instance(inst: InstanceObject, base_prefix: str, is_last: bool, sibling_names: list[str]) -> None:
            inst_name_counts = disambiguate(sibling_names)
            inst_display = format_name(inst.name, inst.id, inst_name_counts)
            inst_label = f"{inst_display} (Instance)"
            if inst.parent is not None:
                inst_label = f"{inst_display} (Instance, child)"

            inst_domains = [d.name for d in inst.env.domains if inst in d.instances]
            if inst_domains:
                inst_label = f"{inst_label}, Domain: {', '.join(inst_domains)}"

            branch = "└── " if is_last else "├── "
            add_line(base_prefix, f"{branch}{inst_label}")

            child_prefix = base_prefix + ("    " if is_last else "│   ")

            inst_properties = [self.register.get(pid) for pid in inst.properties]
            subgroups = [
                sg
                for sg in self.subgroups
                if any(p.instance is inst for p in sg.instances)
            ]

            grouped_prop_ids = {p.id for sg in subgroups for p in sg.instances}
            standalone_props = [p for p in inst_properties if p.id not in grouped_prop_ids]

            prop_name_counts = disambiguate([p.key for p in standalone_props])
            subgroup_name_counts = disambiguate([sg.name for sg in subgroups])
            child_instance_names = [c.name for c in inst.instances]

            child_lines: list[str] = []

            for p in standalone_props:
                prop_key = format_name(p.key, p.id, prop_name_counts)
                if isinstance(p.value, InstanceObject):
                    value_name = p.value.name
                    value_display = format_name(value_name, p.value.id, {value_name: 2})
                    child_lines.append(f"{prop_key} = {value_display} (Instance)")
                else:
                    child_lines.append(f"{prop_key} = {p.value}")

            for sg in subgroups:
                sg_name = format_name(sg.name, sg.id, subgroup_name_counts)
                child_lines.append(f"{sg_name} (Subgroup)")
                for sp in sg.instances:
                    child_lines.append(f"{sg_name}::{sp.key} = {sp.value}")

            if inst.relationship:
                rel_names = [r.name for r in inst.relationship]
                rel_name_counts = disambiguate(rel_names)
                rel_items = [format_name(r.name, r.id, rel_name_counts) for r in inst.relationship]
                child_lines.append(f"relationships = {', '.join(rel_items)}")

            model_rels = [
                rel for rel in self.model_relationships if rel.left is inst or rel.right is inst
            ]
            if model_rels:
                items = []
                for rel in model_rels:
                    other = rel.right if rel.left is inst else rel.left
                    other_name_counts = disambiguate([other.name])
                    other_display = format_name(other.name, other.id, other_name_counts)
                    items.append(f"{other_display} ({other.env.name})")
                child_lines.append(f"model_relationships = {', '.join(items)}")

            for c_idx, child in enumerate(child_lines):
                branch = "└── " if c_idx == len(child_lines) - 1 and not inst.instances else "├── "
                add_line(child_prefix, f"{branch}{child}")

            for idx, child_inst in enumerate(inst.instances):
                render_instance(
                    child_inst,
                    child_prefix,
                    idx == len(inst.instances) - 1,
                    child_instance_names,
                )

        env_name_counts = disambiguate([e.name for e in self.environments])

        for env in self.environments:
            env_display = format_name(env.name, env.id, env_name_counts)
            add_line("", f"{env_display} (Environment)")
            env_instance_ids = env.instances
            env_instances = [self.register.get(iid) for iid in env_instance_ids]
            top_level_instances = [i for i in env_instances if i.parent is None]
            sibling_names = [i.name for i in top_level_instances]
            for i_idx, inst in enumerate(top_level_instances):
                render_instance(inst, "", i_idx == len(top_level_instances) - 1, sibling_names)

        tree_str = "\n".join(lines)
        print(tree_str)
        return tree_str
    
    def relation(self) -> None:
        print("Relationships between Instances:")
        for inst in self.instances:
            if inst.relationship:
                rel_names = [r.name for r in inst.relationship]
                print(f"- {inst.name} {inst.id} is related to: {', '.join(rel_names)}")
        if self.domains:
            print("\nDomain memberships:")
            for dom in self.domains:
                if dom.instances:
                    names = ", ".join(i.name for i in dom.instances)
                    print(f"- {dom.name} ({dom.env.name}): {names}")

            print("\nDomains without instances:")
            for dom in self.domains:
                if not dom.instances:
                    print(f"- {dom.name} ({dom.env.name})")
            
        if self.model_relationships:
            print("\nModelRelationships (cross-environment):")
            for rel in self.model_relationships:
                print(
                    f"- {rel.left.name} ({rel.left.env.name}:{rel.left.id}) ↔ {rel.right.name} ({rel.right.env.name}:{rel.right.id})"
                )
        return None

    def relate_model(self, left: InstanceObject, right: InstanceObject) -> None:
        self.model_relationships.append(ModelRelationship(left=left, right=right))

def test():
    model = Model()
    env = EnvironmentObject(name="World")
    apple = InstanceObject(name="Apple", env=env)
    pear = InstanceObject(name="Pear", env=env)
    basket = InstanceObject(name="Basket", env=env)
    glove_pair = InstanceObject(name="Glove Pair", env=env, parent=basket)

    apple_count = PropertyInstance(key="count", value="5", instance=apple)
    apple_color = PropertyInstance(key="color", value="red", instance=apple)

    pear_count = PropertyInstance(key="count", value="3", instance=pear)

    pear_green = SubGroupInstance(name="Pear 1")
    pear_green_count = PropertyInstance(key="count", value="2", instance=pear)
    pear_green_color = PropertyInstance(key="color", value="green", instance=pear)
    pear_green.link(pear_green_count)
    pear_green.link(pear_green_color)

    pear_yellow = SubGroupInstance(name="Pear 2")
    pear_yellow_count = PropertyInstance(key="count", value="1", instance=pear)
    pear_yellow_color = PropertyInstance(key="color", value="yellow", instance=pear)
    pear_yellow.link(pear_yellow_count)
    pear_yellow.link(pear_yellow_color)

    container = PropertyInstance(key="container", value=basket, instance=apple)
    glove_count = PropertyInstance(key="count", value="3", instance=glove_pair)
    glove_color = PropertyInstance(key="color", value="undefined", instance=glove_pair)
    apple.relationship_to(other=pear)

    #print(env, env.identifier(), env.instances)
    #print(apple, apple.identifier(), apple.properties)
    #print(pear, pear.identifier(), pear.properties)
    #print(apple_count, apple_count.key, apple_count.value)
    #print(apple_color, apple_color.key, apple_color.value)
    #print(pear_count, pear_count.key, pear_count.value)
    #print(pear_green, pear_green.identifier(), [p.id for p in pear_green.instances])
    #print(pear_yellow, pear_yellow.identifier(), [p.id for p in pear_yellow.instances])
   
    model.tree()
    model.relation()

if __name__ == "__main__":
    test()