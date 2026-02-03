# Example

Given: $\text{If}\space k ∈ \mathbb{Z}, \text{then}\space\{n ∈ \mathbb{Z} : n|k\}⊆\{n ∈ \mathbb{Z} : n|k^2\}$

## Proof
Suppose $k ∈\mathbb{Z}$ and let $K= \{n ∈ \mathbb{Z} : n|k\}$ and $S= \{n ∈\mathbb{Z} : n|k2\}$. Let
$x ∈K$ so that $x|k$. We can write $k= ax$ for some $a ∈\mathbb{Z}$. Then
$k^2 = (ax)^2 = x(a^2x)$ so $x|k^2$. Thus, $x ∈S$. Since any element $x$ in $K$ is
also in $S$, we know that every element $x$ in $K$ is also in $S$, thus $K ⊆S$.

## How will CMM-LEN work

### Initialize the Model

> [!NOTE]
> L-Model
> A CMM-LEN Model aka L-Model will contain all nessecary information about domains, groups, instances etc. Through complex relationships and intersection environments, logical correlation. Coherence can be maintained.

```len
MODEL model
ENV Proof

DOMAIN Z IN Proof
```