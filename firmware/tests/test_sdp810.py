import pytest

from crowe.sensors.base import sensirion_crc
from crowe.sensors.sdp810 import ADDR, CMD_START_CONT_DP_AVG, SDP810


def _frame(dp_raw: int, t_raw: int, scale: int) -> list[int]:
    out = []
    for word in (dp_raw, t_raw, scale):
        b = word.to_bytes(2, "big", signed=word < 0)
        out += [b[0], b[1], sensirion_crc(b)]
    return out


def test_decode_scales_pressure_and_temperature():
    dp, t = SDP810.decode(_frame(1500, 4600, 60))
    assert dp == 25.0
    assert t == 23.0


def test_decode_negative_pressure():
    dp, _ = SDP810.decode(_frame(-300, 4000, 60))
    assert dp == -5.0


def test_decode_rejects_bad_crc():
    frame = _frame(1500, 4600, 60)
    frame[2] ^= 0xFF
    with pytest.raises(ValueError, match="crc"):
        SDP810.decode(frame)


@pytest.mark.asyncio
async def test_read_starts_continuous_mode_once_and_emits_two_channels(fake_bus):
    fake_bus.queue(ADDR, 0x00, _frame(1500, 4600, 60))
    s = SDP810(fake_bus)
    r1 = await s.read()
    r2 = await s.read()
    assert [(r.channel, r.value, r.unit) for r in r1] == [("prefilter_dp_pa", 25.0, "Pa"), ("temperature_c", 23.0, "C")]
    assert len(r2) == 2
    starts = [w for w in fake_bus.writes if w[1] == CMD_START_CONT_DP_AVG >> 8]
    assert len(starts) == 1
