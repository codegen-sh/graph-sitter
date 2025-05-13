from graph_sitter.extensions.swebench.enums import SWEBenchDataset
from graph_sitter.extensions.swebench.enums import SWEBenchLiteSubset


DATASET_DICT = {
    "lite": SWEBenchDataset.LITE,
    "full": SWEBenchDataset.FULL,
    "verified": SWEBenchDataset.VERIFIED,
    "lite_small": SWEBenchLiteSubset.LITE_SMALL,
    "lite_medium": SWEBenchLiteSubset.LITE_MEDIUM,
    "lite_large": SWEBenchLiteSubset.LITE_LARGE,
}
