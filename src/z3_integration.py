"""
Z3 Integration for CMM-LEN
Translates CMM-LEN hierarchies into Z3 constraints for complex logical reasoning
"""

from typing import Dict, List, Set
from z3 import *

from main import (
    Domain,
    EnvironmentObject,
    InstanceObject,
    Model,
    PropertyInstance,
    Rule,
)


class Z3ModelBuilder:
    """Converts CMM-LEN Model to Z3 constraints"""

    def __init__(self, model: Model):
        self.model = model
        self.solver = Solver()
        
        # Z3 Sorts (types)
        self.InstanceSort = DeclareSort("Instance")
        self.DomainSort = DeclareSort("Domain")
        self.EnvironmentSort = DeclareSort("Environment")
        
        # Z3 Functions
        self.in_domain = Function("in_domain", self.InstanceSort, self.DomainSort, BoolSort())
        self.in_env = Function("in_env", self.InstanceSort, self.EnvironmentSort, BoolSort())
        self.related = Function("related", self.InstanceSort, self.InstanceSort, BoolSort())
        self.has_property = Function("has_property", self.InstanceSort, StringSort(), StringSort(), BoolSort())
        self.parent_of = Function("parent_of", self.InstanceSort, self.InstanceSort, BoolSort())
        
        # Mappings
        self.instance_consts: Dict[str, ExprRef] = {}
        self.domain_consts: Dict[str, ExprRef] = {}
        self.env_consts: Dict[str, ExprRef] = {}
        
    def build(self) -> Solver:
        """Build Z3 solver with all constraints"""
        self._create_constants()
        self._add_environment_constraints()
        self._add_domain_constraints()
        self._add_relationship_constraints()
        self._add_property_constraints()
        self._add_hierarchy_constraints()
        return self.solver
    
    def _create_constants(self):
        """Create Z3 constants for all objects"""
        for env in self.model.environments:
            self.env_consts[env.id] = Const(f"env_{env.name}", self.EnvironmentSort)
        
        for inst in self.model.instances:
            self.instance_consts[inst.id] = Const(f"inst_{inst.name}_{inst.id[:8]}", self.InstanceSort)
        
        for dom in self.model.domains:
            self.domain_consts[dom.id] = Const(f"dom_{dom.name}", self.DomainSort)
    
    def _add_environment_constraints(self):
        """Add constraints for environment membership"""
        for inst in self.model.instances:
            inst_const = self.instance_consts[inst.id]
            env_const = self.env_consts[inst.env.id]
            self.solver.add(self.in_env(inst_const, env_const))
    
    def _add_domain_constraints(self):
        """Add constraints for domain membership"""
        for dom in self.model.domains:
            dom_const = self.domain_consts[dom.id]
            for inst in dom.instances:
                inst_const = self.instance_consts[inst.id]
                self.solver.add(self.in_domain(inst_const, dom_const))
    
    def _add_relationship_constraints(self):
        """Add constraints for instance relationships"""
        for inst in self.model.instances:
            inst_const = self.instance_consts[inst.id]
            for related_inst in inst.relationship:
                related_const = self.instance_consts[related_inst.id]
                self.solver.add(self.related(inst_const, related_const))
                # Symmetric relationship
                self.solver.add(self.related(related_const, inst_const))
    
    def _add_property_constraints(self):
        """Add constraints for property values"""
        for prop in self.model.properties:
            inst_const = self.instance_consts[prop.instance.id]
            if isinstance(prop.value, str):
                self.solver.add(self.has_property(inst_const, StringVal(prop.key), StringVal(prop.value)))
    
    def _add_hierarchy_constraints(self):
        """Add constraints for parent-child relationships"""
        for inst in self.model.instances:
            if inst.parent:
                inst_const = self.instance_consts[inst.id]
                parent_const = self.instance_consts[inst.parent.id]
                self.solver.add(self.parent_of(parent_const, inst_const))
    
    def query_instances_in_domain(self, domain_name: str) -> List[InstanceObject]:
        """Query: Find all instances in a specific domain"""
        results = []
        dom = next((d for d in self.model.domains if d.name == domain_name), None)
        if not dom:
            return results
        
        dom_const = self.domain_consts[dom.id]
        
        for inst in self.model.instances:
            inst_const = self.instance_consts[inst.id]
            # Check if constraint is satisfiable
            self.solver.push()
            self.solver.add(self.in_domain(inst_const, dom_const))
            if self.solver.check() == sat:
                results.append(inst)
            self.solver.pop()
        
        return results
    
    def query_related_instances(self, instance_name: str) -> List[InstanceObject]:
        """Query: Find all instances related to a given instance"""
        results = []
        target = next((i for i in self.model.instances if i.name == instance_name), None)
        if not target:
            return results
        
        target_const = self.instance_consts[target.id]
        
        for inst in self.model.instances:
            if inst.id == target.id:
                continue
            inst_const = self.instance_consts[inst.id]
            self.solver.push()
            self.solver.add(self.related(target_const, inst_const))
            if self.solver.check() == sat:
                results.append(inst)
            self.solver.pop()
        
        return results
    
    def verify_axiom(self, axiom_func) -> bool:
        """Verify if an axiom holds in the model"""
        self.solver.push()
        try:
            # Add negation of axiom
            self.solver.add(Not(axiom_func()))
            result = self.solver.check()
            # If unsat, axiom is valid (holds in all cases)
            return result == unsat
        finally:
            self.solver.pop()
    
    def find_inconsistencies(self) -> List[str]:
        """Find logical inconsistencies in the model"""
        inconsistencies = []
        
        # Check for circular parent relationships
        for inst in self.model.instances:
            if inst.parent:
                inst_const = self.instance_consts[inst.id]
                parent_const = self.instance_consts[inst.parent.id]
                
                self.solver.push()
                # Check if instance can be its own ancestor
                self.solver.add(self.parent_of(inst_const, parent_const))
                self.solver.add(self.parent_of(parent_const, inst_const))
                if self.solver.check() == sat:
                    inconsistencies.append(f"Circular parent relationship detected: {inst.name}")
                self.solver.pop()
        
        return inconsistencies
    
    def complex_query(self, constraints: List) -> bool:
        """Execute a complex query with custom Z3 constraints"""
        self.solver.push()
        for constraint in constraints:
            self.solver.add(constraint)
        result = self.solver.check()
        self.solver.pop()
        return result == sat
    
    def prove_transitive_inheritance(self, child_name: str, ancestor_name: str) -> dict:
        """Prove that child inherits from ancestor through parent chain"""
        child = next((i for i in self.model.instances if i.name == child_name), None)
        ancestor = next((i for i in self.model.instances if i.name == ancestor_name), None)
        
        if not child or not ancestor:
            return {"valid": False, "reason": "Instance not found"}
        
        # Build transitive closure
        chain = []
        current = child
        visited = set()
        
        while current:
            if current.id in visited:
                return {"valid": False, "reason": "Circular inheritance detected"}
            visited.add(current.id)
            chain.append(current.name)
            
            if current.name == ancestor_name:
                return {
                    "valid": True,
                    "chain": chain,
                    "proof": f"{' → '.join(chain)}"
                }
            
            current = current.parent
        
        return {"valid": False, "reason": "No inheritance path found"}
    
    def prove_disjoint_domains(self, domain1_name: str, domain2_name: str) -> dict:
        """Prove that two domains have no common instances"""
        dom1 = next((d for d in self.model.domains if d.name == domain1_name), None)
        dom2 = next((d for d in self.model.domains if d.name == domain2_name), None)
        
        if not dom1 or not dom2:
            return {"valid": False, "reason": "Domain not found"}
        
        instances1 = set(i.id for i in dom1.instances)
        instances2 = set(i.id for i in dom2.instances)
        intersection = instances1 & instances2
        
        if intersection:
            common = [i.name for i in self.model.instances if i.id in intersection]
            return {
                "valid": False,
                "reason": f"Domains share instances: {', '.join(common)}"
            }
        
        return {
            "valid": True,
            "proof": f"Domains {domain1_name} and {domain2_name} are disjoint",
            "dom1_size": len(instances1),
            "dom2_size": len(instances2)
        }
    
    def prove_property_propagation(self, instance_name: str, property_key: str, expected_value: str) -> dict:
        """Prove that instance has property through inheritance"""
        inst = next((i for i in self.model.instances if i.name == instance_name), None)
        if not inst:
            return {"valid": False, "reason": "Instance not found"}
        
        # Check direct properties
        for prop in self.model.properties:
            if prop.instance.id == inst.id and prop.key == property_key:
                if prop.value == expected_value:
                    return {
                        "valid": True,
                        "source": "direct",
                        "proof": f"{instance_name}.{property_key} = {prop.value}"
                    }
        
        # Check inherited properties
        current = inst.parent
        chain = [inst.name]
        
        while current:
            chain.append(current.name)
            for prop in self.model.properties:
                if prop.instance.id == current.id and prop.key == property_key:
                    if prop.value == expected_value:
                        return {
                            "valid": True,
                            "source": "inherited",
                            "chain": chain,
                            "proof": f"{instance_name} inherits {property_key}={expected_value} from {current.name} via {' → '.join(chain)}"
                        }
            current = current.parent
        
        return {"valid": False, "reason": f"Property {property_key}={expected_value} not found"}
    
    def assert_no_cycles(self) -> dict:
        """Assert that there are no cycles in parent-child relationships"""
        for inst in self.model.instances:
            visited = set()
            current = inst
            
            while current:
                if current.id in visited:
                    return {
                        "valid": False,
                        "reason": f"Cycle detected at {current.name}"
                    }
                visited.add(current.id)
                current = current.parent
        
        return {
            "valid": True,
            "proof": "No cycles detected in parent chain"
        }


def example_z3_usage():
    """Example usage of Z3 integration"""
    from main import Model
    
    # Assume model is loaded from parse.py
    model = Model()
    
    # Build Z3 model
    z3_builder = Z3ModelBuilder(model)
    solver = z3_builder.build()
    
    print("=== Z3 Integration Example ===")
    print(f"Solver has {len(solver.assertions())} assertions")
    
    # Query instances in domain
    security_instances = z3_builder.query_instances_in_domain("Security")
    print(f"\nInstances in Security domain: {[i.name for i in security_instances]}")
    
    # Find inconsistencies
    inconsistencies = z3_builder.find_inconsistencies()
    if inconsistencies:
        print(f"\nInconsistencies found: {inconsistencies}")
    else:
        print("\nNo inconsistencies found")
    
    # Complex query example
    # "Find instances that are in Security domain AND have status='active'"
    if model.domains:
        dom = next((d for d in model.domains if d.name == "Security"), None)
        if dom and dom.instances:
            inst = dom.instances[0]
            inst_const = z3_builder.instance_consts[inst.id]
            dom_const = z3_builder.domain_consts[dom.id]
            
            constraints = [
                z3_builder.in_domain(inst_const, dom_const),
                z3_builder.has_property(inst_const, StringVal("status"), StringVal("active"))
            ]
            
            result = z3_builder.complex_query(constraints)
            print(f"\nComplex query result: {result}")


if __name__ == "__main__":
    example_z3_usage()
