import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

import pytest

from subscript.check_swatinit.check_swatinit import (
    __FINE_EQUIL__,
    __HC_BELOW_FWL__,
    __PC_SCALED__,
    __PPCWMAX__,
    __SWATINIT_1__,
    __SWL_TRUNC__,
    __UNKNOWN__,
    __WATER__,
    _evaluate_pc,
    compute_pc,
    merge_equil,
    qc_flag,
    qc_volumes,
    main,
)

REEK_DATAFILE = (
    Path(__file__).absolute().parent
    / "data"
    / "reek"
    / "eclipse"
    / "model"
    / "2_R001_REEK-0.DATA"
)


@pytest.mark.parametrize(
    "propslist, expected_flag",
    [
        ([{"SWL": 0.3, "SWATINIT": 0.1}], __SWL_TRUNC__),
        (
            [{"SWATINIT": 0.9, "SWAT": 1.0, "Z": 1000, "OWC": 900}],
            __HC_BELOW_FWL__,
        ),
        ([{"SWAT": 0.3, "SWATINIT": 0.3}], __PC_SCALED__),
        (
            [{"SWATINIT": 0.9, "SWAT": 0.8, "PPCW": 100, "PPCWMAX": 100}],
            __PPCWMAX__,
        ),
        (
            [{"SWATINIT": 0.9, "SWAT": 0.8, "PPCW": 1, "PCW": 1}],
            __UNKNOWN__,  # We need PC_SCALING != 1, and can't claim it is EQUIL
        ),
        (
            [{"SWATINIT": 0.9, "SWAT": 0.9, "PPCW": 1.1, "PCW": 1}],
            __PC_SCALED__,
        ),
        (
            [{"SWATINIT": 1, "SWAT": 1}],
            __UNKNOWN__,
        ),  # Not enough information
        (
            [{"SWATINIT": 1, "Z": 100, "OWC": 900}],
            __SWATINIT_1__,
        ),
        (
            [{"SWATINIT": 1, "SWAT": 0.9, "Z": 100, "OWC": 900}],
            # In this case, E100 has ignored SWATINIT and found
            # its own SWAT based on capillary pressure
            __SWATINIT_1__,
        ),
        (
            [{"SWATINIT": 1, "SWAT": 1, "Z": 890, "OWC": 900}],
            # SWAT can still end up at 1 if capillary entry pressure
            # is higher than PC
            __SWATINIT_1__,
        ),
        (
            [{"SWATINIT": 1, "SWAT": 1, "Z": 100, "OWC": 50}],
            __WATER__,
        ),
        (
            [
                {
                    "SWATINIT": 0.56,
                    "SWAT": 0.67,
                    "PC_SCALING": 0.22,
                    "SWL": 0.1,
                    "OIP_INIT": -5,
                }
            ],
            __FINE_EQUIL__,
        ),
        (
            [
                {
                    "SWATINIT": 0.97,
                    "SWAT": 0.7,
                    "PC_SCALING": 22.1,
                    "SWL": 0.1,
                    "OIP_INIT": -5,
                }
            ],
            __FINE_EQUIL__,
        ),
        (
            [{"SWATINIT": 1, "SWAT": 0.67, "Z": 1000, "OWC": 900, "PPCW": 3, "PCW": 3}],
            # This is not believed to be possible output from Eclipse.
            __UNKNOWN__,
        ),
        (
            [
                {
                    "SWATINIT": 0.9,
                    "SWAT": 0.8,
                    "PC_SCALING": 0.8,
                    "Z": 1000,
                    "OWC": 900,
                    "OIP_INIT": -5,
                }
            ],
            __FINE_EQUIL__,
        ),
        (
            [
                {
                    "SWATINIT": 0.9,
                    "SWAT": 0.8,
                    "PC_SCALING": 0.8,
                    "Z": 900,
                    "OWC": 1000,
                    "OIP_INIT": -5,
                }
            ],
            __FINE_EQUIL__,
        ),
        (
            [
                {
                    "SWATINIT": 0.9,
                    "SWAT": 0.8,
                    "PC_SCALING": 1,
                    "Z": 900,
                    "OWC": 1000,
                    "OIP_INIT": -5,
                }
            ],
            __FINE_EQUIL__,
        ),
        (
            [
                {
                    "SWATINIT": 1,
                    "SWAT": 0.8,
                    "Z": 1100,
                    "OWC": 1000,
                    "OIP_INIT": 0,
                }
            ],
            __UNKNOWN__,
        ),
        (
            [
                {
                    # SWATINIT 1 below contact
                    "SWATINIT": 1,
                    "SWAT": 0.8,
                    "Z": 1100,
                    "OWC": 1000,
                    "OIP_INIT": -5,
                }
            ],
            __SWATINIT_1__,
        ),
        # Tests with GWC instead of GOC/OWC:
        (
            [
                {
                    # SWATINIT 1 below contact:
                    "SWATINIT": 1,
                    "SWAT": 0.8,
                    "Z": 1100,
                    "GWC": 1000,
                    "OIP_INIT": -5,
                }
            ],
            __SWATINIT_1__,
        ),
        (
            [
                {
                    "SWATINIT": 0.4,
                    "SWAT": 0.4,
                    "Z": 1000,
                    "GWC": 1100,
                }
            ],
            __PC_SCALED__,
        ),
        (
            [
                {
                    "SWATINIT": 0.4,
                    "SWAT": 0.4,
                    "Z": 1200,
                    "GWC": 1100,
                    "OIP_INIT": -2,
                }
            ],
            __PC_SCALED__,
        ),
        (
            [
                {
                    "SWATINIT": 0.4,
                    "SWAT": 1,
                    "Z": 1200,
                    "GWC": 1100,
                }
            ],
            __HC_BELOW_FWL__,
        ),
    ],
)
def test_qc_flag(propslist, expected_flag):
    """Test that the qc flag is assigned correctly in different situations"""
    qc_frame = pd.DataFrame(propslist)
    if "SWL" not in qc_frame:
        qc_frame["SWL"] = np.nan
    if "SWAT" not in qc_frame:
        qc_frame["SWAT"] = np.nan
    if "OWC" not in qc_frame and "GWC" not in qc_frame:
        qc_frame["OWC"] = np.nan
    if "Z" not in qc_frame:
        qc_frame["Z"] = np.nan
    if "PPCW" not in qc_frame:
        qc_frame["PPCW"] = np.nan
    if "PCW" not in qc_frame:
        qc_frame["PCW"] = np.nan
    assert qc_flag(qc_frame)[0] == expected_flag


@pytest.mark.parametrize(
    "propslist, expected_dict",
    [
        (
            [{"SWATINIT": 1, "PORV": 1e6, "SWAT": 1}],
            {"SWAT_WVOL": 1e6, "PORV": 1e6},
        ),
        (
            [{"SWATINIT": 1, "PORV": 1e6, "SWAT": 0.5}],
            {"SWAT_WVOL": 5e5},
        ),
        (
            [{"SWATINIT": 1, "PORV": 1e6, "SWAT": 0.5, "QC_FLAG": __PPCWMAX__}],
            {
                __PPCWMAX__: (0.5 - 1) * 1e6,
            },
        ),
        (
            [{"SWATINIT": 1, "PORV": 1e6, "SWAT": 0.5, "QC_FLAG": __SWATINIT_1__}],
            {
                __SWATINIT_1__: (0.5 - 1) * 1e6,
            },
        ),
        (
            [{"SWATINIT": 0.1, "PORV": 1e6, "SWAT": 0.2, "QC_FLAG": __SWL_TRUNC__}],
            {
                __SWL_TRUNC__: (0.2 - 0.1) * 1e6,
            },
        ),
        (
            [{"SWATINIT": 0.9, "PORV": 1e6, "SWAT": 1, "QC_FLAG": __HC_BELOW_FWL__}],
            {__HC_BELOW_FWL__: (1 - 0.9) * 1e6, __WATER__: 0},
        ),
    ],
)
def test_qc_volumes(propslist, expected_dict):
    """Test that we calculate qc volumes correctly from a cell-based qc dataframe"""
    qc_frame = pd.DataFrame(propslist)
    qc_vols = qc_volumes(qc_frame)
    for key in expected_dict.keys():
        assert np.isclose(qc_vols[key], expected_dict[key])


@pytest.mark.parametrize(
    "swats, scale_vert, swls, expected_pc",
    [
        ([0], [1], None, [3]),
        ([0.1], [1], None, [3]),
        ([1], [1], None, [0]),
        ([0, 1], [1, 1], None, [3, 0]),
        ([2], [1], None, [0]),  # constant extrapolation
        ([0.55], [1], None, [1.5]),
        ([0.55], [2], None, [3]),
        ([0.55], [2], [0], [3 - 3 / 10.0]),
        ([0], [1], [0], [3]),
        ([0.1], [1], [0], [3 - 3 / 10.0]),
        ([1], [1], [0], [0]),
        ([0.5], [1], [0.5], [3]),
    ],
)
def test_evaluate_pc(swats, scale_vert, swls, expected_pc):
    """Test that we can evaluate capillary pressure from a saturation table
    when we also allow the pc in the table to be scaled as Eclipse is doing it"""
    satfunc_df = pd.DataFrame([{"SW": 0.1, "PCOW": 3}, {"SW": 1, "PCOW": 0}])
    assert np.isclose(
        _evaluate_pc(swats, scale_vert, swls, satfunc_df), expected_pc
    ).all()


@pytest.mark.parametrize(
    "gridlist, equillist, expected",
    [
        (
            [{"EQLNUM": 1}],
            [{"Z": 1000, "PRESSURE": 100, "OWC": 1000, "EQLNUM": 1, "OIP_INIT": 20}],
            [
                {
                    "EQLNUM": 1,
                    "Z_DATUM": 1000,
                    "PRESSURE_DATUM": 100,
                    "OWC": 1000,
                    "OIP_INIT": 20,
                }
            ],
        ),
        (
            # Grid with two cells:
            [{"EQLNUM": 1}, {"EQLNUM": 1}],
            [{"Z": 1000, "PRESSURE": 100, "OWC": 1000, "EQLNUM": 1, "OIP_INIT": 0}],
            [
                {
                    "EQLNUM": 1,
                    "Z_DATUM": 1000,
                    "PRESSURE_DATUM": 100,
                    "OWC": 1000,
                    "OIP_INIT": 0,
                },
                {
                    "EQLNUM": 1,
                    "Z_DATUM": 1000,
                    "PRESSURE_DATUM": 100,
                    "OWC": 1000,
                    "OIP_INIT": 0,
                },
            ],
        ),
        (
            # Grid with two cells and two EQLNUMs:
            [{"EQLNUM": 1}, {"EQLNUM": 2}],
            [
                {"Z": 1000, "PRESSURE": 100, "OWC": 1000, "EQLNUM": 1, "OIP_INIT": -5},
                {"Z": 1000, "PRESSURE": 200, "OWC": 2000, "EQLNUM": 2, "OIP_INIT": -5},
            ],
            [
                {
                    "EQLNUM": 1,
                    "Z_DATUM": 1000,
                    "PRESSURE_DATUM": 100,
                    "OWC": 1000,
                    "OIP_INIT": -5,
                },
                {
                    "EQLNUM": 2,
                    "Z_DATUM": 1000,
                    "PRESSURE_DATUM": 200,
                    "OWC": 2000,
                    "OIP_INIT": -5,
                },
            ],
        ),
    ],
)
def test_merge_equil(gridlist, equillist, expected):
    """Test that we can merge EQUIL information onto a cell-based dataframe"""
    pd.testing.assert_frame_equal(
        merge_equil(pd.DataFrame(gridlist), pd.DataFrame(equillist)),
        pd.DataFrame(expected),
        check_like=True,
    )


SATFUNC_DF = pd.DataFrame([{"SW": 0.1, "PCOW": 3}, {"SW": 1, "PCOW": 0}]).assign(
    SATNUM=1
)


@pytest.mark.parametrize(
    "propslist, satfunc_df, expected_pc",
    [
        ([], None, None),
        ([{}], None, None),
        ([{"SWL": 0.1}], None, np.nan),
        ([{"SATNUM": 1, "PC_SCALING": 1, "SWAT": 0.1}], SATFUNC_DF, 3),
        ([{"SATNUM": 1, "PC_SCALING": 1, "SWAT": 1}], SATFUNC_DF, 0),
        ([{"SATNUM": 1, "PC_SCALING": 2, "SWAT": 0.1}], SATFUNC_DF, 6),
        ([{"SATNUM": 1, "PC_SCALING": 2, "SWAT": 0.55}], SATFUNC_DF, 3),
        (
            [{"SATNUM": 2, "PC_SCALING": 2, "SWAT": 0.55}],
            SATFUNC_DF.assign(SATNUM=2),
            3,
        ),
        ([{"SATNUM": 1, "SWAT": 0.55}], SATFUNC_DF, np.nan),
        # Test special casing for OPM-flow above contact where SWATINIT=1:
        (
            [{"SATNUM": 1, "SWAT": 1, "QC_FLAG": __SWATINIT_1__, "Z": 100, "OWC": 300}],
            SATFUNC_DF,
            np.nan,
        ),
    ],
)
def test_compute_pc(propslist, satfunc_df, expected_pc):
    """Test the computation of capillary pressure in one reservoir cell, defined by
    properties in a qc dataframe.

    Also see the tests running OPM and Eclipse100, they define correctness of
    the computation, while this test more documents the behaviour on a (qc)
    dataframe than testing correctness. Half the "pc computation" lies in the
    construction of the dataframe.
    """
    qc_frame = pd.DataFrame(propslist)
    pc_series = compute_pc(qc_frame, satfunc_df)
    if qc_frame.empty:
        if not pc_series.empty:
            assert all(pd.isnull(pc_series))
    else:
        if pd.isnull(expected_pc):
            assert pd.isnull(pc_series.values[0])
        else:
            assert pc_series.values[0] == expected_pc


def test_reek(tmpdir, mocker):
    """Test that we can run on the Reek dataset with no crashes,
    and with plotting to file"""

    tmpdir.chdir()
    mocker.patch(
        "sys.argv",
        [
            "check_swatinit",
            str(REEK_DATAFILE),
            "--output",
            "foo.csv",
            "--plotfile",
            "scatter.png",
            "--volplotfile",
            "volplot.png",
        ],
    )
    main()
    qc_frame = pd.read_csv("foo.csv")
    assert Path("scatter.png").exists()
    assert Path("volplot.png").exists()

    # Check that we never get -1e20 from libecl in any data:
    assert np.isclose(qc_frame.select_dtypes("number").min().min(), -7097, atol=1)
    assert np.isclose(qc_frame.select_dtypes("number").max().max(), 5938824, atol=1)

    mocker.patch(
        "sys.argv",
        [
            "check_swatinit",
            "foo.csv",
            "--plotfile",
            "scatter_eqlnum2.png",
            "--eqlnum",
            "2",
        ],
    )
    main()
    # (EQLNUM 2 in Reek is only water)
    assert Path("scatter_eqlnum2.png").exists()

    mocker.patch(
        "sys.argv",
        [
            "check_swatinit",
            "foo.csv",
            "--plotfile",
            "scatter_eqlnum99.png",
            "--eqlnum",
            "99",
        ],
    )
    with pytest.raises(SystemExit, match="EQLNUM"):
        main()
    assert not Path("scatter_eqlnum99.png").exists()


@pytest.mark.integration
def test_ert_integration(tmpdir):
    tmpdir.chdir()
    Path("test.ert").write_text(
        "\n".join(
            [
                "ECLBASE DUMMY.DATA",
                "QUEUE_SYSTEM LOCAL",
                "NUM_REALIZATIONS 1",
                "RUNPATH .",
                "",
                f"FORWARD_MODEL CHECK_SWATINIT(<DATAFILE>={REEK_DATAFILE})",
            ]
        )
    )
    subprocess.run(["ert", "test_run", "test.ert"], check=True)
    # Testing the default OUTPUT:
    qc_frame = pd.read_csv("check_swatinit.csv")
    assert not qc_frame.empty

    # Test again with a different output file
    Path("test-output.ert").write_text(
        "\n".join(
            [
                "ECLBASE DUMMY.DATA",
                "QUEUE_SYSTEM LOCAL",
                "NUM_REALIZATIONS 1",
                "RUNPATH .",
                "",
                (
                    f"FORWARD_MODEL CHECK_SWATINIT(<DATAFILE>={REEK_DATAFILE}, "
                    "<OUTPUT>=foo.csv)"
                ),
            ]
        )
    )
    subprocess.run(["ert", "test_run", "test-output.ert"], check=True)
    qc_frame = pd.read_csv("foo.csv")
    assert not qc_frame.empty


@pytest.mark.integration
def test_endpoint_installed():
    """Test that the endpoint is installed"""
    assert subprocess.check_output(["check_swatinit", "-h"])
