from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DatasetBundle:
    dataset_name: str
    orders: pd.DataFrame
    drugs: pd.DataFrame
    orgs: pd.DataFrame
    product_line_mapping: pd.DataFrame


class BaseSourceAdapter(ABC):
    @abstractmethod
    def load_orders(self) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def load_drugs(self) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def load_orgs(self) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def load_product_line_mapping(self) -> pd.DataFrame:
        raise NotImplementedError

    def load_dataset(self) -> DatasetBundle:
        return DatasetBundle(
            dataset_name=self.dataset_name,
            orders=self.load_orders(),
            drugs=self.load_drugs(),
            orgs=self.load_orgs(),
            product_line_mapping=self.load_product_line_mapping(),
        )

    @property
    @abstractmethod
    def dataset_name(self) -> str:
        raise NotImplementedError
