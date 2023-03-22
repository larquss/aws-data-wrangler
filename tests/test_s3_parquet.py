import itertools
import logging
import math
from datetime import datetime

import boto3
import numpy as np
import pandas as pd
import pytest

import awswrangler as wr

from ._utils import ensure_data_types, get_df_list

logging.getLogger("awswrangler").setLevel(logging.DEBUG)


@pytest.mark.parametrize("partition_cols", [None, ["c2"], ["c1", "c2"]])
def test_parquet_metadata_partitions_dataset(path, partition_cols):
    df = pd.DataFrame({"c0": [0, 1, 2], "c1": [3, 4, 5], "c2": [6, 7, 8]})
    paths = wr.s3.to_parquet(df=df, path=path, dataset=True, partition_cols=partition_cols)["paths"]
    wr.s3.wait_objects_exist(paths=paths, use_threads=False)
    columns_types, partitions_types = wr.s3.read_parquet_metadata(path=path, dataset=True)
    partitions_types = partitions_types if partitions_types is not None else {}
    assert len(columns_types) + len(partitions_types) == len(df.columns)
    assert columns_types.get("c0") == "bigint"
    assert (columns_types.get("c1") == "bigint") or (partitions_types.get("c1") == "string")
    assert (columns_types.get("c1") == "bigint") or (partitions_types.get("c1") == "string")


@pytest.mark.parametrize("partition_cols", [None, ["c2"], ["value", "c2"]])
def test_parquet_cast_string_dataset(path, partition_cols):
    df = pd.DataFrame({"id": [1, 2, 3], "value": ["foo", "boo", "bar"], "c2": [4, 5, 6], "c3": [7.0, 8.0, 9.0]})
    paths = wr.s3.to_parquet(
        df, path, dataset=True, partition_cols=partition_cols, dtype={"id": "string", "c3": "string"}
    )["paths"]
    wr.s3.wait_objects_exist(paths)
    df2 = wr.s3.read_parquet(path, dataset=True).sort_values("id", ignore_index=True)
    assert str(df2.id.dtypes) == "string"
    assert str(df2.c3.dtypes) == "string"
    assert df.shape == df2.shape
    for col, row in tuple(itertools.product(df.columns, range(3))):
        assert str(df[col].iloc[row]) == str(df2[col].iloc[row])


@pytest.mark.parametrize("use_threads", [True, False])
def test_read_parquet_filter_partitions(path, use_threads):
    df = pd.DataFrame({"c0": [0, 1, 2], "c1": [0, 1, 2], "c2": [0, 0, 1]})
    paths = wr.s3.to_parquet(df, path, dataset=True, partition_cols=["c1", "c2"], use_threads=use_threads)["paths"]
    wr.s3.wait_objects_exist(paths=paths, use_threads=use_threads)
    df2 = wr.s3.read_parquet(
        path, dataset=True, partition_filter=lambda x: True if x["c1"] == "0" else False, use_threads=use_threads
    )
    assert df2.shape == (1, 3)
    assert df2.c0.iloc[0] == 0
    assert df2.c1.astype(int).iloc[0] == 0
    assert df2.c2.astype(int).iloc[0] == 0
    df2 = wr.s3.read_parquet(
        path,
        dataset=True,
        partition_filter=lambda x: True if x["c1"] == "1" and x["c2"] == "0" else False,
        use_threads=use_threads,
    )
    assert df2.shape == (1, 3)
    assert df2.c0.iloc[0] == 1
    assert df2.c1.astype(int).iloc[0] == 1
    assert df2.c2.astype(int).iloc[0] == 0
    df2 = wr.s3.read_parquet(
        path, dataset=True, partition_filter=lambda x: True if x["c2"] == "0" else False, use_threads=use_threads
    )
    assert df2.shape == (2, 3)
    assert df2.c0.astype(int).sum() == 1
    assert df2.c1.astype(int).sum() == 1
    assert df2.c2.astype(int).sum() == 0


def test_parquet(path):
    df_file = pd.DataFrame({"id": [1, 2, 3]})
    path_file = f"{path}test_parquet_file.parquet"
    df_dataset = pd.DataFrame({"id": [1, 2, 3], "partition": ["A", "A", "B"]})
    df_dataset["partition"] = df_dataset["partition"].astype("category")
    path_dataset = f"{path}test_parquet_dataset"
    with pytest.raises(wr.exceptions.InvalidArgumentCombination):
        wr.s3.to_parquet(df=df_file, path=path_file, mode="append")
    with pytest.raises(wr.exceptions.InvalidCompression):
        wr.s3.to_parquet(df=df_file, path=path_file, compression="WRONG")
    with pytest.raises(wr.exceptions.InvalidArgumentCombination):
        wr.s3.to_parquet(df=df_dataset, path=path_dataset, partition_cols=["col2"])
    with pytest.raises(wr.exceptions.InvalidArgumentCombination):
        wr.s3.to_parquet(df=df_dataset, path=path_dataset, description="foo")
    with pytest.raises(wr.exceptions.InvalidArgumentValue):
        wr.s3.to_parquet(df=df_dataset, path=path_dataset, partition_cols=["col2"], dataset=True, mode="WRONG")
    paths = wr.s3.to_parquet(df=df_file, path=path_file)["paths"]
    wr.s3.wait_objects_exist(paths=paths)
    assert len(wr.s3.read_parquet(path=path_file, use_threads=True, boto3_session=None).index) == 3
    assert len(wr.s3.read_parquet(path=[path_file], use_threads=False, boto3_session=boto3.DEFAULT_SESSION).index) == 3
    paths = wr.s3.to_parquet(df=df_dataset, path=path_dataset, dataset=True)["paths"]
    wr.s3.wait_objects_exist(paths=paths)
    with pytest.raises(wr.exceptions.InvalidArgument):
        assert wr.s3.read_parquet(path=paths, dataset=True)
    assert len(wr.s3.read_parquet(path=path_dataset, use_threads=True, boto3_session=boto3.DEFAULT_SESSION).index) == 3
    dataset_paths = wr.s3.to_parquet(
        df=df_dataset, path=path_dataset, dataset=True, partition_cols=["partition"], mode="overwrite"
    )["paths"]
    wr.s3.wait_objects_exist(paths=dataset_paths)
    assert len(wr.s3.read_parquet(path=path_dataset, use_threads=True, boto3_session=None).index) == 3
    assert len(wr.s3.read_parquet(path=dataset_paths, use_threads=True).index) == 3
    assert len(wr.s3.read_parquet(path=path_dataset, dataset=True, use_threads=True).index) == 3
    wr.s3.to_parquet(df=df_dataset, path=path_dataset, dataset=True, partition_cols=["partition"], mode="overwrite")
    wr.s3.to_parquet(
        df=df_dataset, path=path_dataset, dataset=True, partition_cols=["partition"], mode="overwrite_partitions"
    )


def test_parquet_validate_schema(path):
    df = pd.DataFrame({"id": [1, 2, 3]})
    path_file = f"{path}0.parquet"
    wr.s3.to_parquet(df=df, path=path_file)
    wr.s3.wait_objects_exist(paths=[path_file])
    df2 = pd.DataFrame({"id2": [1, 2, 3], "val": ["foo", "boo", "bar"]})
    path_file2 = f"{path}1.parquet"
    wr.s3.to_parquet(df=df2, path=path_file2)
    wr.s3.wait_objects_exist(paths=[path_file2], use_threads=False)
    df3 = wr.s3.read_parquet(path=path, validate_schema=False)
    assert len(df3.index) == 6
    assert len(df3.columns) == 3
    with pytest.raises(wr.exceptions.InvalidSchemaConvergence):
        wr.s3.read_parquet(path=path, validate_schema=True)


def test_parquet_uint64(path):
    wr.s3.delete_objects(path=path)
    df = pd.DataFrame(
        {
            "c0": [0, 0, (2 ** 8) - 1],
            "c1": [0, 0, (2 ** 16) - 1],
            "c2": [0, 0, (2 ** 32) - 1],
            "c3": [0, 0, (2 ** 64) - 1],
            "c4": [0, 1, 2],
        }
    )
    df["c0"] = df.c0.astype("uint8")
    df["c1"] = df.c1.astype("uint16")
    df["c2"] = df.c2.astype("uint32")
    df["c3"] = df.c3.astype("uint64")
    paths = wr.s3.to_parquet(df=df, path=path, dataset=True, mode="overwrite", partition_cols=["c4"])["paths"]
    wr.s3.wait_objects_exist(paths=paths, use_threads=False)
    df = wr.s3.read_parquet(path=path, dataset=True)
    assert len(df.index) == 3
    assert len(df.columns) == 5
    assert df.c0.max() == (2 ** 8) - 1
    assert df.c1.max() == (2 ** 16) - 1
    assert df.c2.max() == (2 ** 32) - 1
    assert df.c3.max() == (2 ** 64) - 1
    assert df.c4.astype("uint8").sum() == 3
    wr.s3.delete_objects(path=path)


def test_parquet_metadata_partitions(path):
    path = f"{path}0.parquet"
    df = pd.DataFrame({"c0": [0, 1, 2], "c1": ["3", "4", "5"], "c2": [6.0, 7.0, 8.0]})
    paths = wr.s3.to_parquet(df=df, path=path, dataset=False)["paths"]
    wr.s3.wait_objects_exist(paths=paths, use_threads=False)
    columns_types, partitions_types = wr.s3.read_parquet_metadata(path=path, dataset=False)
    assert len(columns_types) == len(df.columns)
    assert columns_types.get("c0") == "bigint"
    assert columns_types.get("c1") == "string"
    assert columns_types.get("c2") == "double"


def test_parquet_cast_string(path):
    df = pd.DataFrame({"id": [1, 2, 3], "value": ["foo", "boo", "bar"]})
    path_file = f"{path}0.parquet"
    wr.s3.to_parquet(df, path_file, dtype={"id": "string"}, sanitize_columns=False)
    wr.s3.wait_objects_exist([path_file])
    df2 = wr.s3.read_parquet(path_file)
    assert str(df2.id.dtypes) == "string"
    assert df.shape == df2.shape
    for col, row in tuple(itertools.product(df.columns, range(3))):
        assert df[col].iloc[row] == df2[col].iloc[row]


def test_to_parquet_file_sanitize(path):
    df = pd.DataFrame({"C0": [0, 1], "camelCase": [2, 3], "c**--2": [4, 5]})
    path_file = f"{path}0.parquet"
    wr.s3.to_parquet(df, path_file, sanitize_columns=True)
    wr.s3.wait_objects_exist([path_file])
    df2 = wr.s3.read_parquet(path_file)
    assert df.shape == df2.shape
    assert list(df2.columns) == ["c0", "camel_case", "c_2"]
    assert df2.c0.sum() == 1
    assert df2.camel_case.sum() == 5
    assert df2.c_2.sum() == 9


@pytest.mark.parametrize("use_threads", [True, False])
def test_to_parquet_file_dtype(path, use_threads):
    df = pd.DataFrame({"c0": [1.0, None, 2.0], "c1": [pd.NA, pd.NA, pd.NA]})
    file_path = f"{path}0.parquet"
    wr.s3.to_parquet(df, file_path, dtype={"c0": "bigint", "c1": "string"}, use_threads=use_threads)
    wr.s3.wait_objects_exist(paths=[file_path], use_threads=use_threads)
    df2 = wr.s3.read_parquet(file_path, use_threads=use_threads)
    assert df2.shape == df.shape
    assert df2.c0.sum() == 3
    assert str(df2.c0.dtype) == "Int64"
    assert str(df2.c1.dtype) == "string"


@pytest.mark.parametrize("use_threads", [True, False])
@pytest.mark.parametrize("max_rows_by_file", [None, 0, 40, 250, 1000])
def test_parquet_with_size(path, use_threads, max_rows_by_file):
    df = get_df_list()
    df = pd.concat([df for _ in range(100)])
    paths = wr.s3.to_parquet(
        df=df,
        path=path + "x.parquet",
        index=False,
        dataset=False,
        max_rows_by_file=max_rows_by_file,
        use_threads=use_threads,
    )["paths"]
    if max_rows_by_file is not None and max_rows_by_file > 0:
        assert len(paths) >= math.floor(300 / max_rows_by_file)
        assert len(paths) <= math.ceil(300 / max_rows_by_file)
    wr.s3.wait_objects_exist(paths, use_threads=use_threads)
    df2 = wr.s3.read_parquet(path=path, dataset=False, use_threads=use_threads)
    ensure_data_types(df2, has_list=True)
    assert df2.shape == (300, 19)
    assert df.iint8.sum() == df2.iint8.sum()


@pytest.mark.parametrize("use_threads", [True, False])
def test_index_and_timezone(path, use_threads):
    df = pd.DataFrame({"c0": [datetime.utcnow(), datetime.utcnow()], "par": ["a", "b"]}, index=["foo", "boo"])
    df["c1"] = pd.DatetimeIndex(df.c0).tz_localize(tz="US/Eastern")
    paths = wr.s3.to_parquet(df, path, index=True, use_threads=use_threads, dataset=True, partition_cols=["par"])[
        "paths"
    ]
    wr.s3.wait_objects_exist(paths=paths, use_threads=use_threads)
    df2 = wr.s3.read_parquet(path, use_threads=use_threads, dataset=True)
    assert df[["c0", "c1"]].equals(df2[["c0", "c1"]])


@pytest.mark.parametrize("use_threads", [True, False])
def test_index_recovery_simple_int(path, use_threads):
    df = pd.DataFrame({"c0": np.arange(10, 1_010, 1)}, dtype="Int64")
    paths = wr.s3.to_parquet(df, path, index=True, use_threads=use_threads, dataset=True, max_rows_by_file=300)["paths"]
    assert len(paths) == 4
    wr.s3.wait_objects_exist(paths=paths, use_threads=use_threads)
    df2 = wr.s3.read_parquet(f"{path}*.parquet", use_threads=use_threads)
    assert df.equals(df2)


@pytest.mark.parametrize("use_threads", [True, False])
def test_index_recovery_simple_str(path, use_threads):
    df = pd.DataFrame({"c0": [0, 1, 2, 3, 4]}, index=["a", "b", "c", "d", "e"], dtype="Int64")
    paths = wr.s3.to_parquet(df, path, index=True, use_threads=use_threads, dataset=True, max_rows_by_file=1)["paths"]
    assert len(paths) == 5
    wr.s3.wait_objects_exist(paths=paths, use_threads=use_threads)
    df2 = wr.s3.read_parquet(f"{path}*.parquet", use_threads=use_threads)
    assert df.equals(df2)


@pytest.mark.parametrize("use_threads", [True, False])
def test_index_recovery_partitioned_str(path, use_threads):
    df = pd.DataFrame(
        {"c0": [0, 1, 2, 3, 4], "par": ["foo", "boo", "bar", "foo", "boo"]}, index=["a", "b", "c", "d", "e"]
    )
    df["c0"] = df["c0"].astype("Int64")
    df["par"] = df["c0"].astype("category")
    paths = wr.s3.to_parquet(
        df, path, index=True, use_threads=use_threads, dataset=True, partition_cols=["par"], max_rows_by_file=1
    )["paths"]
    assert len(paths) == 5
    wr.s3.wait_objects_exist(paths=paths, use_threads=use_threads)
    df2 = wr.s3.read_parquet(f"{path}*.parquet", use_threads=use_threads, dataset=True)
    assert df.shape == df2.shape
    assert df.c0.equals(df2.c0)
    assert df.dtypes.equals(df2.dtypes)
    assert df.index.equals(df2.index)


@pytest.mark.parametrize("use_threads", [True, False])
def test_range_index_recovery_simple(path, use_threads):
    df = pd.DataFrame({"c0": np.arange(10, 15, 1)}, dtype="Int64", index=pd.RangeIndex(start=5, stop=30, step=5))
    paths = wr.s3.to_parquet(df, path, index=True, use_threads=use_threads, dataset=True, max_rows_by_file=3)["paths"]
    assert len(paths) == 2
    wr.s3.wait_objects_exist(paths=paths, use_threads=use_threads)
    df2 = wr.s3.read_parquet(f"{path}*.parquet", use_threads=use_threads)
    assert df.reset_index(level=0).equals(df2.reset_index(level=0))


@pytest.mark.parametrize("use_threads", [True, False])
@pytest.mark.parametrize("name", [None, "foo"])
def test_range_index_recovery_pandas(path, use_threads, name):
    df = pd.DataFrame({"c0": np.arange(10, 15, 1)}, dtype="Int64", index=pd.RangeIndex(start=5, stop=30, step=5))
    df.index.name = name
    path_file = f"{path}0.parquet"
    df.to_parquet(path_file)
    wr.s3.wait_objects_exist(paths=[path_file], use_threads=use_threads)
    df2 = wr.s3.read_parquet([path_file], use_threads=use_threads)
    assert df.reset_index(level=0).equals(df2.reset_index(level=0))


@pytest.mark.parametrize("use_threads", [True, False])
def test_multi_index_recovery_simple(path, use_threads):
    df = pd.DataFrame({"c0": [0, 1, 2], "c1": ["a", "b", "c"], "c2": [True, False, True], "c3": [0, 1, 2]})
    df["c3"] = df["c3"].astype("Int64")
    df = df.set_index(["c0", "c1", "c2"])
    paths = wr.s3.to_parquet(df, path, index=True, use_threads=use_threads, dataset=True, max_rows_by_file=1)["paths"]
    assert len(paths) == 3
    wr.s3.wait_objects_exist(paths=paths, use_threads=use_threads)
    df2 = wr.s3.read_parquet(f"{path}*.parquet", use_threads=use_threads)
    assert df.reset_index().equals(df2.reset_index())


@pytest.mark.parametrize("use_threads", [True, False])
def test_multi_index_recovery_nameless(path, use_threads):
    df = pd.DataFrame({"c0": np.arange(10, 13, 1)}, dtype="Int64")
    df = df.set_index([[1, 2, 3], [1, 2, 3]])
    paths = wr.s3.to_parquet(df, path, index=True, use_threads=use_threads, dataset=True, max_rows_by_file=1)["paths"]
    assert len(paths) == 3
    wr.s3.wait_objects_exist(paths=paths, use_threads=use_threads)
    df2 = wr.s3.read_parquet(f"{path}*.parquet", use_threads=use_threads)
    assert df.reset_index().equals(df2.reset_index())


def test_to_parquet_dataset_sanitize(path):
    df = pd.DataFrame({"C0": [0, 1], "camelCase": [2, 3], "c**--2": [4, 5], "Par": ["a", "b"]})

    paths = wr.s3.to_parquet(df, path, dataset=True, partition_cols=["Par"], sanitize_columns=False)["paths"]
    wr.s3.wait_objects_exist(paths)
    df2 = wr.s3.read_parquet(path, dataset=True)
    assert df.shape == df2.shape
    assert list(df2.columns) == ["C0", "camelCase", "c**--2", "Par"]
    assert df2.C0.sum() == 1
    assert df2.camelCase.sum() == 5
    assert df2["c**--2"].sum() == 9
    assert df2.Par.to_list() == ["a", "b"]

    paths = wr.s3.to_parquet(df, path, dataset=True, partition_cols=["par"], sanitize_columns=True, mode="overwrite")[
        "paths"
    ]
    wr.s3.wait_objects_exist(paths)
    df2 = wr.s3.read_parquet(path, dataset=True)
    assert df.shape == df2.shape
    assert list(df2.columns) == ["c0", "camel_case", "c_2", "par"]
    assert df2.c0.sum() == 1
    assert df2.camel_case.sum() == 5
    assert df2.c_2.sum() == 9
    assert df2.par.to_list() == ["a", "b"]


@pytest.mark.parametrize("use_threads", [False, True])
def test_timezone_file(path, use_threads):
    file_path = f"{path}0.parquet"
    df = pd.DataFrame({"c0": [datetime.utcnow(), datetime.utcnow()]})
    df["c0"] = pd.DatetimeIndex(df.c0).tz_localize(tz="US/Eastern")
    df.to_parquet(file_path)
    wr.s3.wait_objects_exist(paths=[file_path], use_threads=use_threads)
    df2 = wr.s3.read_parquet(path, use_threads=use_threads)
    assert df.equals(df2)


@pytest.mark.parametrize("use_threads", [False])
def test_timezone_file_columns(path, use_threads):
    file_path = f"{path}0.parquet"
    df = pd.DataFrame({"c0": [datetime.utcnow(), datetime.utcnow()], "c1": [1.1, 2.2]})
    df["c0"] = pd.DatetimeIndex(df.c0).tz_localize(tz="US/Eastern")
    df.to_parquet(file_path)
    wr.s3.wait_objects_exist(paths=[file_path], use_threads=use_threads)
    df2 = wr.s3.read_parquet(path, columns=["c1"], use_threads=use_threads)
    assert df[["c1"]].equals(df2)
