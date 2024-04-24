# import copy
import os

import networkx as nx
import numpy as np
import torch
import torch_geometric
from omegaconf import DictConfig

from modules.io.load.loader import AbstractLoader
from modules.io.load.preprocessor import Preprocessor
from modules.io.load.split_utils import (
    assing_train_val_test_mask_to_graphs,
    load_graph_cocitation_split,
    load_graph_tudataset_split,
    load_split,
)
from modules.io.load.utils import (
    load_cell_complex_dataset,
    load_hypergraph_pickle_dataset,
    load_simplicial_dataset,
)


class CellComplexLoader(AbstractLoader):
    r"""Loader for cell complex datasets.

    Parameters
    ----------
    parameters : DictConfig
        Configuration parameters.
    """

    def __init__(self, parameters: DictConfig):
        super().__init__(parameters)
        self.parameters = parameters

    def load(
        self,
    ) -> torch_geometric.data.Dataset:
        r"""Load cell complex dataset.

        Parameters
        ----------
        None

        Returns
        -------
        torch_geometric.data.Dataset
            torch_geometric.data.Dataset object containing the loaded data.
        """
        dataset = load_cell_complex_dataset(self.parameters)
        return dataset


class SimplicialLoader(AbstractLoader):
    r"""Loader for simplicial datasets.

    Parameters
    ----------
    parameters : DictConfig
        Configuration parameters.
    """

    def __init__(self, parameters: DictConfig):
        super().__init__(parameters)
        self.parameters = parameters

    def load(
        self,
    ) -> torch_geometric.data.Dataset:
        r"""Load simplicial dataset.

        Parameters
        ----------
        None

        Returns
        -------
        torch_geometric.data.Dataset
            torch_geometric.data.Dataset object containing the loaded data.
        """
        dataset = load_simplicial_dataset(self.parameters)
        return dataset


class HypergraphLoader(AbstractLoader):
    r"""Loader for hypergraph datasets.

    Parameters
    ----------
    parameters : DictConfig
        Configuration parameters.
    """

    def __init__(self, parameters: DictConfig, transforms=None):
        super().__init__(parameters)
        self.parameters = parameters
        self.transforms_config = transforms

    def load(
        self,
    ) -> torch_geometric.data.Dataset:
        r"""Load hypergraph dataset.

        Parameters
        ----------
        None

        Returns
        -------
        torch_geometric.data.Dataset
            torch_geometric.data.Dataset object containing the loaded data.
        """
        data = load_hypergraph_pickle_dataset(self.parameters)
        dataset = load_split(data, self.parameters)
        return dataset


class GraphLoader(AbstractLoader):
    r"""Loader for graph datasets.

    Parameters
    ----------
    parameters : DictConfig
        Configuration parameters.
    """

    def __init__(self, parameters: DictConfig, transforms=None):
        super().__init__(parameters)
        self.parameters = parameters
        # Still not instantiated
        self.transforms_config = transforms

    def load(self) -> torch_geometric.data.Dataset:
        r"""Load graph dataset.

        Parameters
        ----------
        None

        Returns
        -------
        torch_geometric.data.Dataset
            torch_geometric.data.Dataset object containing the loaded data.
        """
        data_dir = os.path.join(
            self.parameters["data_dir"], self.parameters["data_name"]
        )
        if (
            self.parameters.data_name.lower() in ["cora", "citeseer", "pubmed"]
            and self.parameters.data_type == "cocitation"
        ):
            dataset = torch_geometric.datasets.Planetoid(
                root=self.parameters["data_dir"],
                name=self.parameters["data_name"],
            )
            if self.transforms_config is not None:
                dataset = Preprocessor(data_dir, dataset, self.transforms_config)

            dataset = load_graph_cocitation_split(dataset, self.parameters)

        elif self.parameters.data_name in [
            "MUTAG",
            "ENZYMES",
            "PROTEINS",
            "COLLAB",
            "IMDB-BINARY",
            "IMDB-MULTI",
            "REDDIT-BINARY",
            "NCI1",
            "NCI109",
        ]:
            dataset = torch_geometric.datasets.TUDataset(
                root=self.parameters["data_dir"],
                name=self.parameters["data_name"],
                use_node_attr=False,
            )
            if self.transforms_config is not None:
                dataset = Preprocessor(data_dir, dataset, self.transforms_config)
            dataset = load_graph_tudataset_split(dataset, self.parameters)

        elif self.parameters.data_name in ["ZINC"]:
            datasets = []
            for split in ["train", "val", "test"]:
                datasets.append(
                    torch_geometric.datasets.ZINC(
                        root=self.parameters["data_dir"],
                        subset=True,
                        split=split,
                    )
                )

            assert self.parameters.split_type == "fixed"
            # The splits are predefined
            # Extract and prepare split_idx
            split_idx = {"train": np.arange(len(datasets[0]))}

            split_idx["valid"] = np.arange(
                len(datasets[0]), len(datasets[0]) + len(datasets[1])
            )

            split_idx["test"] = np.arange(
                len(datasets[0]) + len(datasets[1]),
                len(datasets[0]) + len(datasets[1]) + len(datasets[2]),
            )

            # Join dataset to process it
            joined_dataset = datasets[0] + datasets[1] + datasets[2]

            if self.transforms_config is not None:
                joined_dataset = Preprocessor(
                    data_dir,
                    joined_dataset,
                    self.transforms_config,
                )

            # Split back the into train/val/test datasets
            dataset = assing_train_val_test_mask_to_graphs(joined_dataset, split_idx)

        elif self.parameters.data_name in ["AQSOL"]:
            datasets = []
            for split in ["train", "val", "test"]:
                datasets.append(
                    torch_geometric.datasets.AQSOL(
                        root=self.parameters["data_dir"],
                        split=split,
                    )
                )
            # The splits are predefined
            # Extract and prepare split_idx
            split_idx = {"train": np.arange(len(datasets[0]))}

            split_idx["valid"] = np.arange(
                len(datasets[0]), len(datasets[0]) + len(datasets[1])
            )

            split_idx["test"] = np.arange(
                len(datasets[0]) + len(datasets[1]),
                len(datasets[0]) + len(datasets[1]) + len(datasets[2]),
            )

            # Join dataset to process it
            joined_dataset = datasets[0] + datasets[1] + datasets[2]

            if self.transforms_config is not None:
                joined_dataset = Preprocessor(
                    data_dir,
                    joined_dataset,
                    self.transforms_config,
                )

            # Split back the into train/val/test datasets
            dataset = assing_train_val_test_mask_to_graphs(joined_dataset, split_idx)
        
        elif self.parameters.data_name in ["manual"]:
            dataset = ManualGraphLoader(self.parameters, self.transforms_config).load()
         
        else:
            raise NotImplementedError(
                f"Dataset {self.parameters.data_name} not implemented"
            )

        return dataset

class ManualGraphLoader(AbstractLoader):
    r"""Loader for manual graph datasets.

    Parameters
    ----------
    parameters : DictConfig
        Configuration parameters.
    """

    def __init__(self, parameters: DictConfig, transforms=None):
        super().__init__(parameters)
        self.parameters = parameters
        # Still not instantiated
        self.transforms_config = transforms

    def load(self) -> torch_geometric.data.Dataset:
        r"""Load manual graph dataset.

        Parameters
        ----------
        None

        Returns
        -------
        torch_geometric.data.Dataset
            torch_geometric.data.Dataset object containing the loaded data.
        """

        def manual_simple_graph():
            """Create a manual graph for testing purposes."""
            # Define the vertices (just 8 vertices)
            vertices = [i for i in range(8)]
            y = [0, 1, 1, 1, 0, 0, 0, 0]
            # Define the edges
            edges = [
                [0, 1],
                [0, 2],
                [0, 4],
                [1, 2],
                [2, 3],
                [5, 2],
                [5, 6],
                [6, 3],
                [5, 7],
                [2, 7],
                [0, 7],
            ]

            # Define the tetrahedrons
            tetrahedrons = [[0, 1, 2, 4]]

            # Add tetrahedrons
            for tetrahedron in tetrahedrons:
                for i in range(len(tetrahedron)):
                    for j in range(i + 1, len(tetrahedron)):
                        edges.append([tetrahedron[i], tetrahedron[j]])

            # Create a graph
            G = nx.Graph()

            # Add vertices
            G.add_nodes_from(vertices)

            # Add edges
            G.add_edges_from(edges)
            G.to_undirected()
            edge_list = torch.Tensor(list(G.edges())).T.long()

            # Generate feature from 0 to 9
            x = torch.tensor([1, 5, 10, 50, 100, 500, 1000, 5000]).unsqueeze(1).float()

            data = torch_geometric.data.Data(
                x=x,
                edge_index=edge_list,
                num_nodes=len(vertices),
                y=torch.tensor(y),
            )
            return data
        data = manual_simple_graph()

        if self.transforms_config is not None:
            data_dir = os.path.join(
                self.parameters["data_dir"], self.parameters["data_name"]
            )
            processor_dataset = Preprocessor(data_dir, data, self.transforms_config)
        return processor_dataset

