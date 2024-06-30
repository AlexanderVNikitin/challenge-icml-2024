import warnings

import networkx
import torch
import torch_geometric

from modules.transforms.liftings.graph2hypergraph.base import Graph2HypergraphLifting


class ExpanderGraphLifting(Graph2HypergraphLifting):
    r"""Lifts graphs to expander hypergraph.

    Parameters
    ----------
    node_degree : int
        The desired node degree of the expander graph. Must be even.
    **kwargs : optional
        Additional arguments for the class.
    """

    def __init__(self, node_degree: int, **kwargs):
        super().__init__(**kwargs)

        assert node_degree % 2 == 0, "Only even node degree are supported."

        self.node_degree = node_degree

    def lift_topology(self, data: torch_geometric.data.Data) -> dict:
        r"""Lifts the topology of a graph to an expander hypergraph.

        Parameters
        ----------
        data : torch_geometric.data.Data
            The input data to be lifted.

        Returns
        -------
        dict
            The lifted topology.
        """

        expander_graph = random_regular_expander_graph(data.num_nodes, self.node_degree)

        # Catch superfluous warning
        with warnings.catch_warnings():
            warnings.simplefilter(action="ignore", category=FutureWarning)

            incidence_matrix = networkx.incidence_matrix(expander_graph).tocoo()

        coo_indices = torch.stack(
            (
                torch.from_numpy(incidence_matrix.row),
                torch.from_numpy(incidence_matrix.col),
            )
        )
        coo_values = torch.from_numpy(
            incidence_matrix.data.astype("f4")
        )  # 4 byte floating point (single precision)

        incidence_matrix = torch.sparse_coo_tensor(coo_indices, coo_values)

        return {
            "incidence_hyperedges": incidence_matrix,
            "num_hyperedges": incidence_matrix.size(1),
            "x_0": data.x,
        }


"""
Random regular expander graphs are available from networkx >= 3.3 which currently conflicts dependencies. Thus we include the networkx
implementation here. After upgrade to networkx >= 3.3 this should be removed. Upgrading should also get rid of the FutureWarnings.
"""

if "random_regular_expander_graph" in networkx.generators.expanders.__all__:
    from networkx.generators.expanders import random_regular_expander_graph

else:
    nx = networkx

    @nx.utils.decorators.np_random_state("seed")
    # @nx._dispatchable(graphs=None, returns_graph=True)
    def maybe_regular_expander(n, d, *, create_using=None, max_tries=100, seed=None):
        r"""Utility for creating a random regular expander.

        Returns a random $d$-regular graph on $n$ nodes which is an expander
        graph with very good probability.

        Parameters
        ----------
        n : int
          The number of nodes.
        d : int
          The degree of each node.
        create_using : Graph Instance or Constructor
          Indicator of type of graph to return.
          If a Graph-type instance, then clear and use it.
          If a constructor, call it to create an empty graph.
          Use the Graph constructor by default.
        max_tries : int. (default: 100)
          The number of allowed loops when generating each independent cycle
        seed : (default: None)
          Seed used to set random number generation state. See :ref`Randomness<randomness>`.

        Notes
        -----
        The nodes are numbered from $0$ to $n - 1$.

        The graph is generated by taking $d / 2$ random independent cycles.

        Joel Friedman proved that in this model the resulting
        graph is an expander with probability
        $1 - O(n^{-\tau})$ where $\tau = \lceil (\sqrt{d - 1}) / 2 \rceil - 1$. [1]_

        Examples
        --------
        >>> G = nx.maybe_regular_expander(n=200, d=6, seed=8020)

        Returns
        -------
        G : graph
            The constructed undirected graph.

        Raises
        ------
        NetworkXError
            If $d % 2 != 0$ as the degree must be even.
            If $n - 1$ is less than $ 2d $ as the graph is complete at most.
            If max_tries is reached

        See Also
        --------
        is_regular_expander
        random_regular_expander_graph

        References
        ----------
        .. [1] Joel Friedman,
           A Proof of Alon’s Second Eigenvalue Conjecture and Related Problems, 2004
           https://arxiv.org/abs/cs/0405020

        """

        import numpy as np

        if n < 1:
            raise nx.NetworkXError("n must be a positive integer")

        if not (d >= 2):
            raise nx.NetworkXError("d must be greater than or equal to 2")

        if not (d % 2 == 0):
            raise nx.NetworkXError("d must be even")

        if not (n - 1 >= d):
            raise nx.NetworkXError(
                f"Need n-1>= d to have room for {d//2} independent cycles with {n} nodes"
            )

        G = nx.empty_graph(n, create_using)

        if n < 2:
            return G

        cycles = []
        edges = set()

        # Create d / 2 cycles
        for i in range(d // 2):
            iterations = max_tries
            # Make sure the cycles are independent to have a regular graph
            while len(edges) != (i + 1) * n:
                iterations -= 1
                # Faster than random.permutation(n) since there are only
                # (n-1)! distinct cycles against n! permutations of size n
                cycle = seed.permutation(n - 1).tolist()
                cycle.append(n - 1)

                new_edges = {
                    (u, v)
                    for u, v in nx.utils.pairwise(cycle, cyclic=True)
                    if (u, v) not in edges and (v, u) not in edges
                }
                # If the new cycle has no edges in common with previous cycles
                # then add it to the list otherwise try again
                if len(new_edges) == n:
                    cycles.append(cycle)
                    edges.update(new_edges)

                if iterations == 0:
                    raise nx.NetworkXError(
                        "Too many iterations in maybe_regular_expander"
                    )

        G.add_edges_from(edges)

        return G

    @nx.utils.not_implemented_for("directed")
    @nx.utils.not_implemented_for("multigraph")
    # @nx._dispatchable(preserve_edge_attrs={"G": {"weight": 1}})
    def is_regular_expander(G, *, epsilon=0):
        r"""Determines whether the graph G is a regular expander. [1]_

        An expander graph is a sparse graph with strong connectivity properties.

        More precisely, this helper checks whether the graph is a
        regular $(n, d, \lambda)$-expander with $\lambda$ close to
        the Alon-Boppana bound and given by
        $\lambda = 2 \sqrt{d - 1} + \epsilon$. [2]_

        In the case where $\epsilon = 0$ then if the graph successfully passes the test
        it is a Ramanujan graph. [3]_

        A Ramanujan graph has spectral gap almost as large as possible, which makes them
        excellent expanders.

        Parameters
        ----------
        G : NetworkX graph
        epsilon : int, float, default=0

        Returns
        -------
        bool
            Whether the given graph is a regular $(n, d, \lambda)$-expander
            where $\lambda = 2 \sqrt{d - 1} + \epsilon$.

        Examples
        --------
        >>> G = nx.random_regular_expander_graph(20, 4)
        >>> nx.is_regular_expander(G)
        True

        See Also
        --------
        maybe_regular_expander
        random_regular_expander_graph

        References
        ----------
        .. [1] Expander graph, https://en.wikipedia.org/wiki/Expander_graph
        .. [2] Alon-Boppana bound, https://en.wikipedia.org/wiki/Alon%E2%80%93Boppana_bound
        .. [3] Ramanujan graphs, https://en.wikipedia.org/wiki/Ramanujan_graph

        """

        import numpy as np
        from scipy.sparse.linalg import eigsh

        if epsilon < 0:
            raise nx.NetworkXError("epsilon must be non negative")

        if not nx.is_regular(G):
            return False

        _, d = nx.utils.arbitrary_element(G.degree)

        # Catch superfluous warning
        with warnings.catch_warnings():
            warnings.simplefilter(action="ignore", category=FutureWarning)

            A = nx.adjacency_matrix(G, dtype=float)
        lams = eigsh(A, which="LM", k=2, return_eigenvectors=False)

        # lambda2 is the second biggest eigenvalue
        lambda2 = min(lams)

        # Use bool() to convert numpy scalar to Python Boolean
        return bool(abs(lambda2) < 2 ** np.sqrt(d - 1) + epsilon)

    @nx.utils.decorators.np_random_state("seed")
    # @nx._dispatchable(graphs=None, returns_graph=True)
    def random_regular_expander_graph(
        n, d, *, epsilon=0, create_using=None, max_tries=100, seed=None
    ):
        r"""Returns a random regular expander graph on $n$ nodes with degree $d$.

        An expander graph is a sparse graph with strong connectivity properties. [1]_

        More precisely the returned graph is a $(n, d, \lambda)$-expander with
        $\lambda = 2 \sqrt{d - 1} + \epsilon$, close to the Alon-Boppana bound. [2]_

        In the case where $\epsilon = 0$ it returns a Ramanujan graph.
        A Ramanujan graph has spectral gap almost as large as possible,
        which makes them excellent expanders. [3]_

        Parameters
        ----------
        n : int
          The number of nodes.
        d : int
          The degree of each node.
        epsilon : int, float, default=0
        max_tries : int, (default: 100)
          The number of allowed loops, also used in the maybe_regular_expander utility
        seed : (default: None)
          Seed used to set random number generation state. See :ref`Randomness<randomness>`.

        Raises
        ------
        NetworkXError
            If max_tries is reached

        Examples
        --------
        >>> G = nx.random_regular_expander_graph(20, 4)
        >>> nx.is_regular_expander(G)
        True

        Notes
        -----
        This loops over `maybe_regular_expander` and can be slow when
        $n$ is too big or $\epsilon$ too small.

        See Also
        --------
        maybe_regular_expander
        is_regular_expander

        References
        ----------
        .. [1] Expander graph, https://en.wikipedia.org/wiki/Expander_graph
        .. [2] Alon-Boppana bound, https://en.wikipedia.org/wiki/Alon%E2%80%93Boppana_bound
        .. [3] Ramanujan graphs, https://en.wikipedia.org/wiki/Ramanujan_graph

        """
        G = maybe_regular_expander(
            n, d, create_using=create_using, max_tries=max_tries, seed=seed
        )
        iterations = max_tries

        while not is_regular_expander(G, epsilon=epsilon):
            iterations -= 1
            G = maybe_regular_expander(
                n=n, d=d, create_using=create_using, max_tries=max_tries, seed=seed
            )

            if iterations == 0:
                raise nx.NetworkXError(
                    "Too many iterations in random_regular_expander_graph"
                )

        return G
