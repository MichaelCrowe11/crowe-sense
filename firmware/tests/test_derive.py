from crowe.derive import dew_point_c, vpd_kpa


def test_vpd_matches_the_rig_formula():
    # 21.0 C at 85 % RH: 0.6108*exp(17.27*21/258.3)*(0.15) = 0.3729 kPa
    assert abs(vpd_kpa(21.0, 85.0) - 0.3729) < 0.001
    assert vpd_kpa(20.0, 100.0) == 0.0


def test_dew_point_is_below_air_temperature_and_equal_at_saturation():
    assert dew_point_c(21.0, 85.0) < 21.0
    assert abs(dew_point_c(21.0, 100.0) - 21.0) < 0.05
    assert abs(dew_point_c(21.0, 85.0) - 18.4) < 0.2
