# CMM-LEN Logic Evaluation Network

This is a integration for Z3 from MS. Through more complex data structural integrety more and complex operation can be performed by the actoring agent.


## Example

### Scenario: Fruit Inventory

We have one Environment called "World" containing two types of fruit instances:

- **Apples**: We have 5 apples and all of them are red
- **Pears**: We have 3 pears - 2 are green and 1 is yellow
 - **Basket**: A container instance used to demonstrate instance-to-instance relationships

### Object Structure

```
World (Environment)
├── Apple (Instance)
│   ├── count = 5
│   └── color = red
│   └── container = Basket (Instance)
└── Pear (Instance)
    ├── count = 3
    ├── Pear 1 (Subgroup)
    │   ├── count = 2
    │   └── color = green
    └── Pear 2 (Subgroup) = 1
        ├── = 2
        └── color = yellow

Relationships
- Apple ↔ Pear
```

### Explanation

**Environment "World"**: This is the top-level container that groups all fruit-related objects under a single logical scope.

**Instance "Apple"**: Represents the apple entity within the World environment. When created, it automatically links itself to the World environment. The Apple instance has two properties:
- Property `count` with value `5` - indicating there are 5 apples
- Property `color` with value `red` - indicating all apples are red

**Instance "Pear"**: Represents the pear entity within the World environment. It automatically links itself to the World environment. The Pear instance has a total `count = 3` and is shown with two subgroups to reflect the color split:
- **Pear 1 (Subgroup)**: `count = 2`, `color = green`
- **Pear 2 (Subgroup)**: `count = 1`, `color = yellow`

This subgroup view keeps the Pears under one instance while still expressing that the 3 pears are divided by color.

**Instance "Basket"**: Demonstrates that an instance can be used as a property value of another instance. Here, Apple has the property `container = Basket`.

**Relationships**: Instances can also have explicit relationships with each other (e.g., `Apple ↔ Pear`) to represent semantic links beyond properties.

### Key Insights

The Pear instance demonstrates how related but distinct objects can be grouped together within the same scope. Although the 2 green pears and 1 yellow pear are separate items, they all belong to the same Pear instance because they share the same meaning/category within the World environment.

Each object (Environment, Instance, and Property) has a unique ID for tracking and retrieval, enabling relationship management and data consistency.

### Logic and Evaluation

How should an AI

## Difference between Subgroups and Inherite Instances
Subgroups. Same Instances. Like dogs from different races
Inherite Instances in a Instance. Like a apple in a basket

# Relationship
