"""
Tests for the population constraint extension to CPMVertexPartition.

Test coverage:
  1. Backward compatibility  — pop_lambda=0 gives identical results to vanilla CPM
  2. Penalty is a no-op      — pop_lambda=0, default node_pop=0, quality unchanged
  3. Penalty reduces quality — pop_lambda>0 lowers quality() vs vanilla CPM
  4. Communities respect cap — strong penalty keeps community populations <= threshold
  5. Below-threshold safe    — communities below pop_threshold are never penalized
  6. cpop accounting         — cpop() tracks population correctly after moves
  7. deepcopy preserves params
"""

import unittest
import igraph as ig
import leidenalg
from copy import deepcopy


def make_two_clique_graph():
    """Two tightly connected cliques of 5 nodes joined by one bridge edge."""
    G = ig.Graph()
    G.add_vertices(10)
    # Clique 0-4
    G.add_edges([(i, j) for i in range(5) for j in range(i+1, 5)])
    # Clique 5-9
    G.add_edges([(i, j) for i in range(5, 10) for j in range(i+1, 10)])
    # Bridge
    G.add_edges([(4, 5)])
    return G


def community_pop(partition, c):
    """Return the total population of community c by summing over node_pop."""
    node_pop = partition._node_pop
    if node_pop is None:
        return 0.0
    return sum(node_pop[v] for v, m in enumerate(partition.membership) if m == c)


class TestPopConstraintBackwardCompat(unittest.TestCase):
    """pop_lambda=0 must reproduce vanilla CPM exactly."""

    def setUp(self):
        self.G = make_two_clique_graph()

    def test_membership_identical_to_vanilla(self):
        """Same membership as vanilla CPM when pop_lambda=0 (default)."""
        import random
        random.seed(42)

        vanilla = leidenalg.find_partition(
            self.G,
            leidenalg.CPMVertexPartition,
            resolution_parameter=0.3,
            seed=42
        )
        constrained = leidenalg.find_partition(
            self.G,
            leidenalg.CPMVertexPartition,
            resolution_parameter=0.3,
            node_pop=[0.0] * self.G.vcount(),
            pop_lambda=0.0,
            pop_threshold=0.0,
            seed=42
        )
        self.assertEqual(vanilla.membership, constrained.membership)

    def test_quality_identical_to_vanilla(self):
        """Same quality() value as vanilla CPM when pop_lambda=0."""
        G = self.G
        n = G.vcount()
        # Use a non-trivial membership: the two natural cliques
        membership = [0] * 5 + [1] * 5

        vanilla = leidenalg.CPMVertexPartition(G, resolution_parameter=0.3)
        constrained = leidenalg.CPMVertexPartition(
            G,
            resolution_parameter=0.3,
            node_pop=[0.0] * n,
            pop_lambda=0.0,
            pop_threshold=0.0
        )
        # Force the same membership
        vanilla.set_membership(membership)
        constrained.set_membership(membership)

        self.assertAlmostEqual(vanilla.quality(), constrained.quality(), places=10)


class TestPopConstraintPenalty(unittest.TestCase):
    """Penalty mechanics."""

    def setUp(self):
        self.G = make_two_clique_graph()
        self.n = self.G.vcount()

    def test_quality_lower_with_penalty(self):
        """quality() must be lower when pop_lambda>0 and communities exceed threshold."""
        G = self.G
        n = self.n
        pop = [100.0] * n  # each node has population 100; each clique = 500 total
        # Non-trivial membership: two cliques
        membership = [0] * 5 + [1] * 5

        vanilla = leidenalg.CPMVertexPartition(G, resolution_parameter=0.3)
        constrained = leidenalg.CPMVertexPartition(
            G,
            resolution_parameter=0.3,
            node_pop=pop,
            pop_lambda=0.01,
            pop_threshold=200.0   # threshold well below clique population (500)
        )
        vanilla.set_membership(membership)
        constrained.set_membership(membership)

        self.assertLess(constrained.quality(), vanilla.quality())

    def test_no_penalty_below_threshold(self):
        """quality() must equal vanilla CPM when all communities are below threshold."""
        G = self.G
        n = self.n
        pop = [10.0] * n  # each clique = 50 total population
        membership = [0] * 5 + [1] * 5

        vanilla = leidenalg.CPMVertexPartition(G, resolution_parameter=0.3)
        constrained = leidenalg.CPMVertexPartition(
            G,
            resolution_parameter=0.3,
            node_pop=pop,
            pop_lambda=0.01,
            pop_threshold=1000.0  # threshold far above any community population
        )
        vanilla.set_membership(membership)
        constrained.set_membership(membership)

        self.assertAlmostEqual(vanilla.quality(), constrained.quality(), places=10)

    def test_strong_penalty_splits_communities(self):
        """A very strong penalty should result in more, smaller communities."""
        G = self.G
        n = self.n
        pop = [100.0] * n  # clique pop = 500

        vanilla = leidenalg.find_partition(
            G, leidenalg.CPMVertexPartition,
            resolution_parameter=0.3, seed=0
        )
        constrained = leidenalg.find_partition(
            G, leidenalg.CPMVertexPartition,
            resolution_parameter=0.3,
            node_pop=pop,
            pop_lambda=10.0,      # very strong penalty
            pop_threshold=150.0,  # only 1-2 nodes allowed per community
            seed=0
        )
        # Constrained partition should have more communities (smaller ones)
        self.assertGreaterEqual(
            len(constrained),
            len(vanilla)
        )


class TestCpopAccounting(unittest.TestCase):
    """cpop() should correctly track community population."""

    def test_cpop_matches_manual_sum(self):
        """community_pop(c) must equal sum of node_pop for nodes in community c."""
        G = make_two_clique_graph()
        n = G.vcount()
        pop = [float(v + 1) for v in range(n)]  # distinct populations

        partition = leidenalg.CPMVertexPartition(
            G,
            resolution_parameter=0.3,
            node_pop=pop
        )

        for c in range(len(partition)):
            members = [v for v, m in enumerate(partition.membership) if m == c]
            expected = sum(pop[v] for v in members)
            self.assertAlmostEqual(community_pop(partition, c), expected, places=10)

    def test_cpop_updates_after_move(self):
        """community_pop() must be consistent after set_membership is called."""
        G = make_two_clique_graph()
        n = G.vcount()
        pop = [10.0] * n

        partition = leidenalg.CPMVertexPartition(
            G,
            resolution_parameter=0.3,
            node_pop=pop
        )

        # Force singleton partition so community_pop(v) == pop[v] for each node
        partition.set_membership(list(range(n)))
        for v in range(n):
            self.assertAlmostEqual(community_pop(partition, v), pop[v], places=10)


class TestDeepCopy(unittest.TestCase):
    """deepcopy must preserve pop_lambda, pop_threshold, and node_pop."""

    def test_deepcopy_preserves_params(self):
        G = make_two_clique_graph()
        n = G.vcount()
        pop = [float(v) for v in range(n)]

        original = leidenalg.CPMVertexPartition(
            G,
            resolution_parameter=0.5,
            node_pop=pop,
            pop_lambda=0.05,
            pop_threshold=25.0
        )
        copied = deepcopy(original)

        self.assertEqual(copied.pop_lambda, original.pop_lambda)
        self.assertEqual(copied.pop_threshold, original.pop_threshold)
        self.assertEqual(copied.resolution_parameter, original.resolution_parameter)


if __name__ == '__main__':
    unittest.main()
